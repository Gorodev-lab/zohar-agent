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

import os, re, json, csv, time, signal, logging, datetime, sys
import subprocess, urllib.request, urllib.error, urllib.parse
import hashlib
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional

try:
    import pandas as pd
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    pass

# ─────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────────────────
HOME = Path.home()
AGENT_DIR = Path(__file__).resolve().parent

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
    "MAX_TOKENS":        600,        # Suficiente para descripción técnica y razonamiento CoT
    "TEMPERATURE":       0.1,
    "CONTEXT_CHARS":     3200,     # Proporcionar más fragmento a la IA

    # Ciclo de monitoreo
    "POLL_INTERVAL_MIN": 30,      # minutos entre chequeos de nuevas gacetas
    "YEARS":             list(range(2005, 2027)), # Barrido completo por defecto
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
    URLs de PDF usando Selenium y Pandas para garantizar recolección.
    """
    url = CONFIG["GACETA_LIST_URL"].format(year=year)
    report_state("—", "MONITOREANDO", f"Gaceta {year} (Selenium)")
    log.info(f"🔍 Verificando Gaceta {year} con Webdriver: {url}")

    html = ""
    try:
        # Configurar Selenium Chromium Headless
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.binary_location = '/usr/bin/google-chrome-stable'
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(60)
        driver.get(url)
        time.sleep(3) # Esperar a que renderice JS
        html = driver.page_source
        driver.quit()
    except Exception as e:
        log.warning(f"⚠️ Fallo en Selenium, usando fallback HTTP: {e}")
        html = http_get(url, timeout=60)
        if html is None:
            log.warning(f"  ⚠️ No se pudo acceder a la Gaceta {year}")
            return []

    if html is None or html == "":
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

    # FALLBACK si Selenium no pudo cargar los links por protecciones anti-bot
    if len(pdf_links) == 0:
        log.warning(f"⚠️ Selenium no encontró PDFs. Intentando con request HTTP directo...")
        html_fb = http_get(url, timeout=60)
        if html_fb:
            pdf_links = re.findall(r'https?://[^\s"\'<>]+\.pdf', html_fb)
            rel_links  = re.findall(r'href=["\']([^"\']+\.pdf)["\']', html_fb)
            for rl in rel_links:
                if rl.startswith("http"):
                    pdf_links.append(rl)
                else:
                    pdf_links.append(base + rl.lstrip("/"))

    # Usar pandas para la deduplicación y limpieza, asegurando que la info está "aterrizada"
    try:
        df = pd.DataFrame({"url": pdf_links})
        df = df.drop_duplicates().reset_index(drop=True)
        pdf_links = df["url"].tolist()
    except Exception:
        pdf_links = sorted(set(pdf_links))

    pdf_links = sorted(set(pdf_links)) # doble check
    log.info(f"  📄 {len(pdf_links)} PDFs encontrados usando métodos avanzados.")
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
# Mapeo de Claves de Estado SEMARNAT (01-32)
STATE_CODES = {
    "01": "AGUASCALIENTES", "02": "BAJA CALIFORNIA", "03": "BAJA CALIFORNIA SUR",
    "04": "CAMPECHE", "05": "COAHUILA", "06": "COLIMA", "07": "CHIAPAS",
    "08": "CHIHUAHUA", "09": "CIUDAD DE MÉXICO", "10": "DURANGO",
    "11": "GUANAJUATO", "12": "GUERRERO", "13": "HIDALGO", "14": "JALISCO",
    "15": "MÉXICO", "16": "MICHOACÁN", "17": "MORELOS", "18": "NAYARIT",
    "19": "NUEVO LEÓN", "20": "OAXACA", "21": "PUEBLA", "22": "QUERÉTARO",
    "23": "QUINTANA ROO", "24": "SAN LUIS POTOSÍ", "25": "SINALOA",
    "26": "SONORA", "27": "TABASCO", "28": "TAMAULIPAS", "29": "TLAXCALA",
    "30": "VERACRUZ", "31": "YUCATÁN", "32": "ZACATECAS"
}

def normalize_extracted_data(pid: str, data: dict) -> dict:
    """Normaliza y corrige nombres de estados y municipios, limpiando ruido tabular."""
    # 1. Extraer datos crudos y normalizar claves
    data = {k.lower().strip(): v for k, v in data.items()}
    
    raw_state = str(data.get("estado", "")).upper().strip()
    raw_mun   = str(data.get("municipio", "")).upper().strip()
    raw_proj  = str(data.get("proyecto", "")).upper().strip()
    raw_prom  = str(data.get("promovente", "")).upper().strip()
    
    # 2. Forzar Estado correcto según los 2 primeros dígitos del PID (Standard SEMARNAT)
    state_code = pid[:2]
    if state_code in STATE_CODES:
        data["estado"] = STATE_CODES[state_code]
    
    # 3. Limpieza de ruido tabular agresiva (Headers que se filtran)
    # Lista de sub-strings que indican que el valor extraído es un encabezado de tabla, no un dato.
    noise_terms = [
        "EL ID", "ID_PROYECTO", "ID PROYECTO", "CLAVE", "MODALIDAD", "FECHA", 
        "INGRESO", "PROMOVENTE", "PROYECTO", "ESTADO", "MUNICIPIO", "NUMERO",
        "DETALLES", "BITACORA", "REGISTRO", "PUBLICACION"
    ]
    
    def is_noise(text: str) -> bool:
        text_up = text.upper()
        # Si el texto es idéntico a un header o contiene demasiados términos de header
        if text_up in noise_terms: return True
        # Si la longitud es mínima
        if len(text_up.replace(" ", "")) <= 2: return True
        # Detección de "EL ID" con regex
        if re.search(r'^(EL\s+)?ID(_PROYECTO)?$', text_up): return True
        return False

    # Limpiar Municipio
    if is_noise(raw_mun):
        data["municipio"] = ""
    else:
        # Corregir municipios con prefijos
        prefixes = ["LOS", "LA", "EL", "LAS", "SAN", "SANTA", "SANTO", "VALLE DE", "DE"]
        mun = raw_mun
        if raw_state in prefixes and mun and not mun.startswith(raw_state):
            mun = f"{raw_state} {mun}"
        
        # Correcciones específicas comunes
        corrections = {
            "CABOS": "LOS CABOS", "PAZ": "LA PAZ", "BRAVO": "VALLE DE BRAVO",
            "ANDRÉS": "SAN ANDRÉS", "PEDRO": "SAN PEDRO", "CRISTÓBAL": "SAN CRISTÓVAL",
            "DEL CARMEN": "PLAYA DEL CARMEN"
        }
        for k, v in corrections.items():
            if mun == k: mun = v
            
        data["municipio"] = mun

    # Limpiar Proyecto (Si parece un encabezado de tabla, usar la descripción o marcar como error)
    if is_noise(raw_proj) or any(term in raw_proj for term in ["PROMOVENTE", "FECHA DE INGRESO"]):
        data["proyecto"] = "PROYECTO EN EVALUACIÓN"
    
    # Limpiar Promovente
    if is_noise(raw_prom):
        data["promovente"] = "DESCONOCIDO"
    
    # Si la descripción es genérica, basura o muy corta, usar el título del proyecto
    desc = str(data.get("descripcion", "")).strip()
    # Si la IA devuelve algo muy corto o con puntos suspensivos, es un fallo
    if not desc or len(desc) < 20 or desc == "..." or "AUTOMÁTICA" in desc.upper():
        proj_title = str(data.get("proyecto", ""))
        if len(proj_title) > 30:
             data["descripcion"] = f"Análisis técnico: {proj_title[:150]}..."
        else:
             data["descripcion"] = f"Evaluación de Manifestación de Impacto Ambiental para el proyecto en {data.get('estado')}"
             
    # LOG DE SEGURIDAD
    # log.debug(f"      Normalized {pid}: Mun='{data['municipio']}' Desc='{data['descripcion'][:30]}...'")
    
    # 4. Limpieza general
    for k in data:
        if isinstance(data[k], str):
            val = data[k]
            # Eliminar "PROMOVIDO POR...", "ESTADO DE...", y ruidos de metadatos
            val = re.sub(r'(?i)PROMOVIDO POR.*', '', val)
            val = re.sub(r'(?i)ESTADO DE\s+', '', val)
            val = re.sub(r'(?i)MUNICIPIO DE\s+', '', val)
            # Limpiar espacios múltiples y mayúsculas (excepto descripción que es mixta)
            val = re.sub(r'\s+', ' ', val).strip()
            if k != "descripcion":
                val = val.upper()
            data[k] = val
    
    return data

EXTRACTION_PROMPT = """\
<system_instruction>
Eres un investigador experto de nivel doctoral especializado en ingeniería de datos estructurados, procesamiento avanzado de lenguaje natural (NLP) y análisis forense de documentos gubernamentales mexicanos (específicamente la Gaceta Ecológica y Manifestaciones de Impacto Ambiental de SEMARNAT). 

Tu tarea crítica y exclusiva es extraer información estructurada y prístina a partir de texto crudo, severamente ruidoso y desestructurado, proveniente de PDFs escaneados (OCR) que sufren de degradación topológica y tablas rotas.

Debes aplicar un rigor analítico metodológico extremo para diferenciar categóricamente entre "Metadatos/Encabezados de Tabla rotos" y "Valores de Datos Reales de Proyectos". Eres totalmente inmune a las trampas de proximidad espacial en el texto.
</system_instruction>

<schema_definition>
Debes extraer la información requerida del texto y poblar de manera estricta el siguiente esquema de salida JSON. No inventes campos nuevos.
{{
  "PROMOVENTE": "El nombre corporativo de la empresa, persona física o entidad gubernamental que propone y financia el proyecto ambiental.",
  "PROYECTO": "El nombre formal y oficial del proyecto tal y como está registrado en el documento.",
  "ESTADO": "El nombre oficial y normativo de la entidad federativa de México (Ej. CAMPECHE, SONORA, BAJA CALIFORNIA SUR). NUNCA uses abreviaturas ni artículos sueltos erróneos como 'EL' o 'LA'.",
  "MUNICIPIO": "El nombre oficial del municipio correspondiente. Debe existir y tener coherencia geográfica comprobada con el ESTADO asignado.",
  "RIESGO": "Nivel de impacto ambiental detectado (bajo, medio, alto).",
  "DESCRIPCION": "Un resumen técnico y analítico de las características de la obra. NUNCA debe ser igual al nombre del proyecto ni quedar vacío."
}}
</schema_definition>

<extraction_rules>
Para garantizar una extracción de datos de altísima fidelidad, debes interiorizar y obedecer estrictamente las siguientes reglas procedimentales inviolables:

1. EVASIÓN ABSOLUTA DE RUIDO Y ENCABEZADOS (RESOLUCIÓN DEL PROBLEMA "EL ID"):
   - El texto fuente de entrada proviene de tablas PDF que han sido aplanadas a texto plano. Por consiguiente, encabezados de columna como "EL ID", "ID_PROYECTO", "CLAVE", "MODALIDAD", o "FECHA DE INGRESO" aparecerán caóticamente mezclados con los datos reales de los proyectos.
   - REGLA CRÍTICA DE RECHAZO: "EL ID" NO ES BAJO NINGUNA CIRCUNSTANCIA UN MUNICIPIO O ESTADO MEXICANO. "ID_PROYECTO" NO ES UN MUNICIPIO. Si tus sensores de lectura detectan estas combinaciones de palabras cerca de etiquetas geográficas, ignóralas por completo al buscar ubicaciones. Son, sin excepción, basura estructural resultante del OCR.

2. PROTOCOLO DE VALIDACIÓN SEMÁNTICA GEOGRÁFICA (TAXONOMÍA INEGI):
   - Los valores asignados a los campos ESTADO y MUNICIPIO deben existir factual y normativamente en la geografía física mexicana y en el Catálogo de Claves de Entidades Federativas y Municipios del INEGI.
   - Si extraes "EL" o iniciales aisladas como estado, se considerará un error fatal de procesamiento. Un estado legítimo es "CAMPECHE", "YUCATÁN", "JALISCO", etc.
   - Validación cruzada interna obligatoria: Pregúntate internamente, ¿El municipio que estoy a punto de extraer realmente pertenece al estado que he extraído? (Ej. Si el estado es Sonora, el municipio no puede ser Cozumel). Si hay una incongruencia, el texto está roto; debes seguir buscando en el contexto más amplio la alineación geográfica correcta.

3. INGENIERÍA Y SÍNTESIS DE LA DESCRIPCIÓN MEDIANTE VERBOS DE ACCIÓN (ABSTRACTIVE SUMMARIZATION):
   - El campo DESCRIPCION no puede ser bajo ninguna circunstancia simplemente una reiteración perezosa del nombre del proyecto. Está estrictamente prohibido que quede vacío o se complete con un guion ("—").
   - DEBE comenzar siempre y de manera obligatoria con un sustantivo o gerundio derivado de un verbo de acción técnica e ingenieril (Ej: "Construcción...", "Operación y mantenimiento de...", "Ampliación de la infraestructura de...", "Instalación de...", "Aprovechamiento forestal sustentable para...").
   - Tienes el mandato de leer profundamente los párrafos adyacentes al título para extraer detalles y parámetros técnicos valiosos (superficie de afectación en hectáreas, tipo específico de infraestructura, capacidad operativa de las plantas, voltajes, etc.) y sintetizar todo este conocimiento en un bloque narrativo conciso de 2 a 3 oraciones completas.
</extraction_rules>

<contrastive_examples>
  <negative_example_anti_pattern>
    <texto_crudo_simulado>
    NUMERO 04 EL ID 02BC2024HD010 ESTADO QUINTANA ROO PROYECTO TREN MAYA TRAMO 5 SUR MUNICIPIO EL ID PROMOVENTE FONDO NACIONAL DE FOMENTO AL TURISMO DESCRIPCION TREN MAYA TRAMO 5 SUR INGRESO A EVALUACION EL DIA
    </texto_crudo_simulado>
    <error_analysis_and_correction>
    1. Error Geográfico: Extraer "EL ID" como municipio es un fallo crítico. 
    2. Error Descriptivo: Repetir el título es inaceptable.
    </error_analysis_and_correction>
  </negative_example_anti_pattern>

  <positive_example_correct_extraction>
    <texto_crudo_simulado>
    TRAMITE NUMERO 04 EL ID 23QR2023TD099 ESTADO QUINTANA ROO PROYECTO DESARROLLO TURISTICO ESMERALDA MUNICIPIO SOLIDARIDAD PROMOVENTE INMOBILIARIA CARIBE S.A. DE C.V. El proyecto busca el cambio de uso de suelo en 15.4 hectáreas para un complejo hotelero de 400 habitaciones.
    </texto_crudo_simulado>
    <output_json>
    {{
      "PROMOVENTE": "INMOBILIARIA CARIBE S.A. DE C.V.",
      "PROYECTO": "DESARROLLO TURISTICO ESMERALDA",
      "ESTADO": "QUINTANA ROO",
      "MUNICIPIO": "SOLIDARIDAD",
      "RIESGO": "alto",
      "DESCRIPCION": "Construcción de un complejo hotelero con capacidad para 400 habitaciones, el cual requiere autorizaciones para el cambio de uso de suelo en terrenos forestales abarcando una superficie de 15.4 hectáreas."
    }}
    </output_json>
  </positive_example_correct_extraction>
</contrastive_examples>

<execution_instructions>
Paso 1: Genera el bloque <razonamiento> analizando el contexto del proyecto {pid}.
Paso 2: Genera el bloque <output_json> estrictamente con el esquema definido.
</execution_instructions>

<texto_gaceta_crudo>
{context}
</texto_gaceta_crudo>
"""



def extract_with_ai(pid: str, context: str, log: logging.Logger) -> Optional[dict]:
    prompt = EXTRACTION_PROMPT.format(pid=pid, context=context[:CONFIG["CONTEXT_CHARS"]])
    payload = json.dumps({
        "model":          CONFIG["MODEL"],
        "messages":       [{"role": "user", "content": prompt}],
        "temperature":    CONFIG["TEMPERATURE"],
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

            # Loguear razonamiento si existe
            razonamiento = re.search(r'<razonamiento>(.*?)</razonamiento>', content, re.DOTALL)
            if razonamiento:
                log.debug(f"    🧠 Razonamiento AI {pid}: {razonamiento.group(1).strip()[:200]}...")

            # Buscar el bloque JSON dentro de <output_json> o simplemente el primer { }
            json_match = re.search(r'<output_json>(.*?)</output_json>', content, re.DOTALL)
            if not json_match:
                json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(1) if '<output_json>' in content else json_match.group(0)
                extracted = json.loads(json_str)
                log.info(f"  🤖 AI Resp {pid}: {extracted}")
                # Normalizar claves en minúscula
                extracted = {k.lower().strip(): str(v).strip()
                             for k, v in extracted.items()}
                
                # Normalización de riesgos (Nueva regla de negocio)
                if extracted.get("riesgo") == "crítico":
                    extracted["riesgo"] = "alto"
                
                log.debug(f"    AI ({attempt}): {extracted}")
                return extracted
            else:
                log.warning(f"    ⚠️ Sin JSON en respuesta ({attempt}/{CONFIG['MAX_RETRIES']}): {content[:100]}")
                # Fallback si la IA no produce JSON válido
                return {
                    "proyecto": "EXTRACCIÓN AUTOMÁTICA",
                    "promovente": "DESCONOCIDO",
                    "estado": "",
                    "municipio": "",
                    "riesgo": "bajo",
                    "descripcion": "Extracción automática (AI falló o sin contexto corregido)"
                }

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
    """Escribe una fila al CSV de producción si no existe el PID."""
    if pid_in_csv(pid):
        return
    def clean(v): return re.sub(r'[,\n\r]', ' ', str(d.get(v, ""))).strip()
    row = [str(year), pid,
           clean("estado"), clean("municipio"),
           clean("proyecto"), clean("promovente"),
           clean("riesgo") or "bajo",
           clean("descripcion")]
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
            extracted = normalize_extracted_data(item.pid, extracted)
            promovente = extracted.get("promovente", "").strip()
            
            # La descripción ya viene normalizada de normalize_extracted_data

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
            # Fallback a metadatos del portal si la IA falla completamente
            portal_data = fetch_portal_docs(item.pid, log)
            fallback = {
                "proyecto": portal_data.get("titulo") or portal_data.get("proyecto") or "MIA PARTICULAR (Metadata)",
                "promovente": portal_data.get("promovente", "DESCONOCIDO"),
                "estado": portal_data.get("estado", ""),
                "municipio": portal_data.get("municipio", ""),
                "riesgo": "bajo",
                "descripcion": "Extracción automática (AI falló)"
            }
            fallback = normalize_extracted_data(item.pid, fallback)
            if not CONFIG["DRY_RUN"]:
                write_to_csv(item.year, item.pid, fallback)
            queue.mark_success(item.pid)
            log.warning(f"  ⚠️ Fallback usado para {item.pid}")

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
    # Soporte para argumentos: --year 2024 o --daemon
    if "--daemon" in sys.argv:
        CONFIG["DAEMON_MODE"] = True
    if "--dry-run" in sys.argv:
        CONFIG["DRY_RUN"] = True
    
    # Si se especifica un año concreto via --year YYYY
    target_years = CONFIG["YEARS"]
    if "--year" in sys.argv:
        try:
            idx = sys.argv.index("--year")
            target_years = [int(sys.argv[idx+1])]
        except (ValueError, IndexError):
            pass

    log   = setup_logging(CONFIG["LOG_FILE"])
    queue = PersistentQueue(CONFIG["QUEUE_FILE"])
    seen  = SeenGacetas(CONFIG["SEEN_FILE"])

    log.info("═" * 58)
    log.info(f"  ZOHAR AGENT v2.2  |  Años: {target_years[0]}...{target_years[-1]}  |  DRY_RUN:{CONFIG['DRY_RUN']}")
    st = queue.stats()
    log.info(f"  Queue: {st}")
    log.info("═" * 58)

    CONFIG["DOCS_DIR"].mkdir(parents=True, exist_ok=True)

    def run_cycle():
        # Discover en todos los años seleccionados
        for year in target_years:
            if _shutdown: break
            log.info(f"🔍 Monitoreando año {year}...")
            pdf_links = fetch_pdf_links(year, seen, log)
            total_new = 0
            for url in pdf_links:
                if _shutdown: break
                n = process_pdf(url, year, queue, log)
                total_new += n
            if total_new > 0:
                log.info(f"📥 {year}: {total_new} IDs nuevos agregados")

        # Extracción de la queue global (IA)
        if not _shutdown:
            run_extraction(queue, log)

    if CONFIG["DAEMON_MODE"]:
        poll_s = CONFIG["POLL_INTERVAL_MIN"] * 60
        log.info(f"⏰ Modo daemon — polling años {target_years} cada {CONFIG['POLL_INTERVAL_MIN']} min")
        while not _shutdown:
            run_cycle()
            if not _shutdown:
                log.info(f"😴 Durmiendo {CONFIG['POLL_INTERVAL_MIN']} min...")
                for _ in range(poll_s):
                    if _shutdown: break
                    time.sleep(1)
    else:
        run_cycle()

    log.info("👋 Agente detenido correctamente.")


if __name__ == "__main__":
    main()
