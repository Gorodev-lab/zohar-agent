#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║  ZOHAR AGENT v2.1 — NATIONAL MONITORING PIPELINE                ║
║  AMD A8 Optimized · Stdlib only (sin dependencias externas)     ║
╚══════════════════════════════════════════════════════════════════╝

FLUJO PRINCIPAL:
  1. MONITOR  → Detecta nuevas Gacetas en semarnat.gob.mx
  2. DISCOVER → Descarga PDFs, extrae IDs de proyectos
  3. EXTRACT  → Llama a Qwen para obtener datos estructurados
  4. FETCH    → Consulta portal SEMARNAT y descarga documentos

URLs clave:
  Gaceta listing : http://sinat.semarnat.gob.mx/Gaceta/gacetapublicacion/?ai={year}
  PDF pattern    : http://sinat.semarnat.gob.mx/Gacetas/archivos{year}/gaceta_{n}-{yy}.pdf
  Portal consulta: https://app.semarnat.gob.mx/consulta-tramite/#/portal-consulta
  Portal API     : https://apps1.semarnat.gob.mx/ws-bitacora-tramite/proyectos/{id}
"""

import os, re, json, csv, time, signal, logging, datetime
import subprocess, urllib.request, urllib.error, urllib.parse
import hashlib
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional

# ─────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────────────────
HOME = Path.home()
AGENT_DIR = HOME / "zohar-agent" / "agent"

CONFIG = {
    # Dirs & Files
    "WORK_DIR":     HOME / "gaceta_work",
    "DOCS_DIR":     HOME / "gaceta_work" / "documentos",
    "CSV_FILE":     HOME / "zohar_historico_proyectos.csv",
    "STATE_FILE":   HOME / "zohar_agent_state.json",
    "QUEUE_FILE":   AGENT_DIR / "zohar_queue.json",
    "LOG_FILE":     AGENT_DIR / "zohar_agent.jsonl",
    "SEEN_FILE":    AGENT_DIR / "zohar_seen_gacetas.json",  # hash de gacetas ya procesadas
    "GRAPH_FILE":   HOME / "zohar_grafo.triples",

    # Llama server (Qwen 2.5 1.5B)
    "MOTOR_URL":    "http://127.0.0.1:8001/v1/chat/completions",
    "MODEL":        "qwen2.5-1.5b-instruct-q4_k_m.gguf",

    # SEMARNAT — IMPORTANTE: HTTP puro (no HTTPS), el servidor usa :8080
    "GACETA_LIST_URL":  "http://sinat.semarnat.gob.mx/Gaceta/gacetapublicacion/?ai={year}",
    "GACETA_PDF_BASE":  "http://sinat.semarnat.gob.mx/Gacetas/archivos{year}/",
    "PORTAL_API_BASE":  "https://apps1.semarnat.gob.mx/ws-bitacora-tramite/proyectos/",
    "PORTAL_URL":       "https://app.semarnat.gob.mx/consulta-tramite/#/portal-consulta",

    # Extracción
    "MAX_RETRIES":       3,
    "RETRY_BASE_WAIT":   10,      # segundos, backoff: 10→20→40
    "COOL_DOWN_NORMAL":  6,
    "COOL_DOWN_HOT":     20,
    "TEMP_WARN":         76.0,
    "TEMP_CRIT":         85.0,
    "LLAMA_TIMEOUT":     35,
    "MAX_TOKENS":        250,
    "CONTEXT_CHARS":     900,

    # Ciclo de monitoreo
    "POLL_INTERVAL_MIN": 30,      # minutos entre chequeos de nuevas gacetas
    "YEAR":              2026,
    "DRY_RUN":           False,
    "DAEMON_MODE":       False,   # True = corre indefinidamente
}

# Regex ID SEMARNAT: 2 dígitos + 2 letras + 4 dígitos + 2-5 alfanum
# Ejemplos: 23QR2025TD077, 21PU2025H0155, 20OA2025V0090
ID_PATTERN = re.compile(r'\b\d{2}[A-Z]{2}\d{4}[A-Z0-9]{2,5}\b')

# ─────────────────────────────────────────────────────────
# LOGGER (JSON Lines + consola legible)
# ─────────────────────────────────────────────────────────
class _JsonlHandler(logging.Handler):
    def __init__(self, path: Path):
        super().__init__()
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, record):
        entry = {
            "ts":    datetime.datetime.now().isoformat(timespec="seconds"),
            "level": record.levelname,
            "msg":   self.format(record),
        }
        if hasattr(record, "extra"):
            entry["data"] = record.extra
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

def setup_logging(path: Path) -> logging.Logger:
    log = logging.getLogger("zohar")
    log.setLevel(logging.DEBUG)
    if log.handlers:
        log.handlers.clear()
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S"))
    log.addHandler(ch)
    jh = _JsonlHandler(path)
    jh.setLevel(logging.DEBUG)
    jh.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(jh)
    return log

def log_extra(log, level, msg, **kwargs):
    record = log.makeRecord(log.name, level, "", 0, msg, [], None)
    record.extra = kwargs
    log.handle(record)


# ─────────────────────────────────────────────────────────
# PERSISTENT QUEUE
# ─────────────────────────────────────────────────────────
@dataclass
class QueueItem:
    pid:        str
    pdf:        str
    year:       int
    txt_file:   str
    attempts:   int  = 0
    status:     str  = "pending"   # pending | success | failed
    last_error: str  = ""
    added_at:   str  = field(default_factory=lambda: datetime.datetime.now().isoformat(timespec="seconds"))
    updated_at: str  = field(default_factory=lambda: datetime.datetime.now().isoformat(timespec="seconds"))

class PersistentQueue:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._d: dict[str, QueueItem] = {}
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text())
                self._d = {k: QueueItem(**v) for k, v in raw.items()}
            except Exception:
                self._d = {}

    def save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({k: asdict(v) for k, v in self._d.items()},
                                  indent=2, ensure_ascii=False))
        tmp.replace(self.path)

    def add(self, pid, pdf, year, txt_file) -> bool:
        if pid in self._d:
            return False
        self._d[pid] = QueueItem(pid=pid, pdf=pdf, year=year, txt_file=txt_file)
        self.save()
        return True

    def pending(self) -> list[QueueItem]:
        return [i for i in self._d.values()
                if i.status == "pending" and i.attempts < CONFIG["MAX_RETRIES"]]

    def mark_success(self, pid: str):
        if pid in self._d:
            self._d[pid].status    = "success"
            self._d[pid].updated_at = datetime.datetime.now().isoformat(timespec="seconds")
            self.save()

    def mark_attempt(self, pid: str, error: str = ""):
        if pid in self._d:
            item = self._d[pid]
            item.attempts  += 1
            item.last_error = error[:120]
            item.updated_at = datetime.datetime.now().isoformat(timespec="seconds")
            if item.attempts >= CONFIG["MAX_RETRIES"]:
                item.status = "failed"
            self.save()

    def is_done(self, pid: str) -> bool:
        return pid in self._d and self._d[pid].status == "success"

    def stats(self) -> dict:
        items = list(self._d.values())
        return {
            "total":   len(items),
            "success": sum(1 for i in items if i.status == "success"),
            "pending": sum(1 for i in items if i.status == "pending"),
            "failed":  sum(1 for i in items if i.status == "failed"),
        }

    def reset_failed(self):
        count = 0
        for item in self._d.values():
            if item.status == "failed":
                item.status = "pending"
                item.attempts = 0
                item.last_error = ""
                count += 1
        if count:
            self.save()
        return count


# ─────────────────────────────────────────────────────────
# SEEN GACETAS (para detectar nuevas publicaciones)
# ─────────────────────────────────────────────────────────
class SeenGacetas:
    """Persiste hashes de los listados de Gaceta para detectar cambios."""
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._d: dict[str, str] = {}  # year_str → hash del contenido HTML
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                self._d = json.loads(self.path.read_text())
            except Exception:
                self._d = {}

    def save(self):
        self.path.write_text(json.dumps(self._d, indent=2))

    def has_changed(self, year: int, content: str) -> bool:
        """Retorna True si el contenido cambió desde la última vez."""
        key  = str(year)
        h    = hashlib.md5(content.encode()).hexdigest()
        prev = self._d.get(key)
        if prev != h:
            self._d[key] = h
            self.save()
            return True
        return False


# ─────────────────────────────────────────────────────────
# THERMAL MONITOR
# ─────────────────────────────────────────────────────────
def read_temp() -> float:
    try:
        out = subprocess.check_output(["sensors"], text=True, timeout=4)
        m = re.search(r'(?:CPU|temp1|Tdie):\s+\+?([\d\.]+)', out)
        if m:
            return float(m.group(1))
    except Exception:
        pass
    return -1.0

def thermal_wait(log: logging.Logger):
    t = read_temp()
    if t >= CONFIG["TEMP_CRIT"]:
        log.warning(f"🌡️ TEMP CRÍTICA {t}°C → pausa 60s")
        time.sleep(60)
    elif t >= CONFIG["TEMP_WARN"]:
        log.info(f"🌡️ {t}°C → cool-down {CONFIG['COOL_DOWN_HOT']}s")
        time.sleep(CONFIG["COOL_DOWN_HOT"])
    else:
        time.sleep(CONFIG["COOL_DOWN_NORMAL"])


# ─────────────────────────────────────────────────────────
# LLAMA SERVER WATCHDOG
# ─────────────────────────────────────────────────────────
def wait_for_llama(log: logging.Logger, max_wait: int = 90) -> bool:
    health = "http://127.0.0.1:8001/health"
    for i in range(max_wait // 5):
        try:
            with urllib.request.urlopen(health, timeout=4) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        if i == 0:
            log.warning("⏳ llama-server no responde, esperando...")
        time.sleep(5)
    log.error("❌ llama-server no disponible")
    return False


# ─────────────────────────────────────────────────────────
# HTTP HELPER (con User-Agent y timeout)
# ─────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/109.0",
    "Accept": "text/html,application/pdf,*/*",
}

def http_get(url: str, timeout: int = 45, binary: bool = False):
    """GET simple. Retorna bytes si binary=True, str si False. None si falla."""
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
            return data if binary else data.decode("utf-8", errors="replace")
    except Exception as e:
        return None


# ─────────────────────────────────────────────────────────
# ESTADO del agente (visible en el dashboard :8081)
# ─────────────────────────────────────────────────────────
def report_state(pdf: str, action: str, target: str):
    state = {
        "pdf":    pdf,
        "action": action,
        "target": target,
        "time":   datetime.datetime.now().strftime("%H:%M:%S"),
    }
    try:
        CONFIG["STATE_FILE"].write_text(json.dumps(state))
    except Exception:
        pass


# ─────────────────────────────────────────────────────────
# PASO 1: MONITOR — detectar nuevas Gacetas
# ─────────────────────────────────────────────────────────
def fetch_pdf_links(year: int, seen: SeenGacetas, log: logging.Logger) -> list[str]:
    """
    Descarga el índice de gacetas del año y retorna lista de
    URLs de PDF. Solo notifica cambio si el contenido varió.
    """
    url = CONFIG["GACETA_LIST_URL"].format(year=year)
    report_state("—", "MONITOREANDO", f"Gaceta {year}")
    log.info(f"🔍 Verificando Gaceta {year}: {url}")

    html = http_get(url, timeout=60)
    if html is None:
        log.warning(f"  ⚠️ No se pudo acceder a la Gaceta {year}")
        return []

    changed = seen.has_changed(year, html)
    if not changed:
        log.info(f"  ✅ Sin cambios en Gaceta {year}")
        return []

    log.info(f"  🆕 ¡Cambio detectado en Gaceta {year}! Extrayendo PDFs...")

    # Extraer todos los links .pdf del HTML
    pdf_links = re.findall(r'https?://[^\s"\'<>]+\.pdf', html)
    # También buscar patrones relativos
    rel_links  = re.findall(r'href=["\']([^"\']+\.pdf)["\']', html)
    base       = CONFIG["GACETA_PDF_BASE"].format(year=year)
    for rl in rel_links:
        if rl.startswith("http"):
            pdf_links.append(rl)
        else:
            pdf_links.append(base + rl.lstrip("/"))

    pdf_links = sorted(set(pdf_links))
    log.info(f"  📄 {len(pdf_links)} PDFs encontrados")
    return pdf_links


# ─────────────────────────────────────────────────────────
# PASO 2: DISCOVER — descargar PDF, extraer IDs
# ─────────────────────────────────────────────────────────
def pid_in_csv(pid: str) -> bool:
    p = CONFIG["CSV_FILE"]
    if not p.exists():
        return False
    try:
        return pid in p.read_text()
    except Exception:
        return False

def process_pdf(pdf_url: str, year: int, queue: PersistentQueue,
                log: logging.Logger) -> int:
    filename = os.path.basename(pdf_url.split("?")[0])
    work_dir = CONFIG["WORK_DIR"] / str(year)
    work_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = work_dir / filename
    txt_path = work_dir / filename.replace(".pdf", ".txt")

    # Descargar PDF
    if not pdf_path.exists():
        report_state(filename, "DESCARGANDO", "PDF")
        log.info(f"  ⬇️  {filename}")
        data = http_get(pdf_url, timeout=90, binary=True)
        if data is None:
            log.warning(f"  ⚠️ Fallo descarga: {filename}")
            return 0
        pdf_path.write_bytes(data)

    # PDF → TXT
    if not txt_path.exists():
        log.info(f"  📝 pdftotext: {filename}")
        r = subprocess.run(["pdftotext", "-layout", str(pdf_path), str(txt_path)],
                           capture_output=True, timeout=90)
        if r.returncode != 0:
            log.error(f"  ❌ pdftotext falló ({r.returncode}): {filename}")
            return 0

    # Verificar que el TXT no esté vacío
    if not txt_path.exists() or txt_path.stat().st_size < 10:
        log.warning(f"  ⚠️ TXT vacío para {filename}")
        return 0

    txt = txt_path.read_text(errors="replace")
    ids = sorted(set(ID_PATTERN.findall(txt)))

    new_count = 0
    for pid in ids:
        if pid_in_csv(pid) or queue.is_done(pid):
            continue
        if queue.add(pid=pid, pdf=filename, year=year, txt_file=str(txt_path)):
            new_count += 1

    log.info(f"  🆔 {len(ids)} IDs en PDF, {new_count} nuevos en queue")
    return new_count


# ─────────────────────────────────────────────────────────
# PASO 3: EXTRACT — Qwen extrae datos del proyecto
# ─────────────────────────────────────────────────────────
EXTRACTION_PROMPT = """\
Eres un extractor de datos de proyectos de impacto ambiental de México.
Dado el siguiente texto de la Gaceta Ecológica SEMARNAT, extrae los datos del proyecto con ID: {pid}

TEXTO:
{context}

Responde ÚNICAMENTE con un objeto JSON válido con estas claves exactas:
{{"proyecto": "nombre del proyecto", "promovente": "nombre de la empresa o persona", "estado": "estado de la república", "municipio": "municipio", "riesgo": "alto|medio|bajo"}}

Si no encuentras un campo, usa cadena vacía "". No agregues texto fuera del JSON."""

def extract_with_ai(pid: str, context: str, log: logging.Logger) -> Optional[dict]:
    prompt = EXTRACTION_PROMPT.format(pid=pid, context=context[:CONFIG["CONTEXT_CHARS"]])
    payload = json.dumps({
        "model":          CONFIG["MODEL"],
        "messages":       [{"role": "user", "content": prompt}],
        "temperature":    0.0,
        "max_tokens":     CONFIG["MAX_TOKENS"],
        "repeat_penalty": 1.1,
    }).encode("utf-8")

    for attempt in range(1, CONFIG["MAX_RETRIES"] + 1):
        try:
            req = urllib.request.Request(
                CONFIG["MOTOR_URL"], data=payload,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=CONFIG["LLAMA_TIMEOUT"]) as resp:
                content = json.loads(resp.read())["choices"][0]["message"]["content"]

            # Limpiar y extraer JSON
            content = content.strip()
            # Buscar el primer bloque JSON
            m = re.search(r'\{[^{}]*\}', content, re.DOTALL)
            if m:
                extracted = json.loads(m.group(0))
                # Normalizar claves en minúscula
                extracted = {k.lower().strip(): str(v).strip()
                             for k, v in extracted.items()}
                log.debug(f"    AI ({attempt}): {extracted}")
                return extracted
            else:
                log.warning(f"    ⚠️ Sin JSON en respuesta ({attempt}/{CONFIG['MAX_RETRIES']}): {content[:100]}")

        except urllib.error.URLError as e:
            log.warning(f"    ⚠️ URLError ({attempt}): {e.reason}")
        except (json.JSONDecodeError, KeyError) as e:
            log.warning(f"    ⚠️ Parse error ({attempt}): {e}")
        except Exception as e:
            log.warning(f"    ⚠️ Error ({attempt}): {e}")

        if attempt < CONFIG["MAX_RETRIES"]:
            wait = CONFIG["RETRY_BASE_WAIT"] * (2 ** (attempt - 1))
            log.info(f"    ⏳ Retry en {wait}s...")
            time.sleep(wait)

    return None


# ─────────────────────────────────────────────────────────
# CSV y GRAFO
# ─────────────────────────────────────────────────────────
def write_to_csv(year: int, pid: str, d: dict):
    """Escribe una fila al CSV de producción. Seguro ante comas."""
    def clean(v): return re.sub(r'[,\n\r]', ' ', str(d.get(v, ""))).strip()
    row = [str(year), pid,
           clean("estado"), clean("municipio"),
           clean("proyecto"), clean("promovente"),
           clean("riesgo") or "bajo"]
    with open(CONFIG["CSV_FILE"], "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(row)

def write_to_graph(pid: str, d: dict):
    lines = []
    if p := d.get("promovente", "").strip():
        lines.append(f"({pid})-[PROMOVIDO_POR]->({p})")
    if s := d.get("estado", "").strip():
        lines.append(f"({pid})-[ESTADO]->({s})")
    if m := d.get("municipio", "").strip():
        lines.append(f"({pid})-[MUNICIPIO]->({m})")
    if lines:
        with open(CONFIG["GRAPH_FILE"], "a") as f:
            f.write("\n".join(lines) + "\n")


# ─────────────────────────────────────────────────────────
# PASO 4: FETCH — Portal SEMARNAT, descarga de documentos
# ─────────────────────────────────────────────────────────
def fetch_portal_docs(pid: str, log: logging.Logger) -> dict:
    """
    Consulta la API del portal SEMARNAT para obtener metadatos
    y rutas de documentos asociados al proyecto.

    La API no requiere autenticación para metadatos básicos.
    Retorna dict con claves: bitacora, titulo, documentos[]
    """
    # Endpoint público de metadatos del proyecto
    api_url = CONFIG["PORTAL_API_BASE"] + urllib.parse.quote(pid)

    log.info(f"  🌐 Portal: consultando {pid}")
    content = http_get(api_url, timeout=30)
    if content is None:
        log.warning(f"  ⚠️ Portal no respondió para {pid}")
        return {}

    try:
        data = json.loads(content)
        return data
    except json.JSONDecodeError:
        log.debug(f"  ⚠️ Portal: respuesta no JSON para {pid}")
        return {}

def download_document(pid: str, doc_url: str, doc_type: str, log: logging.Logger) -> Optional[Path]:
    """
    Descarga un documento (estudio, resumen, resolutivo) del portal.
    Guarda en DOCS_DIR/{pid}/{doc_type}.pdf
    """
    save_dir = CONFIG["DOCS_DIR"] / pid
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / f"{doc_type}.pdf"

    if save_path.exists():
        log.info(f"  📁 Ya existe: {save_path.name}")
        return save_path

    log.info(f"  ⬇️  Descargando {doc_type} para {pid}...")
    data = http_get(doc_url, timeout=120, binary=True)
    if data and data[:4] == b'%PDF':
        save_path.write_bytes(data)
        log.info(f"  ✅ Guardado: {save_path}")
        return save_path
    else:
        log.warning(f"  ⚠️ Respuesta inválida para {doc_type} ({pid})")
        return None


# ─────────────────────────────────────────────────────────
# LOOP DE EXTRACCIÓN (procesa la queue pendiente)
# ─────────────────────────────────────────────────────────
def run_extraction(queue: PersistentQueue, log: logging.Logger):
    pending = queue.pending()
    if not pending:
        log.info("📋 Queue vacía")
        return

    log.info(f"🚀 Extrayendo {len(pending)} IDs pendientes...")

    for item in pending:
        if _shutdown:
            break

        if not wait_for_llama(log, max_wait=60):
            log.error("🛑 llama-server inaccesible — abortando ciclo")
            break

        txt_path = Path(item.txt_file)
        if not txt_path.exists():
            queue.mark_attempt(item.pid, error="txt_missing")
            continue

        txt = txt_path.read_text(errors="replace")

        # Ventana de contexto centrada en el ID
        idx = txt.find(item.pid)
        if idx == -1:
            queue.mark_attempt(item.pid, error="id_not_in_txt")
            continue

        half = CONFIG["CONTEXT_CHARS"] // 2
        context = txt[max(0, idx - half): idx + half]
        context = re.sub(r'\s+', ' ', context).strip()

        report_state(item.pdf, "IA_EXTRACTING", item.pid)
        log.info(f"  🇲🇽 [{item.attempts + 1}/{CONFIG['MAX_RETRIES']}] {item.pid}")

        extracted = extract_with_ai(item.pid, context, log)

        if extracted:
            promovente = extracted.get("promovente", "").strip()
            if promovente and promovente.lower() not in ("", "null", "n/a", "desconocido"):
                if not CONFIG["DRY_RUN"]:
                    write_to_csv(item.year, item.pid, extracted)
                    write_to_graph(item.pid, extracted)
                    # Intentar descargar documentos del portal
                    portal_data = fetch_portal_docs(item.pid, log)
                    if portal_data:
                        _process_portal_docs(item.pid, portal_data, log)

                queue.mark_success(item.pid)
                st = queue.stats()
                log_extra(log, logging.INFO,
                          f"  ✅ {item.pid} → {promovente[:50]}  "
                          f"[OK:{st['success']} P:{st['pending']} F:{st['failed']}]",
                          pid=item.pid, promovente=promovente)
            else:
                queue.mark_attempt(item.pid, error="empty_promovente")
                log.warning(f"  ⚠️ Promovente vacío para {item.pid}")
        else:
            queue.mark_attempt(item.pid, error="ai_no_json")
            log.warning(f"  ❌ Extracción fallida: {item.pid}")

        thermal_wait(log)

    st = queue.stats()
    report_state("IDLE", "STANDBY", "NONE")
    log.info(f"✅ Ciclo OK — Total:{st['total']} OK:{st['success']} Pend:{st['pending']} Fail:{st['failed']}")


def _process_portal_docs(pid: str, portal_data: dict, log: logging.Logger):
    """Descarga documentos disponibles (resumen, estudio, resolutivo)."""
    # La API devuelve una lista de archivos bajo distintas claves
    doc_map = {
        "resumen":    ["resumen", "resumenEjecutivo", "summary"],
        "estudio":    ["estudio", "estudioImpacto", "eia"],
        "resolutivo": ["resolutivo", "resolucion", "resolution"],
    }
    docs = portal_data.get("documentos", portal_data.get("archivos", []))
    if not isinstance(docs, list):
        return

    for doc in docs:
        url  = doc.get("url") or doc.get("ruta") or doc.get("path", "")
        name = (doc.get("tipo") or doc.get("name") or "").lower()
        if not url:
            continue
        for doc_type, keys in doc_map.items():
            if any(k in name for k in keys):
                download_document(pid, url, doc_type, log)
                break


# ─────────────────────────────────────────────────────────
# GRACEFUL SHUTDOWN
# ─────────────────────────────────────────────────────────
_shutdown = False

def _handle_signal(sig, _frame):
    global _shutdown
    print("\n🛑 Señal recibida — guardando estado...")
    _shutdown = True

signal.signal(signal.SIGINT,  _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


# ─────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────
def main():
    log   = setup_logging(CONFIG["LOG_FILE"])
    queue = PersistentQueue(CONFIG["QUEUE_FILE"])
    seen  = SeenGacetas(CONFIG["SEEN_FILE"])
    year  = CONFIG["YEAR"]

    log.info("═" * 58)
    log.info(f"  ZOHAR AGENT v2.1  |  Año:{year}  |  DRY_RUN:{CONFIG['DRY_RUN']}")
    st = queue.stats()
    log.info(f"  Queue: {st}")
    log.info("═" * 58)

    CONFIG["DOCS_DIR"].mkdir(parents=True, exist_ok=True)

    def run_cycle():
        # 1. Monitorear gaceta y descubrir PDFs
        pdf_links = fetch_pdf_links(year, seen, log)
        total_new = 0
        for url in pdf_links:
            if _shutdown:
                break
            n = process_pdf(url, year, queue, log)
            total_new += n
        if pdf_links:
            log.info(f"📥 {total_new} IDs nuevos agregados a la queue")

        # 2. Extraer con IA
        if not _shutdown:
            run_extraction(queue, log)

    if CONFIG["DAEMON_MODE"]:
        poll_s = CONFIG["POLL_INTERVAL_MIN"] * 60
        log.info(f"⏰ Modo daemon — polling cada {CONFIG['POLL_INTERVAL_MIN']} min")
        while not _shutdown:
            run_cycle()
            if not _shutdown:
                log.info(f"😴 Durmiendo {CONFIG['POLL_INTERVAL_MIN']} min...")
                for _ in range(poll_s):
                    if _shutdown:
                        break
                    time.sleep(1)
    else:
        run_cycle()

    log.info("👋 Agente detenido correctamente.")


if __name__ == "__main__":
    main()
