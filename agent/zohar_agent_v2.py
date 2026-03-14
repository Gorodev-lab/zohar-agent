#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║  ZOHAR AGENT v2.2 — NATIONAL MONITORING PIPELINE                ║
║  Ryzen 5 Optimized · Advanced Extraction Architecture           ║
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
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from supabase import create_client, Client
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
    supabase_client = None
    if SUPABASE_URL and SUPABASE_KEY:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
except ImportError:
    supabase_client = None

try:
    import pandas as pd
    import base64
    from pdf2image import convert_from_path
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

    # Llama server (Qwen 1.5B / Mistral / Granite)
    "LLAMA_URL":    os.environ.get("LLAMA_URL", "http://127.0.0.1:8001/v1/chat/completions"),
    "LLAMA_HEALTH": os.environ.get("LLAMA_HEALTH", "http://127.0.0.1:8001/v1/models"),
    "OCR_URL":      os.environ.get("OCR_URL", "http://127.0.0.1:8002/v1/chat/completions"),
    "MODEL":        os.environ.get("ZOHAR_MODEL", "granite-3.0-8b-instruct-Q4_K_M.gguf"),
    "TEMPERATURE":  float(os.environ.get("ZOHAR_TEMP", "0.2")),
    "MAX_TOKENS":   int(os.environ.get("ZOHAR_MAX_TOKENS", "1000")),

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
    "LLAMA_TIMEOUT":     600, # Tolerancia máxima para inferencia completa
    "CONTEXT_CHARS":     6000, # Aumentar el contexto alimenta mejor el insight descriptivo

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
        try:
            tmp = self.path.with_suffix(".tmp")
            # Convertir a JSON una sola vez para eficiencia
            content = json.dumps({k: asdict(v) for k, v in self._d.items()}, 
                                indent=2, ensure_ascii=False)
            
            # Escritura robusta con sync (atómica)
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            
            # Reemplazo solo si el archivo existe
            if tmp.exists():
                tmp.replace(self.path)
            else:
                log.error(f"  ⚠️  Fallo crítico al guardar cola: {tmp} no se generó.")
        except Exception as e:
            log.error(f"  ❌ Error de I/O al guardar cola: {e}")

    def add(self, pid, pdf, year, txt_file) -> bool:
        if pid in self._d:
            return False
        self._d[pid] = QueueItem(pid=pid, pdf=pdf, year=year, txt_file=txt_file)
        self.save()
        return True

    def pending(self) -> list[QueueItem]:
        """Retorna items pendientes ordenados de forma descendente (2026 primero)."""
        items = [i for i in self._d.values()
                if i.status == "pending" and i.attempts < CONFIG["MAX_RETRIES"]]
        # Ordenar por año de mayor a menor
        return sorted(items, key=lambda x: x.year, reverse=True)

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
    """
    Verifica disponibilidad del llama-server usando /v1/models.
    NOTA: llama-cpp-python NO expone /health — usar /v1/models (200 = listo).
    """
    health = CONFIG["LLAMA_HEALTH"]  # /v1/models — compatible con llama-cpp-python
    for i in range(max_wait // 5):
        try:
            with urllib.request.urlopen(health, timeout=30) as r:
                if r.status == 200:
                    if i > 0:
                        log.info("LLM infrastructure validation successful")
                    return True
        except Exception:
            pass
        if i == 0:
            log.warning("LLM service latency detected - pending response...")
        time.sleep(5)
    log.error("LLM service unavailable (verify: curl http://127.0.0.1:8001/v1/models)")
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
    log.info(f"🔍 Verificando Gaceta {year} (HTTP First): {url}")
    html = http_get(url, timeout=60)
    
    if html is None or "document.write" in html or len(html) < 500:
        log.warning(f"  ⚠️ HTTP insuficiente o JS detectado, usando Selenium (Heavy)...")
        try:
            # Configurar Selenium Chromium Headless
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            # Configuración Robusta para Arch Linux
            chrome_options.binary_location = '/usr/bin/google-chrome-stable'
            
            # Usar binario local para evitar esperas de descarga
            driver_path = "/usr/bin/chromedriver"
            if not os.path.exists(driver_path): driver_path = "/usr/local/bin/chromedriver"
            
            service = Service(executable_path=driver_path)
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.set_page_load_timeout(45) # Reducir para evitar bloqueos
            driver.set_script_timeout(15)
            
            log.info(f"  🌐 Abriendo Gaceta {year}...")
            driver.get(url)
            time.sleep(5) # Esperar renderizado dinámico
            html = driver.page_source
            driver.quit()
        except Exception as e:
            log.warning(f"  ❌ Fallo total: no se pudo acceder a la Gaceta {year} ({e})")
            return []

    if html is None or html == "":
        return []

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
    """Busca el PID solo en la segunda columna del CSV (índice 1) para precisión."""
    p = CONFIG["CSV_FILE"]
    if not p.exists():
        return False
    try:
        # Usar set local de caché para velocidad si el archivo es grande
        # Para sistemas con 13GB RAM, leer la columna completa es trivial
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            next(reader, None) # Saltar cabecera
            for row in reader:
                if len(row) > 1 and row[1].strip() == pid.strip():
                    return True
        return False
    except Exception as e:
        log.error(f"  ⚠️ Error verificando PID en CSV: {e}")
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
    raw_loc   = str(data.get("localidad", "")).upper().strip() # Quitamos el fallback default a CABECERA MUNICIPAL
    raw_proj  = str(data.get("proyecto", "")).upper().strip()
    raw_prom  = str(data.get("promovente", "")).upper().strip()
    raw_coord = str(data.get("coordenadas", "")).strip()
    raw_poly  = str(data.get("poligono", "")).strip()
    
    # 2. Forzar Estado correcto según los 2 primeros dígitos del PID (Standard SEMARNAT)
    state_code = pid[:2]
    if state_code in STATE_CODES:
        data["estado"] = STATE_CODES[state_code]
    
    # 3. Limpieza de ruido tabular agresiva (Headers que se filtran)
    noise_terms = [
        "EL ID", "ID_PROYECTO", "ID PROYECTO", "CLAVE", "MODALIDAD", "FECHA", 
        "INGRESO", "PROMOVENTE", "PROYECTO", "ESTADO", "MUNICIPIO", "NUMERO",
        "DETALLES", "BITACORA", "REGISTRO", "PUBLICACION", "CABECERA MUNICIPAL",
        "NOMBRE ESPECIFICO", "BUSCA EL NOMBRE"
    ]
    
    def is_noise(text: str) -> bool:
        text_up = text.upper()
        if text_up in noise_terms: return True
        if len(text_up.replace(" ", "")) <= 2: return True
        # Si el texto contiene instrucciones del prompt, es basura
        if "EVITA" in text_up or "NOMBRE ESPECIFICO" in text_up: return True
        if re.search(r'^(EL\s+)?ID(_PROYECTO)?$', text_up): return True
        return False

    # Limpiar Municipio
    if is_noise(raw_mun) or raw_mun in ["GENERICO", "GENÉRICO", "NONE", "CABECERA MUNICIPAL"]:
        data["municipio"] = ""
    else:
        mun = raw_mun
        # Eliminar términos genéricos que no son nombres
        generic_terms = ["CABECERA MUNICIPAL", "MUNICIPIO", "GENERICO", "GENÉRICO", "VARIOS", "ESTADO"]
        if any(term == mun for term in generic_terms):
            mun = ""

        # En esta versión, si no hay municipio claro, se queda vacío.
        corrections = {
            "CABOS": "LOS CABOS", "PAZ": "LA PAZ", "BRAVO": "VALLE DE BRAVO",
            "ANDRÉS": "SAN ANDRÉS", "PEDRO": "SAN PEDRO", "CRISTÓBAL": "SAN CRISTÓVAL",
            "DEL CARMEN": "PLAYA DEL CARMEN", "JUÁREZ": "BENITO JUÁREZ"
        }
        for k, v in corrections.items():
            if mun == k: mun = v
            
        # Intento de rescate si está vacío: buscar en proyecto o descripción
        if not mun:
            context_text = (raw_proj + " " + str(data.get("descripcion", ""))).upper()
            m_mun = re.search(r'MUNICIPIO\s+(?:DE\s+)?([A-Z\xC0-\xDF\s]{3,30})(?:,|\.|\s+EN|$)', context_text)
            if m_mun:
                mun = m_mun.group(1).strip()

        data["municipio"] = mun
    
    # Limpiar Localidad
    if is_noise(raw_loc) or raw_loc in ["NONE", "NULL", "DESCONOCIDO", "CABECERA MUNICIPAL", ""]:
        data["localidad"] = "" # No forzar CABECERA MUNICIPAL
    else:
        data["localidad"] = raw_loc

    # Limpiar Proyecto
    if is_noise(raw_proj) or any(term in raw_proj for term in ["PROMOVENTE", "FECHA DE INGRESO"]):
        data["proyecto"] = "PROYECTO EN EVALUACIÓN"
    
    # Limpiar Promovente
    if is_noise(raw_prom) or "NOMBRE LEGAL" in raw_prom.upper():
        data["promovente"] = "DESCONOCIDO"
    else:
        data["promovente"] = raw_prom

    # Limpiar Coordenadas y Polígono
    if is_noise(raw_coord) or raw_coord.upper() in ["NONE", "NULL", "DESCONOCIDO"]:
        data["coordenadas"] = ""
    else:
        data["coordenadas"] = raw_coord

    if is_noise(raw_poly) or raw_poly.upper() in ["NONE", "NULL", "DESCONOCIDO"]:
        data["poligono"] = ""
    else:
        data["poligono"] = raw_poly
    
    # Si la descripción (insight) es genérica, basura o muy corta, usar el título del proyecto
    desc = str(data.get("insight", data.get("descripcion", ""))).strip()
    # Si la IA devuelve algo muy corto o con instrucciones del prompt
    is_placeholder = any(x in desc.upper() for x in ["EXTRACCIÓN AUTOMÁTICA", "SIN DETALLES", "FALLÓ", "ULTRA PRECIS"])
    if not desc or len(desc) < 30 or desc == "..." or is_placeholder or "MIGRADO" in desc.upper():
        proj_title = str(data.get("proyecto", ""))
        state_name = data.get("estado", "MÉXICO")
        if len(proj_title) > 30:
             data["insight"] = f"Análisis técnico del proyecto: {proj_title[:150]}..."
        else:
             data["insight"] = f"Evaluación de Manifestación de Impacto Ambiental para el proyecto {proj_title} en {state_name}. Se requiere revisión manual de confidencialidad."
    else:
        data["insight"] = desc
             
    # 4. Limpieza general
    for k in data:
        if isinstance(data[k], str):
            val = data[k]
            val = re.sub(r'(?i)PROMOVIDO POR.*', '', val)
            val = re.sub(r'(?i)ESTADO DE\s+', '', val)
            val = re.sub(r'(?i)MUNICIPIO DE\s+', '', val)
            val = re.sub(r'\s+', ' ', val).strip()
            if k not in ["descripcion", "insight", "coordenadas", "poligono"]:
                val = val.upper()
            data[k] = val
    
    return data


def ground_data(extracted: dict, portal_data: dict, log: logging.Logger) -> dict:
    """
    PASO 3.5: Digital Twin Grounding (Estrategia 1).
    Aterriza y verifica la calidad usando los datos oficiales del portal SEMARNAT.
    """
    if not portal_data:
        return extracted

    # Mapeo de campos SEMARNAT API -> Zohar Schema
    grounding_map = {
        "proyecto":   ["proyecto", "titulo", "nomProyecto", "nombreProyecto"],
        "promovente": ["promovente", "nomPromovente", "nombrePromovente"],
        "estado":     ["estado", "entidadFederativa", "nomEntidad", "nomEstado"],
        "municipio":  ["municipio", "nomMunicipio", "nombreMunicipio", "ubicacionMunicipio"]
    }

    for target, portal_keys in grounding_map.items():
        official_val = None
        for k in portal_keys:
            if val := portal_data.get(k):
                official_val = str(val).strip()
                if official_val.upper() not in ["DESCONOCIDO", "", "NULL", "NONE"]:
                    break
                official_val = None
        
        if official_val:
            ai_val = str(extracted.get(target) or "").strip()
            # Si hay discrepancia o la IA cortó la palabra, preferimos el portal
            if (ai_val.upper() != official_val.upper()) or (len(official_val) > len(ai_val) and len(ai_val) < 10):
                if len(ai_val) > 3:
                    log.debug(f"    🔗 Grounding {target}: '{ai_val}' -> '{official_val}'")
                extracted[target] = official_val
    
    return extracted

# Prompt Chaining - Paso 1: Ubicar contexto específico de ubicación
LOCATION_FINDER_PROMPT = """\
<instruction>
Eres un perito experto en lectura de gacetas SEMARNAT. Tu objetivo es encontrar el fragmento exacto que describe la ubicación de un proyecto.
</instruction>

<task>
Busca en el texto el proyecto con ID {pid}. 
Extrae ÚNICAMENTE el fragmento de texto (oración o tabla) donde se menciona el ESTADO y el MUNICIPIO o LOCALIDAD de este proyecto específico.
</task>

<context>
{context}
</context>

Si no encuentras el municipio pero sí el estado, copia el fragmento del estado.
Responde SOLAMENTE con el fragmento hallado. Si no hay nada claro, responde "NO_HALLADO".
"""

# Prompt Chaining - Paso 2: Extracción estructurada avanzada (Meta-Prompt Arquitectura v3.0)
EXTRACTION_PROMPT = """\
<system_instruction>
Eres un Investigador Senior de la SEMARNAT y Data Scientist experto en ingeniería de datos y análisis forense de documentos gubernamentales. 
Tu tarea es extraer información prístina de texto extremadamente ruidoso (OCR degradado).
Eres totalmente inmune a las trampas de proximidad espacial como la anomalía "EL ID" y detectas encabezados rotos como basura estructural.
</system_instruction>

<schema_definition>
{
  "PROMOVENTE": "Nombre legal exacto de la empresa o entidad.",
  "PROYECTO": "Nombre oficial del proyecto.",
  "ESTADO": "Entidad federativa (INEGI). NUNCA uses abreviaturas.",
  "MUNICIPIO": "Nombre específico del municipio (DÉJALO VACÍO si no aparece el nombre propio).",
  "LOCALIDAD": "Localidad o sitio específico (o vacío).",
  "COORDENADAS": "Lat/Lon precisely si aparecen.",
  "POLIGONO": "Vértices/Geometría si aparece.",
  "SECTOR": "Uno de: [ENERGÍA, MINERÍA, TURISMO, INFRAESTRUCTURA, HIDROCARBUROS, AGROINDUSTRIA, OTROS].",
  "INSIGHT": "Resumen técnico de 2-3 oraciones iniciando OBLIGATORIAMENTE con un VERBO DE ACCIÓN (Ej: Construcción, Operación, Modernización...)."
}
</schema_definition>

<extraction_rules>
1. EVASIÓN DEL RUIDO "EL ID": "EL ID" NO ES UN MUNICIPIO. Ignora etiquetas de encabezado.
2. VALIDACIÓN GEOGRÁFICA: El MUNICIPIO debe existir y coincidir con el ESTADO.
3. VERBOS DE ACCIÓN: El INSIGHT debe describir el 'qué' técnico, no solo repetir el título.
</extraction_rules>

<contrastive_examples>
  <negative_example_anti_pattern>
    <texto_crudo_simulado>
    NUMERO 04 EL ID 02BC2024HD010 ESTADO QUINTANA ROO PROYECTO TREN MAYA TRAMO 5 MUNICIPIO EL ID PROMOVENTE FONATUR
    </texto_crudo_simulado>
    <error_analysis>
    El modelo fallaría al extraer "EL ID" como municipio por proximidad. "EL ID" es basura de tabla.
    </error_analysis>
  </negative_example_anti_pattern>

  <positive_example_correct_extraction>
    <texto_crudo_simulado>
    TRAMITE NUMERO 04 EL ID 23QR2023TD099 ESTADO QUINTANA ROO PROYECTO DESARROLLO TURISTICO ESMERALDA MUNICIPIO SOLIDARIDAD PROMOVENTE INMOBILIARIA CARIBE S.A. DE C.V. 
    El proyecto contempla el cambio de uso de suelo para un desarrollo hotelero de 400 habitaciones en 15 hectáreas.
    </texto_crudo_simulado>
    <razonamiento>
    Identifiqué "EL ID" como ruido. Ubiqué "QUINTANA ROO" como estado y validé que "SOLIDARIDAD" es un municipio válido en ese estado. El insight inicia con el verbo "Construcción".
    </razonamiento>
    <output_json>
    {
      "PROMOVENTE": "INMOBILIARIA CARIBE S.A. DE C.V.",
      "PROYECTO": "DESARROLLO TURISTICO ESMERALDA",
      "ESTADO": "QUINTANA ROO",
      "MUNICIPIO": "SOLIDARIDAD",
      "LOCALIDAD": "PLAYA DEL CARMEN",
      "SECTOR": "TURISMO",
      "INSIGHT": "Construcción de un desarrollo hotelero de 400 habitaciones que requiere el cambio de uso de suelo en 15 hectáreas de vegetación forestal."
    }
    </output_json>
  </positive_example_correct_extraction>
</contrastive_examples>

<location_context_snippet>
{location_snippet}
</location_context_snippet>

<full_text_context>
{context}
</full_text_context>

INSTRUCCIÓN FINAL:
Genera primero un bloque <razonamiento> y luego ESTRÍCTAMENTE un bloque <output_json>.
SI NO ENCUENTRAS EL MUNICIPIO REAL, DEJA EL CAMPO "MUNICIPIO" VACÍO ("").
"""




def extract_with_ai(pid: str, context: str, log: logging.Logger, pdf_name: str = "—") -> Optional[dict]:
    """
    Implementa Prompt Chaining para extraer datos con precisión:
    Paso 1: Localizar el fragmento de ubicación relevante.
    Paso 2: Realizar la extracción técnica completa usando el fragmento localizado.
    """
    
    # --- PASO 1 del CHAIN: Localizar el snippet de ubicación ---
    find_payload = json.dumps({
        "model": CONFIG["MODEL"],
        "messages": [{"role": "user", "content": LOCATION_FINDER_PROMPT.format(pid=pid, context=context[:2000])}],
        "temperature": 0.0,
        "max_tokens": 150
    }).encode("utf-8")
    
    location_snippet = "No se halló snippet específico"
    try:
        req = urllib.request.Request(CONFIG["LLAMA_URL"], data=find_payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=CONFIG["LLAMA_TIMEOUT"]) as resp:
            location_snippet = json.loads(resp.read())["choices"][0]["message"]["content"].strip()
            log.debug(f"    Locality Context Signal {pid}: {location_snippet[:100]}...")
    except Exception as e:
        log.warning(f"    Inference Sequence Stage 1 Failure for {pid}: {e}")

    # --- PASO 2 del CHAIN: Extracción Estructurada ---
    prompt = EXTRACTION_PROMPT.format(
        pid=pid, 
        location_snippet=location_snippet,
        context=context[:CONFIG["CONTEXT_CHARS"]]
    )
    
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
                CONFIG["LLAMA_URL"], data=payload,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=CONFIG["LLAMA_TIMEOUT"]) as resp:
                content = json.loads(resp.read())["choices"][0]["message"]["content"]

            # Loguear razonamiento
            razonamiento = re.search(r'<(think|razonamiento)>(.*?)</\1>', content, re.DOTALL | re.IGNORECASE)
            if razonamiento:
                thought = razonamiento.group(2).strip()
                log.debug(f"    Heuristic Rationale {pid}: {thought[:200]}...")
                report_state(pdf_name, "IA_THINKING", f"[{pid}] {thought[:180]}...")

            json_match = re.search(r'<output_json>(.*?)</output_json>', content, re.DOTALL)
            if not json_match:
                json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(1) if '<output_json>' in content else json_match.group(0)
                extracted = json.loads(json_str)
                extracted = {k.lower().strip(): str(v).strip() for k, v in extracted.items()}
                
                # Normalización de Sectores
                sector = extracted.get("sector", "OTROS").upper()
                if any(x in sector for x in ["SOLAR", "EOLICA", "ELECTRIC", "LINEA", "ENERGIA"]):
                    extracted["sector"] = "ENERGÍA"
                
                log.debug(f"    AI ({attempt}): {extracted}")
                return extracted
            else:
                log.warning(f"    Non-structured response detected ({attempt}/{CONFIG['MAX_RETRIES']})")
                return {
                    "proyecto": "EXTRACCIÓN AUTOMÁTICA", "promovente": "DESCONOCIDO",
                    "estado": "", "municipio": "", "riesgo": "bajo",
                    "descripcion": "AI falló en estructurar JSON"
                }

        except Exception as e:
            log.warning(f"    Neural extraction anomaly ({attempt}): {e}")
            if attempt < CONFIG["MAX_RETRIES"]:
                time.sleep(CONFIG["RETRY_BASE_WAIT"])

    return None



# ─────────────────────────────────────────────────────────
# CSV y GRAFO
# ─────────────────────────────────────────────────────────
def write_to_csv(year: int, pid: str, d: dict):
    """Escribe una fila al CSV de producción si no existe el PID."""
    if pid_in_csv(pid):
        return
    def clean(v): return re.sub(r'[,\n\r]', ' ', str(d.get(v, ""))).strip()
    # Nueva estructura: AÑO, ID, ESTADO, MUNICIPIO, LOCALIDAD, PROYECTO, PROMOVENTE, SECTOR, INSIGHT, COORDENADAS, POLIGONO
    row = [str(year), pid,
           clean("estado"), clean("municipio"), clean("localidad"),
           clean("proyecto"), clean("promovente"),
           clean("sector") or "OTROS",
           clean("insight"),
           clean("coordenadas"), clean("poligono")]
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

def write_to_supabase(year: int, pid: str, d: dict, log: logging.Logger):
    """Sincroniza el proyecto con Supabase."""
    if not supabase_client:
        return

    try:
        # Preparar data
        data = {
            "id_proyecto": pid,
            "anio": int(year),
            "estado": d.get("estado", ""),
            "municipio": d.get("municipio", ""),
            "localidad": d.get("localidad", ""),
            "proyecto": d.get("proyecto", ""),
            "promovente": d.get("promovente", ""),
            "sector": d.get("sector", "OTROS"),
            "insight": d.get("insight", ""),
            "coordenadas": d.get("coordenadas") or d.get("coordinates", ""),
            "poligono": d.get("poligono") or d.get("polygon", ""),
            "updated_at": datetime.datetime.now().isoformat()
        }
        
        # Upsert: insertar o actualizar por id_proyecto
        supabase_client.table("proyectos").upsert(data, on_conflict="id_proyecto").execute()
        log.debug(f"  ☁️ Cloud: {pid} sincronizado")
    except Exception as e:
        log.error(f"  ❌ Cloud Sync Error para {pid}: {e}")


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
        log.warning(f"    Remote source timeout for {pid}")
        return {}

    try:
        data = json.loads(content)
        return data
    except json.JSONDecodeError:
        log.debug(f"    Remote source: non-JSON response for {pid}")
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


def extract_with_vision(pid: str, year: int, pdf_name: str, log: logging.Logger) -> Optional[dict]:
    """Extrae datos usando Qwen2-VL (Vision) si el texto está muy roto o es ilegible."""
    try:
        work_dir = CONFIG["WORK_DIR"] / str(year)
        pdf_path = work_dir / pdf_name
        if not pdf_path.exists(): return None
        
        log.info(f"  👁️  Activando OCR Vision (Qwen2-VL) para {pid}...")
        
        # Convertir las primeras páginas (donde suelen estar las tablas)
        # Ajustamos DPI a 150 para balancear calidad y velocidad en el AMD A8
        images = convert_from_path(str(pdf_path), first_page=1, last_page=3, dpi=150)
        
        for i, img in enumerate(images):
            # Redimensionar para no saturar memoria
            img.thumbnail((1200, 1200)) 
            from io import BytesIO
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=85)
            img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            
            payload = {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"Extract project info for ID {pid} from this SEMARNAT Gaceta image. Return JSON with PROMOVENTE, PROYECTO, ESTADO, MUNICIPIO, RIESGO, DESCRIPCION."},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                        ]
                    }
                ],
                "max_tokens": 600
            }
            
            req = urllib.request.Request(CONFIG["OCR_URL"], data=json.dumps(payload).encode(),
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=180) as r:
                res = json.loads(r.read())
                content = res["choices"][0]["message"]["content"]
                
                # Extraer JSON
                m = re.search(r"\{.*\}", content, re.DOTALL)
                if m:
                    extracted = json.loads(m.group(0))
                    # Normalizar
                    extracted = {k.lower().strip(): str(v).strip() for k, v in extracted.items()}
                    if extracted.get("promovente") and extracted.get("promovente").lower() not in ("desconocido", "none", "null", ""):
                        log.info(f"  ✨ Vision OCR exitoso para {pid}")
                        return extracted
        return None
    except Exception as e:
        log.error(f"  ❌ Error en Vision OCR: {e}")
        return None


# ─────────────────────────────────────────────────────────
# LOOP DE EXTRACCIÓN (procesa la queue pendiente)
# ─────────────────────────────────────────────────────────
def run_extraction(queue: PersistentQueue, log: logging.Logger):
    pending = queue.pending()
    if not pending:
        log.info("📋 Queue vacía")
        return

    log.info(f"Executing high-throughput extraction on {len(pending)} operational identifiers...")

    for item in pending:
        if _shutdown:
            break

        if not wait_for_llama(log, max_wait=60):
            log.error("Critical: LLM endpoint unreachable - cycle aborted")
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
        log.info(f"  Processor Task [{item.attempts + 1}/{CONFIG['MAX_RETRIES']}] {item.pid}")

        extracted = extract_with_ai(item.pid, context, log)

        # DIGITAL TWIN GROUNDING: Consultar el portal antes de decidir calidad
        portal_data = fetch_portal_docs(item.pid, log)

        # Fallback a Vision OCR si la IA de texto no fue convincente
        if not extracted or (extracted.get("promovente") or "").lower() in ("desconocido", "none", "", "null"):
            vision_extracted = extract_with_vision(item.pid, item.year, item.pdf, log)
            if vision_extracted:
                extracted = vision_extracted

        if extracted:
            # 1. Normalizar estructura técnica
            extracted = normalize_extracted_data(item.pid, extracted)
            
            # 2. Aterrizar con datos oficiales (Estrategia 1: Grounding)
            if portal_data:
                extracted = ground_data(extracted, portal_data, log)
                # Volver a normalizar por si el portal trajo nombres en minúscula
                extracted = normalize_extracted_data(item.pid, extracted)

            promovente = extracted.get("promovente", "").strip()
            
            # La descripción ya viene normalizada de normalize_extracted_data

            if promovente and promovente.lower() not in ("", "null", "n/a", "desconocido"):
                if not CONFIG["DRY_RUN"]:
                    write_to_csv(item.year, item.pid, extracted)
                    write_to_graph(item.pid, extracted)
                    write_to_supabase(item.year, item.pid, extracted, log)
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
                write_to_supabase(item.year, item.pid, fallback, log)
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
    print("\nTermination signal received - persisting operational state...")
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

    # Asegurar que el PID_FILE existe si estamos corriendo
    pid = os.getpid()
    try:
        with open("/tmp/zohar_agent_v2.pid", "w") as f:
            f.write(str(pid))
    except Exception:
        pass

    log   = setup_logging(CONFIG["LOG_FILE"])
    queue = PersistentQueue(CONFIG["QUEUE_FILE"])
    seen  = SeenGacetas(CONFIG["SEEN_FILE"])

    log.info("══ ZOHAR AGENT V2.2 START ══")
    log.info(f"  ZOHAR AGENT v2.2  |  Años: {target_years[0]}...{target_years[-1]}  |  DRY_RUN:{CONFIG['DRY_RUN']}")
    st = queue.stats()
    log.info(f"  Queue: {st}")
    log.info("═" * 58)

    CONFIG["DOCS_DIR"].mkdir(parents=True, exist_ok=True)

    def run_cycle():
        # ⚡ PRIORIDAD: Extracción de la queue global (IA)
        if not _shutdown:
            run_extraction(queue, log)

        # 🔍 Después del procesamiento, monitorear años para nuevos PDFs
        for year in target_years:
            if _shutdown: break
            log.info(f"Monitoring temporal index for year {year}...")
            pdf_links = fetch_pdf_links(year, seen, log)
            total_new = 0
            for url in pdf_links:
                if _shutdown: break
                n = process_pdf(url, year, queue, log)
                total_new += n
            if total_new > 0:
                log.info(f"Ingestion successful: {year}: {total_new} new identifiers cataloged")

    if CONFIG["DAEMON_MODE"]:
        log.info(f"HIGH-THROUGHPUT BATCH ESCALATION ACTIVE — Processing temporal index: {target_years}")
        while not _shutdown:
            # 1. Forzar recarga de cola desde disco
            queue = PersistentQueue(CONFIG["QUEUE_FILE"])
            pending_count = len(queue.pending())
            
            # 2. Si hay trabajo, procesar SIN DESCANSO
            if pending_count > 0:
                log.info(f"Initiating extraction cycle: {pending_count} identifiers queued.")
                run_extraction(queue, log)
                # Volver al inicio del bucle inmediatamente
                continue
            
            # 3. Si no hay trabajo de IA, buscar gacetas nuevas
            log.info("Queue empty. Initiating search for new datasets...")
            run_cycle()
            
            # 4. Solo dormir si REALMENTE no hay nada más que hacer
            if len(queue.pending()) == 0:
                poll_s = CONFIG["POLL_INTERVAL_MIN"] * 60
                log.info(f"No pending operations. Standby mode active for {CONFIG['POLL_INTERVAL_MIN']} minutes.")
                for _ in range(poll_s):
                    if _shutdown: break
                    time.sleep(1)
    else:
        run_cycle()

    log.info("Agent process terminated gracefully.")


if __name__ == "__main__":
    main()
