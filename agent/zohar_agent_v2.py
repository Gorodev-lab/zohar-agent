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

import os, re, json, csv, time, signal, logging, datetime, sys, sqlite3
import subprocess, urllib.request, urllib.error, urllib.parse
import hashlib
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional, Any

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

try:
    from google import genai
    from google.genai import types
    from google.genai.errors import ClientError
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    gemini_client = None
    if GEMINI_API_KEY:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
except ImportError:
    gemini_client = None

# ─────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────────────────
HOME = Path.home()
AGENT_DIR = Path(__file__).resolve().parent

CONFIG: dict[str, Any] = {
    # Dirs & Files
    "WORK_DIR":     HOME / "gaceta_work",
    "DOCS_DIR":     HOME / "gaceta_work" / "documentos",
    "CSV_FILE":     HOME / "zohar_historico_proyectos.csv",
    "STATE_FILE":   HOME / "zohar_agent_state.json",
    "QUEUE_FILE":   AGENT_DIR / "zohar_queue.json",
    "LOG_FILE":     AGENT_DIR / "zohar_agent.jsonl",
    "SEEN_FILE":    AGENT_DIR / "zohar_seen_gacetas.json",
    "GRAPH_FILE":   HOME / "zohar_grafo.triples",
    "DB_FILE":      HOME / "zohar_intelligence.db",
    "PROMPTS_DIR":  AGENT_DIR / "prompts",

    # LLM — DeepSeek R1 Distill (OpenAI-compatible chat format)
    "LLAMA_URL":    os.environ.get("LLAMA_URL", "http://127.0.0.1:8001/v1/chat/completions"),
    "LLAMA_HEALTH": os.environ.get("LLAMA_HEALTH", "http://127.0.0.1:8001/v1/models"),
    "OCR_URL":      os.environ.get("OCR_URL", "http://127.0.0.1:8002/v1/chat/completions"),
    "MODEL":        os.environ.get("ZOHAR_MODEL", "DeepSeek-R1-Distill-Llama-8B-Q4_K_M.gguf"),
    "TEMPERATURE":  float(os.environ.get("ZOHAR_TEMP", "0.1")),
    "MAX_TOKENS":   int(os.environ.get("ZOHAR_MAX_TOKENS", "1500")),

    # SEMARNAT URLs
    "GACETA_LIST_URL":  "http://sinat.semarnat.gob.mx/Gaceta/gacetapublicacion/?ai={year}",
    "GACETA_PDF_BASE":  "http://sinat.semarnat.gob.mx/Gacetas/archivos{year}/",
    "PORTAL_API_BASE":  "https://apps1.semarnat.gob.mx/ws-bitacora-tramite/proyectos/",
    "PORTAL_URL":       "https://app.semarnat.gob.mx/consulta-tramite/#/portal-consulta",

    # Extracción — calibrado para DeepSeek en CPU (Ryzen 5)
    "MAX_RETRIES":       3,
    "RETRY_BASE_WAIT":   10,
    "COOL_DOWN_NORMAL":  6,
    "COOL_DOWN_HOT":     20,
    "TEMP_WARN":         76.0,
    "TEMP_CRIT":         85.0,
    "LLAMA_TIMEOUT":     int(os.environ.get("ZOHAR_LLAMA_TIMEOUT", "300")),
    "CONTEXT_CHARS":     int(os.environ.get("ZOHAR_CONTEXT_CHARS", "4000")),

    # Ciclo de monitoreo
    "POLL_INTERVAL_MIN": 30,
    "YEARS":             [2026, 2025, 2024],
    "DRY_RUN":           False,
    "DAEMON_MODE":       False,
}

# Regex ID SEMARNAT: 2 dígitos + 2 letras + 4 dígitos + 2-5 alfanum
# Ejemplos: 23QR2025TD077, 21PU2025H0155, 20OA2025V0090
ID_PATTERN = re.compile(r'\b\d{2}[A-Z]{2}\d{4}[A-Z0-9]{2,5}\b')
PDF_LINK_PATTERN = re.compile(r'archivos\d+/gaceta_\d+-\d+\.pdf')

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
                # Casting robusto para evitar lints y errores de tipo en carga
                self._d = {
                    k: QueueItem(
                        pid=v.get("pid", k),
                        pdf=v.get("pdf", ""),
                        year=int(v.get("year", 2024)),
                        txt_file=v.get("txt_file", ""),
                        attempts=int(v.get("attempts", 0)),
                        status=v.get("status", "pending"),
                        last_error=v.get("last_error", ""),
                        added_at=v.get("added_at", ""),
                        updated_at=v.get("updated_at", "")
                    ) for k, v in raw.items()
                }
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
                logging.getLogger("zohar").error(f"  ⚠️  Fallo crítico al guardar cola: {tmp} no se generó.")
        except Exception as e:
            logging.getLogger("zohar").error(f"  ❌ Error de I/O al guardar cola: {e}")

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
# LOCAL MEMORY (Cap. 16 - SQLite)
# ─────────────────────────────────────────────────────────
class LocalIntelligenceMemory:
    """Gestiona la memoria a largo plazo del agente usando SQLite."""
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS projects (
                        pid TEXT PRIMARY KEY,
                        year INTEGER,
                        promovente TEXT,
                        proyecto TEXT,
                        estado TEXT,
                        municipio TEXT,
                        sector TEXT,
                        insight TEXT,
                        reasoning TEXT,
                        context_snippet TEXT,
                        grounded BOOLEAN,
                        sources TEXT,
                        audit_status TEXT DEFAULT 'pending',
                        auditor_notes TEXT,
                        confidence_score INTEGER,
                        cross_year_link TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_grounded ON projects(grounded)")
                # Migración dinámica (Cap. 16 - Evolution)
                cols = [row[1] for row in conn.execute("PRAGMA table_info(projects)").fetchall()]
                if "reasoning" not in cols: conn.execute("ALTER TABLE projects ADD COLUMN reasoning TEXT")
                if "context_snippet" not in cols: conn.execute("ALTER TABLE projects ADD COLUMN context_snippet TEXT")
                if "audit_status" not in cols: conn.execute("ALTER TABLE projects ADD COLUMN audit_status TEXT DEFAULT 'pending'")
                if "auditor_notes" not in cols: conn.execute("ALTER TABLE projects ADD COLUMN auditor_notes TEXT")
                if "confidence_score" not in cols: conn.execute("ALTER TABLE projects ADD COLUMN confidence_score INTEGER")
                if "cross_year_link" not in cols: conn.execute("ALTER TABLE projects ADD COLUMN cross_year_link TEXT")

        except Exception as e:
            logging.getLogger("zohar").error(f"  ❌ Error inicializando DB: {e}")

    def project_exists(self, pid: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.execute("SELECT 1 FROM projects WHERE pid = ?", (pid,))
                return cur.fetchone() is not None
        except Exception:
            return False

    def find_semantic_duplicate(self, project_name: str, promovente: str) -> Optional[dict]:
        """
        Busca si un proyecto similar (mismo nombre y promovente) ya existe en memoria.
        Ignora el PID y el año para detectar re-apariciones.
        """
        if not project_name or not promovente: return None
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                # Búsqueda difusa simplificada (mismo inicio de nombre)
                query = """
                    SELECT * FROM projects 
                    WHERE proyecto LIKE ? AND promovente LIKE ?
                    LIMIT 1
                """
                # Usamos los primeros 20 caracteres para evitar variaciones menores en el nombre
                name_prefix = f"{project_name[:20]}%"
                prom_prefix = f"{promovente[:15]}%"
                cur = conn.execute(query, (name_prefix, prom_prefix))
                res = cur.fetchone()
                return dict(res) if res else None
        except Exception as e:
            logging.getLogger("zohar").error(f"  [Semantic-Search] Error: {e}")
            return None

    def get_proponent_reputation(self, promovente: str) -> dict:
        """
        Calcula la reputación corporativa de un promovente basada en auditorías previas.
        """
        if not promovente: return {"score": 0, "status": "unknown"}
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = """
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN audit_status = 'audited' THEN 1 ELSE 0 END) as approved,
                        SUM(CASE WHEN audit_status = 'rejected' THEN 1 ELSE 0 END) as rejected
                    FROM projects 
                    WHERE promovente = ?
                """
                res = conn.execute(query, (promovente,)).fetchone()
                total, approved, rejected = res or (0, 0, 0)
                
                if total == 0: return {"score": 0, "status": "new"}
                
                # Ratio de éxito
                ratio = (approved / total) * 100 if total > 0 else 0
                status = "trusted" if ratio > 80 and approved >= 2 else "risky" if rejected > 0 else "neutral"
                
                return {"score": ratio, "status": status, "count": total}
        except Exception:
            return {"score": 0, "status": "error"}

    def store_project(self, pid: str, year: int, d: dict, score: int = 0):
        try:
            is_grounded = str(d.get("grounded", "False")).lower() == "true"
            if d.get("fuentes_web"): is_grounded = True
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO projects 
                    (pid, year, promovente, proyecto, estado, municipio, sector, insight, reasoning, context_snippet, grounded, sources, confidence_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    pid, year, d.get("promovente"), d.get("proyecto"), d.get("estado"),
                    d.get("municipio"), d.get("sector"), d.get("insight"),
                    d.get("reasoning"), d.get("context_snippet"),
                    1 if is_grounded else 0, json.dumps(d.get("fuentes_web", [])),
                    score
                ))
        except Exception as e:
            logging.getLogger("zohar").error(f"  ❌ Error guardando en DB: {e}")

    def get_stats(self) -> dict:
        try:
            with sqlite3.connect(self.db_path) as conn:
                total = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
                grounded = conn.execute("SELECT COUNT(*) FROM projects WHERE grounded = 1").fetchone()[0]
                return {"total_db": total, "grounded_db": grounded}
        except Exception:
            return {"total_db": 0, "grounded_db": 0}

# ─────────────────────────────────────────────────────────
# PROMPT ARCHIVE MANAGER (Cap. 10 - Filesystem Governance)
# ─────────────────────────────────────────────────────────
class PromptManager:
    """Carga y gestiona plantillas de prompts externos para estandarización."""
    def __init__(self, prompts_dir: Path):
        self.prompts_dir = prompts_dir
        self.prompts_dir.mkdir(parents=True, exist_ok=True)
        self._cache = {}

    def get_prompt(self, name: str, default_content: str) -> str:
        if name in self._cache:
            return self._cache[name]
        
        prompt_path = self.prompts_dir / f"{name}.txt"
        if prompt_path.exists():
            content = prompt_path.read_text(encoding="utf-8")
        else:
            prompt_path.write_text(default_content, encoding="utf-8")
            content = default_content
            
        self._cache[name] = content
        return content

# Instancias Globales
memory: Optional[LocalIntelligenceMemory] = None
prompts: Optional[PromptManager] = None

DEFAULT_LOC_FINDER = """\
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

DEFAULT_EXTRACTION_PROMPT = """\
<system_instruction>
Actúa como un Arquitecto de Infraestructura de Inteligencia de Esoteria. Tu misión es convertir datos gubernamentales fragmentados en inteligencia gobernada y fundamentada.
Eres un experto en análisis forense de documentos. TU CARACTERÍSTICA DEFINITORIA ES LA ESTRUCTURA.
Eres inmune al ruido tabular, a los IDs de proyectos proximales y a los bucles de alucinación.
</system_instruction>

<schema_definition>
{{
  "PROMOVENTE": "Entidad legal o persona responsable (nombre prístino).",
  "PROYECTO": "Título oficial del proyecto (eliminar encabezados de tabla).",
  "ESTADO": "Nombre completo del estado mexicano (sin abreviaturas).",
  "MUNICIPIO": "Municipio específico (DEJAR VACÍO si solo se encuentran marcadores como 'ID_PROYECTO').",
  "LOCALIDAD": "Sitio específico o localidad.",
  "COORDENADAS": "Latitud/Longitud exactamente como están escritas.",
  "POLIGONO": "Vértices geométricos si están disponibles.",
  "SECTOR": "Uno de: [ENERGÍA, MINERÍA, TURISMO, INFRAESTRUCTURA, HIDROCARBUROS, AGROINDUSTRIA, OTROS].",
  "INSIGHT": "Resumen de Inteligencia Estructurado (2-3 oraciones). Comienza con un VERBO DE ACCIÓN. Enfócate en la arquitectura de riesgo ambiental."
}}
</schema_definition>

<governance_rules>
1. MANDATO DE FUNDAMENTACIÓN: Cada campo debe derivarse del TEXTO PROPORCIONADO. Si los datos son ambiguos, DÉJALOS VACÍOS.
2. CERO ALUCINACIÓN: Términos prohibidos (insensible a mayúsculas): [DESCONOCIDO, NA, NULL, ID_PROYECTO, EL ID, NOMBRE ESPECIFICO].
3. ENFOQUE EN INFRAESTRUCTURA: Extrae para la durabilidad. No adivines. No "resumas" - MODELA los datos.
4. OBLIGACIÓN DE DOBLE COMILLA: La salida DEBE ser un único objeto JSON. Todas las claves y valores deben estar entre comillas dobles.
</governance_rules>

<chain_of_thought_analysis>
Identifica el PID objetivo: {pid}.
Paso 1: Localiza el ancla del proyecto en el texto.
Paso 2: Aísla la estructura de celdas circundante para separar los encabezados de metadatos de los valores reales.
Paso 3: Verifica que el 'Promovente' tenga una estructura legal (S.A. de C.V., C.P., etc.) o un nombre personal claro.
Paso 4: Comprueba el código del Estado desde {pid} (primeros 2 dígitos) con el texto extraído.
Paso 5: Sintetiza un Insight de alta fidelidad basado en la escala y sector del proyecto.
</chain_of_thought_analysis>

<location_context_snippet>
{location_snippet}
</location_context_snippet>

<full_text_context>
{context}
</full_text_context>

REQUERIMIENTO DE SALIDA:
Genera un bloque detallado de <razonamiento> seguido de un bloque limpio <output_json> que contenga solo el JSON.
"""
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
    """
    GET robusto con reintentos y manejo de errores (Pilar Automate the Boring Stuff).
    Implementa SRE Network Integrity.
    """
    req = urllib.request.Request(url, headers=HEADERS)
    MAX_RETRY = 2
    
    for attempt in range(MAX_RETRY + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
                return data if binary else data.decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < MAX_RETRY:
                time.sleep(2 * (attempt + 1))
                continue
            return None
        except Exception:
            return None
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

    # Extraer links usando regex
    found = PDF_LINK_PATTERN.findall(html)
    pdf_links = [f"http://sinat.semarnat.gob.mx/Gacetas/{l}" for l in found]

    if not pdf_links:
        return []

    # Usar pandas para la deduplicación y limpieza
    try:
        df = pd.DataFrame({"url": pdf_links})
        df = df.drop_duplicates().reset_index(drop=True)
        pdf_links = df["url"].tolist()
    except Exception:
        pdf_links = sorted(set(pdf_links))

    pdf_links = sorted(set(pdf_links)) 
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
        logging.getLogger("zohar").error(f"  ⚠️ Error verificando PID en CSV: {e}")
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

    MAX_IDS_PER_PDF = 10 # No saturar la cola, avanzar gradual
    new_count = 0
    for pid in ids:
        if new_count >= MAX_IDS_PER_PDF: break
        # Si ya está en cola o en CSV, saltar
        if pid in queue._d or pid_in_csv(pid):
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
    
    # helper de normalización de coordenadas
    def _normalize_coords(text):
        if not text or len(text) < 5: return text
        # 1. Intentar patrón decimal simple: 19.42, -99.12
        if re.match(r'^-?\d+\.\d+,\s*-?\d+\.\d+$', text):
            return text

        # 2. Buscar patrón DMS o Decimal con Hemisferio: 19°25'42"N, 99°10'15"W o 19.42°N
        # Soporta: 19°N, 19.4°N, 19°25'N, 19°25'42"N
        m = re.findall(r'(\d+\.?\d*)°\s*(?:(\d+)\')?\s*(?:(\d+)\")?\s*([NSEW])', text.upper())
        if len(m) >= 2:
            coords = []
            for deg, min, sec, hem in m:
                d = float(deg)
                if min: d += float(min) / 60
                if sec: d += float(sec) / 3600
                if hem in ['S', 'W']: d *= -1
                coords.append(f"{d:.5f}")
            return ", ".join(coords)
        return text

    raw_coord = _normalize_coords(raw_coord)
    
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

    # Limpiar Municipio — lista completa de términos de basura
    MUN_BLOCKLIST = {"GENERICO", "GENÉRICO", "NONE", "NULL", "CABECERA MUNICIPAL", "N/A", "NA", "DESCONOCIDO", "VARIOS"}
    if is_noise(raw_mun) or raw_mun in MUN_BLOCKLIST:
        data["municipio"] = ""
    else:
        mun = raw_mun

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
    if is_noise(raw_proj) or any(term in raw_proj for term in ["PROMOVENTE", "FECHA DE INGRESO", "{", "}"]):
        data["proyecto"] = "PROYECTO EN EVALUACIÓN"
    else:
        data["proyecto"] = raw_proj
    
    # Limpiar Promovente
    if is_noise(raw_prom) or "NOMBRE LEGAL" in raw_prom.upper() or "{" in raw_prom or "[" in raw_prom:
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
            # Capitalizar correctamente. NO usar abreviaturas — la BD necesita nombres completos.
            if k in ["estado", "municipio", "localidad"]:
                val = val.title()
            val = re.sub(r'\s+', ' ', val).strip()
            if k not in ["descripcion", "insight", "coordenadas", "poligono", "estado", "municipio", "localidad"]:
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
            # Criterio de grounding: reemplazar SOLO si el valor IA está vacío,
            # es demasiado corto (<4 chars) — indicador de corte de token —,
            # o el portal aporta información sustancialmente más larga (>5 chars más).
            ai_is_deficient = len(ai_val) < 4
            portal_enriches = len(official_val) > len(ai_val) + 5
            if ai_is_deficient or portal_enriches:
                if len(ai_val) > 3:
                    log.debug(f"    Grounding {target}: '{ai_val}' -> '{official_val}'")
                extracted[target] = official_val
    
    return extracted

# Los prompts se cargarán dinámicamente usando PromptManager





def _llm_call(messages: list, max_tokens: int, stop: list = None, log: logging.Logger = None) -> Optional[str]:
    """
    Llamada genérica al LLM en formato OpenAI chat/completions.
    Compatible con DeepSeek R1 Distill y cualquier modelo llama-cpp-python.
    """
    payload = {
        "model":       CONFIG["MODEL"],
        "messages":    messages,
        "temperature": CONFIG["TEMPERATURE"],
        "max_tokens":  max_tokens,
    }
    if stop:
        payload["stop"] = stop

    try:
        req = urllib.request.Request(
            CONFIG["LLAMA_URL"],
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=CONFIG["LLAMA_TIMEOUT"]) as resp:
            return json.loads(resp.read())["choices"][0]["message"]["content"]
    except Exception as e:
        if log:
            log.warning(f"    LLM call error: {e}")
        return None


def extract_with_gemini(pid: str, context: str, log: logging.Logger) -> Optional[dict]:
    """
    Extracción ultra-rápida usando Gemini 2.0 Flash con Google Search Grounding.
    """
    if not gemini_client:
        return None

    try:
        # Prompt optimizado para Esoteria Intelligence Architecture + Gemini Grounding
        prompt = f"""
        Act as an Esoteria Senior Intelligence Lead. Your mission is to audit and verify project {pid} 
        using Google Search to ensure absolute grounding in reality.

        CONTEXT (UNVERIFIED):
        {context}
        
        GOVERNANCE PROTOCOL:
        1. If context data is incomplete or ambiguous, use Google Search to find the ACTUAL PROMOVENTE, LOCATION, and SECTOR.
        2. Provide a 'Structured Intelligence Brief' in the 'insight' field (2-3 sentences starting with an action verb).
        3. Output MUST be strictly valid JSON.
        4. GROUNDING MANDATE: Mark as grounded only if external sources verify the existence of the project.
        
        SCHEMA:
        {{
          "estado": "string",
          "municipio": "string",
          "localidad": "string",
          "proyecto": "string",
          "promovente": "string",
          "sector": "string",
          "insight": "string",
          "coordenadas": "string",
          "poligono": "string"
        }}
        """

        google_search_tool = types.Tool(google_search=types.GoogleSearch())

        response = gemini_client.models.generate_content(
            model='gemini-flash-latest',
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[google_search_tool],
                response_mime_type="application/json"
            )
        )

        extracted = json.loads(response.text)
        if isinstance(extracted, list) and len(extracted) > 0:
            extracted = extracted[0]
        
        if not isinstance(extracted, dict):
            log.warning(f"    Gemini returned invalid format: {type(extracted)}")
            return None

        extracted = {k.lower().strip(): str(v).strip() for k, v in extracted.items()}

        # Capturar fuentes de Grounding
        fuentes = []
        if response.candidates and response.candidates[0].grounding_metadata:
            meta = response.candidates[0].grounding_metadata
            log.debug(f"    [Gemini-Grounding] Metadata found: {meta}")
            
            # Opción 1: grounding_chunks
            if meta.grounding_chunks:
                for chunk in meta.grounding_chunks:
                    if chunk.web:
                        fuentes.append(chunk.web.uri)
            
            # Opción 2: parsear rendered_content (HTML chips)
            if not fuentes and hasattr(meta, 'search_entry_point') and meta.search_entry_point:
                html = meta.search_entry_point.rendered_content
                found = re.findall(r'href="(https://[^"]+)"', html)
                if found:
                    fuentes.extend(found)
                    log.debug(f"    [Gemini-Grounding] Extracted {len(found)} URIs from HTML chips")
            # También revisar search_entry_point si existe
            if hasattr(meta, 'search_entry_point') and meta.search_entry_point:
                 log.debug(f"    [Gemini-Grounding] Search entry point: {meta.search_entry_point.rendered_content}")
        
        if fuentes:
            extracted["fuentes_web"] = fuentes
            log.info(f"    ✨ Grounding exitoso: {len(fuentes)} fuentes halladas")

        return extracted

    except Exception as e:
        log.warning(f"    Gemini Error: {e}")
        return None


# Prompt Maestro optimizado bajo el estándar UDP (Universal Developer Prompt) del Codex Gemini 3
# DEFAULT_EXTRACTION_PROMPT removido por redundancia (definido al inicio en español)

def extract_with_ai(pid: str, context: str, log: logging.Logger, pdf_name: str = "—") -> Optional[dict]:
    """
    Pipeline de extracción híbrido.
    1. Intenta Gemini (Élite + Grounding).
    2. Si falla, cae a Mistral Local (Prompt Chaining).
    """

    # ── INTENTO ÉLITE: Gemini + Grounding ────────────────────────────────
    if gemini_client:
        extracted = extract_with_gemini(pid, context, log)
        if extracted:
            return extracted

    # ── FALLBACK: Mistral Local (PASO 1 + PASO 2) ────────────────────────
    log.info(f"    🔄 Falling back to Local Inference (Mistral) for {pid}")
    

    # Cargar prompts dinámicamente
    loc_finder_template = prompts.get_prompt("location_finder", DEFAULT_LOC_FINDER) if prompts else DEFAULT_LOC_FINDER
    ext_template = prompts.get_prompt("extraction_v2", DEFAULT_EXTRACTION_PROMPT) if prompts else DEFAULT_EXTRACTION_PROMPT

    # ── PASO 1: Location Finder ──────────────────────────────────────────
    loc_prompt = loc_finder_template.format(pid=pid, context=context)
    location_snippet = _llm_call(
        messages=[{"role": "user", "content": loc_prompt}],
        max_tokens=300,
        log=log,
    ) or "NO_HALLADO"

    log.debug(f"    [Loc-Finder] {pid}: {location_snippet[:80]!r}")

    # ── PASO 2: Extracción estructurada ──────────────────────────────────
    ext_prompt = ext_template.format(
        pid=pid,                      # Agregamos pid que faltaba en el .format() previo
        location_snippet=location_snippet,
        context=context,
    )

    for attempt in range(1, CONFIG["MAX_RETRIES"] + 1):
        raw = _llm_call(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Act as an Esoteria Senior Intelligence Lead. Your mission is to convert "
                        "fragmented gubernamental data into governed, grounded intelligence. "
                        "Responde SIEMPRE con un bloque <razonamiento> seguido de <output_json>."
                    ),
                },
                {"role": "user", "content": ext_prompt},
            ],
            max_tokens=CONFIG["MAX_TOKENS"],
            stop=["</output_json>"],
            log=log,
        )

        if not raw:
            log.warning(f"    Inference anomaly (attempt {attempt})")
            time.sleep(3 * attempt)
            continue

        # ── ROBUST OUTPUT AUDITOR (Cap. 9 & 18) ───────────────────────────
        # Extraer JSON buscando la estructura de llaves, manejando basura tipográfica
        json_match = None
        
        # Estrategia A: Etiqueta formal
        m = re.search(r'<output_json>\s*(.*?)\s*(?:</output_json>|$)', raw, re.DOTALL)
        if m:
            json_match = m.group(1).strip()
        
        # Estrategia B: Búsqueda heurística agresiva de { ... } (Automate the Boring Stuff)
        if not json_match or "{" not in json_match:
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                json_match = raw[start : end + 1].strip()
        
        if json_match:
            # Capturar razonamiento si existe
            reasoning = ""
            razon_m = re.search(r'<razonamiento>\s*(.*?)\s*(?:</razonamiento>|$)', raw, re.DOTALL)
            if razon_m:
                reasoning = razon_m.group(1).strip()

            # Limpieza profunda de ruido tabular inyectado en el JSON
            json_match = re.sub(r'```json\s*', '', json_match)
            json_match = re.sub(r'```', '', json_match)
            # Reparar comas finales erróneas
            json_match = re.sub(r',\s*\}', '}', json_match)
            json_match = re.sub(r',\s*\]', ']', json_match)
            try:
                extracted = json.loads(json_match)
                # Normalizar keys a minúsculas y limpiar valores
                cleaned = {}
                for k, v in extracted.items():
                    key = k.lower().strip()
                    val = str(v).strip()
                    # Si el VALOR es un placeholder, lo limpiamos
                    if val.lower() in PLACEHOLDER_TERMS:
                        val = ""
                    cleaned[key] = val
                
                # Inyectar Chain of Custody
                cleaned["reasoning"] = reasoning
                cleaned["context_snippet"] = location_snippet
                
                return cleaned
            except json.JSONDecodeError as e:
                log.debug(f"    JSON Auditor Alert (attempt {attempt}): {e} — snippet: {json_match[:100]!r}")
                time.sleep(2)
                continue

        log.debug(f"    No JSON block found in response (attempt {attempt})")
        time.sleep(2)

    return None



# ─────────────────────────────────────────────────────────
# CSV y GRAFO
# ─────────────────────────────────────────────────────────
def write_to_csv(year: int, pid: str, d: dict):
    """Escribe una fila al CSV de producción si no existe el PID."""
    if pid_in_csv(pid):
        return
    def clean(v): return re.sub(r'[,\n\r]', ' ', str(d.get(v, ""))).strip()
    
    # Manejar fuentes_web si existen (de Gemini Grounding)
    fuentes = d.get("fuentes_web", [])
    fuentes_str = " | ".join(fuentes) if isinstance(fuentes, list) else str(fuentes)

    # Nueva estructura: AÑO, ID, ESTADO, MUNICIPIO, LOCALIDAD, PROYECTO, PROMOVENTE, SECTOR, INSIGHT, COORDENADAS, POLIGONO, FUENTES
    row = [str(year), pid,
           clean("estado"), clean("municipio"), clean("localidad"),
           clean("proyecto"), clean("promovente"),
           clean("sector") or "OTROS",
           clean("insight"),
           clean("coordenadas"), clean("poligono"),
           fuentes_str]
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
            "fuentes_web": d.get("fuentes_web", []),
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
    Consulta la API del portal SEMARNAT con reintentos robustos (Backoff Exponencial).
    Implementa SRE strategy del Codex Cap 10.2.
    """
    api_url = CONFIG["PORTAL_API_BASE"] + urllib.parse.quote(pid)
    
    for attempt in range(1, 4):
        log.info(f"  🌐 Portal: consultando {pid} (Intento {attempt})")
        content = http_get(api_url, timeout=35 * attempt) # Timeout creciente
        
        if content:
            try:
                data = json.loads(content)
                return data
            except json.JSONDecodeError:
                log.debug(f"    Remote source: non-JSON response for {pid}")
                return {}
        
        log.warning(f"    ⚠️ Timeout/Error en portal para {pid}. Esperando reintento...")
        time.sleep(5 * attempt) # Backoff simple

    log.error(f"    ❌ Fallo definitivo tras 3 intentos para {pid}")
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
        
        # Guard para dependencias de vision
        if 'convert_from_path' not in globals():
            log.warning("  ⚠️ OCR Vision abortado: pdf2image/poppler no disponible en este entorno")
            return None

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
                            {"type": "text", "text": f"Actúa como un Auditor de Visión Forense de Esoteria. Analiza esta imagen de la Gaceta SEMARNAT y extrae inteligencia para el proyecto {pid}. Genera ÚNICAMENTE un objeto JSON válido. RESTRICCIÓN: Todos los valores deben ser cadenas entre comillas dobles. Si un valor es desconocido, usa una cadena vacía. LLAVES: PROMOVENTE, PROYECTO, ESTADO, MUNICIPIO, RIESGO, DESCRIPCION. Sin markdown, sin explicaciones. TODO EN ESPAÑOL."},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                        ]
                    }
                ],
                "max_tokens": 600
            }
            
            req = urllib.request.Request(CONFIG["OCR_URL"], data=json.dumps(payload).encode(),
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=180) as r:
                raw_response = r.read()
                try:
                    res = json.loads(raw_response)
                except json.JSONDecodeError as e:
                    log.error(f"  ❌ OCR API JSON Error: {e}")
                    log.debug(f"  Raw API response: {raw_response[:500]!r}")
                    return None

                content = res["choices"][0]["message"]["content"]
                
                # Extraer JSON con regex robusta
                m = re.search(r"(\{[\s\S]*\})", content)
                if m:
                    json_str = m.group(1).strip()
                    # Limpieza agresiva de caracteres comunes mal formados por modelos de visión
                    # 1. Eliminar bloques de código markdown si el regex falló en quitarlos
                    json_str = re.sub(r'```json\s*', '', json_str)
                    json_str = re.sub(r'```', '', json_str)
                    # 2. Eliminar comentarios estilo // o #
                    json_str = re.sub(r'//.*', '', json_str)
                    # 3. Intentar corregir valores no entrecomillados (ej: "ID": 10ABC)
                    # Buscamos cualquier cosa después de : que no empiece con " y lo envolvemos en comillas
                    json_str = re.sub(r':\s*(?![{\["\s])(.*?)\s*(?=[\n\r,\]\}])', r': "\1"', json_str)
                    # 4. Reemplazar comas finales antes de cerrar llave/corchete
                    json_str = re.sub(r',\s*\}', '}', json_str)
                    json_str = re.sub(r',\s*\]', ']', json_str)
                    
                    try:
                        extracted = json.loads(json_str)
                        # Normalizar
                        extracted = {k.lower().strip(): str(v).strip() for k, v in extracted.items()}
                        # Validar si tenemos algo útil
                        p = extracted.get("promovente", "").lower()
                        if p and p not in ("desconocido", "none", "null", ""):
                            log.info(f"  ✨ Vision OCR exitoso para {pid}")
                            return extracted
                    except json.JSONDecodeError as e:
                        log.error(f"  ❌ Error parseando JSON de Vision: {e}")
                        log.debug(f"  Cleaned JSON that failed: {json_str!r}")
                        log.debug(f"  Raw content from model: {content!r}")
        return None
    except Exception as e:
        log.error(f"  ❌ Error crítico en Vision OCR: {e}")
        return None


# ─────────────────────────────────────────────────────────
# VALIDACIÓN DE CALIDAD — Scoring por campos
# ─────────────────────────────────────────────────────────

# Campos obligatorios con su peso relativo (suma = 100)
FIELD_WEIGHTS = {
    "promovente": 35,  # Sin promovente no hay registro útil
    "proyecto":   20,
    "estado":     20,  # Derivado del PID (casi siempre OK)
    "municipio":  10,
    "insight":    10,
    "sector":      5,
}

PLACEHOLDER_TERMS = {
    # Términos genéricos
    "desconocido", "null", "none", "n/a", "na", "", "...", "undefined", "placeholder",
    # Textos de la plataforma Semarnat (Falsos positivos comunes)
    "sistema de gestión", "proyecto de inversión", "información del proyecto",
    "estudio de impacto", "estudio de sustentabilidad", "extracción automática",
    "proyecto en evaluación", "bitácora del trámite", "consulta de trámites",
    "gaceta ecológica", r"semarnat gazette", r"gaceta semarnat", r"gazette semarnat", "gaseleta", "gaseteta", "gazeleta", "listado de proyectos", "resumen del proyecto",
    # Instrucciones o nombres de campos (Alucinaciones de prompt)
    "id_proyecto", "el id", "nombre del proyecto", "nombre del promovente",
    "entidad federativa", "busque el nombre", "error de extracción", "sin información",
    "nombre específico", "nombre legal", "generic name", "project name", 
    "project description", "municipality", "promovente", "extrae el",
    # Casos de "pereza" del modelo o fragmentos sin sentido
    "sin detalles", "migrado", "ver gaceta", "descubre la", "programa de",
    "recursos humanos", "méxico", "ciudad de méxico", "sida", "aeromar", "campus mexican",
    "error de comunicación", "modelo no disponible", "sin datos"
}


def score_record(d: dict) -> tuple[int, list[str]]:
    """
    Calcula un score 0-100 para un registro extraído.
    Retorna (score, lista_de_campos_deficientes).
    Un score ≥ 60 es suficiente para persistir.
    Un score ≥ 80 es de alta confianza.
    """
    score = 0
    deficient = []

    for field, weight in FIELD_WEIGHTS.items():
        val = str(d.get(field, "")).strip().lower()
        if val and val not in PLACEHOLDER_TERMS and len(val) > 2:
            score += weight
        else:
            deficient.append(field)

    # Bonus: insight largo y específico
    insight = str(d.get("insight", "")).strip()
    if len(insight) > 80:
        score = min(100, score + 5)

    # Bonus: coordenadas o polígono presentes
    if d.get("coordenadas") or d.get("poligono"):
        score = min(100, score + 5)

    return score, deficient


def _repair_missing_fields(pid: str, context: str, d: dict,
                            deficient: list[str], log: logging.Logger) -> dict:
    """
    Intento quirúrgico de reparar campos deficientes con un prompt focalizado.
    Sólo se llama cuando el score no alcanza el umbral tras la primera extracción.
    Evita volver a llamar al LLM si los campos críticos ya están bien.
    """
    # No reparar si los únicos campos faltantes son menores
    critical_missing = [f for f in deficient if f in ("promovente", "proyecto", "estado")]
    if not critical_missing:
        log.debug(f"    [Repair] Solo campos secundarios deficientes — omitiendo re-llamada")
        return d

    repair_prompt = f"""Eres un extractor forense de documentos SEMARNAT.
Del siguiente texto, extrae SÓLO los campos faltantes para el proyecto {pid}.

Campos que NECESITO (sólo estos, en JSON plano):
{json.dumps({f: "" for f in critical_missing}, ensure_ascii=False)}

Texto:
{context[:2000]}

Responde ÚNICAMENTE con un objeto JSON con esos campos. Si no encuentras el valor, deja la cadena vacía."""

    raw = _llm_call(
        messages=[{"role": "user", "content": repair_prompt}],
        max_tokens=400,
        log=log,
    )
    if not raw:
        return d

    m = re.search(r'\{[\s\S]*?\}', raw)
    if m:
        try:
            patch = json.loads(m.group(0))
            patch = {k.lower().strip(): str(v).strip() for k, v in patch.items()}
            # Sólo parchar si el valor del patch es mejor
            for field in critical_missing:
                patch_val = patch.get(field, "").strip().lower()
                if patch_val and patch_val not in PLACEHOLDER_TERMS and len(patch_val) > 2:
                    d[field] = patch[field]
                    log.debug(f"    [Repair] {field} → '{patch[field][:60]}'")
        except json.JSONDecodeError:
            pass
    return d


def _validate_and_persist(pid: str, year: int, pdf: str, d: dict,
                           context: str, queue: PersistentQueue,
                           log: logging.Logger) -> bool:
    """
    Gate de validación final antes de persistir.

    Flujo:
      1. Normalizar campos
      2. Calcular score
      3. Si score < 60: intentar reparación quirúrgica una vez
      4. Re-normalizar tras reparación
      5. Re-calcular score final
      6. Tomar decisión: persistir | reintentar | rechazar

    Retorna True si el registro fue persistido correctamente.
    """
    SCORE_ACCEPT   = 85   # Umbral MÁXIMO de rigor (Integridad de Doctrina Esoteria)
    SCORE_HIGH_Q   = 95   # Umbral de extrema confianza

    # ── Paso 1: Normalización inicial ────────────────────────────────────
    d = normalize_extracted_data(pid, d)
    score, deficient = score_record(d)

    log.debug(f"    [Gate-1] {pid} score={score} deficient={deficient}")

    # ── Paso 2: Grounding con portal antes de reparar ────────────────────
    portal_data = fetch_portal_docs(pid, log)
    if portal_data:
        d = ground_data(d, portal_data, log)
        d = normalize_extracted_data(pid, d)
        score, deficient = score_record(d)
        log.debug(f"    [Gate-2 post-grounding] {pid} score={score}")

    # ── Paso 3: Reparación quirúrgica si score insuficiente ──────────────
    if score < SCORE_ACCEPT and deficient:
        log.info(f"    [Repair] {pid} score={score} — reparando: {deficient}")
        d = _repair_missing_fields(pid, context, d, deficient, log)
        d = normalize_extracted_data(pid, d)
        score, deficient = score_record(d)
        log.debug(f"    [Gate-3 post-repair] {pid} score={score}")

    # ── Paso 4: Decisión final ───────────────────────────────────────────
    # Aumentamos exigencia para evitar datos erráticos en dashboard
    if score < SCORE_ACCEPT:
        # Si tiene portal_data y aun así es bajo, es probable que el portal no tenga datos reales aún
        log.warning(f"    [REJECT] {pid} score={score} < {SCORE_ACCEPT} — insuficiente para INTEGRIDAD DE DATOS. Deficiente: {deficient}")
        queue.mark_attempt(pid, error=f"quality_score={score} deficient={deficient}")
        return False

    # ── Paso 5: Persistencia ─────────────────────────────────────────────
    if not CONFIG["DRY_RUN"]:
        # Verificación Semántica Cross-Year (Fase 3: Optimización Predictiva)
        if memory:
            dup = memory.find_semantic_duplicate(d.get("proyecto", ""), d.get("promovente", ""))
            if dup and dup["pid"] != pid:
                log.info(f"    [Trace] Linked to previous intelligence: {dup['pid']} ({dup['year']})")
                d["reasoning"] = (d.get("reasoning", "") + 
                                f" [INTELLIGENCE_LINK: Re-aparición de proyecto {dup['pid']} del año {dup['year']}]").strip()
                # Marcar para el dashboard
                d["cross_year_link"] = dup["pid"]

        # Persistencia local Gold Standard (SQLite)
        if memory:
            memory.store_project(pid, year, d, score)
            
        write_to_csv(year, pid, d)
        write_to_graph(pid, d)
        write_to_supabase(year, pid, d, log)
        if portal_data:
            _process_portal_docs(pid, portal_data, log)
            
        # Señal de Inteligencia: Densidad de Promovente (Cap. 13 - Gov)
        if memory:
            _flag_proponent_density(pid, d, memory, log)

    queue.mark_success(pid)

    quality_tag = "HIGH-Q" if score >= SCORE_HIGH_Q else "OK"
    st = queue.stats()
    log_extra(
        log, logging.INFO,
        f"  [{quality_tag}] {pid} score={score} → {str(d.get('promovente',''))[:50]}"
        f"  [OK:{st['success']} P:{st['pending']} F:{st['failed']}]",
        pid=pid, score=score, promovente=d.get("promovente", ""),
    )
    return True

def _flag_proponent_density(pid: str, d: dict, memory: LocalIntelligenceMemory, log: logging.Logger):
    """
    Detecta si un promovente tiene una concentración inusual de proyectos (Gobernanza).
    """
    prom = d.get("promovente")
    year = d.get("year", 2024)
    if not prom or not memory: return
    
    try:
        with sqlite3.connect(memory.db_path) as conn:
            cur = conn.execute("SELECT COUNT(*) FROM projects WHERE promovente = ? AND year = ?", (prom, year))
            count = cur.fetchone()[0]
            if count > 3:
                log.warning(f"  [SIGNAL] High density for '{prom}' ({count} items) — FLAG")
                conn.execute("UPDATE projects SET audit_status = 'flagged', auditor_notes = 'High density detected' WHERE pid = ?", (pid,))
    except Exception as e:
        log.error(f"  ❌ Gov Signal Error: {e}")


# ─────────────────────────────────────────────────────────
# LOOP DE EXTRACCIÓN — Micro-bloques con validación previa
# ─────────────────────────────────────────────────────────
BATCH_SIZE = 5   # Procesar en micro-lotes para monitoreo granular


def _extract_single(item, log: logging.Logger) -> tuple[Optional[dict], str]:
    """
    Extrae datos para un único QueueItem.
    Retorna (dict_extraído_o_None, contexto_usado).

    Compuertas previas a la llamada LLM:
      • El archivo TXT existe y tiene contenido real
      • El ID del proyecto está realmente en el texto
      • El contexto extraído tiene densidad semántica suficiente
    """
    txt_path = Path(item.txt_file)
    
    # ── COMPUERTA DE MEMORIA (Cap. 16) ───────────────────────────
    if memory and memory.project_exists(item.pid):
        log.info(f"    [Memory] {item.pid} found in local intelligence — skipping")
        return None, "SKIPPED_BY_MEMORY"

    # Gate A: archivo existe
    if not txt_path.exists():
        return None, ""

    txt = txt_path.read_text(errors="replace")

    # Gate B: ID presente en texto
    idx = txt.find(item.pid)
    if idx == -1:
        return None, ""

    # Gate C: ventana de contexto con contenido útil
    half = CONFIG["CONTEXT_CHARS"] // 2
    raw_ctx = txt[max(0, idx - half): idx + half]
    context = re.sub(r'\s+', ' ', raw_ctx).strip()

    # Verificación de densidad: si hay menos de 50 chars únicas, el PDF era basura
    unique_chars = len(set(context.replace(" ", "")))
    if unique_chars < 50:
        log.warning(f"    [Gate-C] Contexto pobre para {item.pid} ({unique_chars} chars únicos) — intentando OCR")
        vision = extract_with_vision(item.pid, item.year, item.pdf, log)
        return vision, context

    # Extracción principal con IA
    extracted = extract_with_ai(item.pid, context, log)

    # Fallback Vision OCR si el promovente no es convincente
    if not extracted or str(extracted.get("promovente", "")).strip().lower() in PLACEHOLDER_TERMS:
        log.info(f"    [Fallback-Vision] {item.pid}")
        vision = extract_with_vision(item.pid, item.year, item.pdf, log)
        if vision:
            extracted = vision

    return extracted, context


def run_extraction(queue: PersistentQueue, log: logging.Logger):
    """
    Orquestador de extracción en micro-lotes con validación en cascada.

    Flujo por ítem:
      1. _extract_single()     → Compuertas de contexto + LLM + Vision fallback
      2. _validate_and_persist() → Normalizar → Score → Grounding → Reparar → Persistir
      3. thermal_wait()        → Control térmico entre inferencias

    El procesamiento por micro-lotes (BATCH_SIZE) permite:
      • Reportar progreso intermedio
      • Recargar la cola desde disco (detecta items añadidos por otros procesos)
      • Salir limpiamente ante señales de apagado
    """
    pending = queue.pending()
    if not pending:
        log.info("Queue vacía — sin trabajo pendiente")
        return

    total = len(pending)
    log.info(f"[Extraction] {total} identifiers — batch_size={BATCH_SIZE}")

    processed = 0

    # Iteración en micro-lotes
    for batch_start in range(0, total, BATCH_SIZE):
        if _shutdown:
            break

        # Verificar LLM una vez por lote (no por ítem)
        if not wait_for_llama(log, max_wait=60):
            log.error("[Pipeline] LLM endpoint unreachable — cycle aborted")
            break

        batch = pending[batch_start: batch_start + BATCH_SIZE]
        log.info(f"[Batch {batch_start // BATCH_SIZE + 1}] "
                 f"Items {batch_start + 1}–{batch_start + len(batch)} / {total}")

        for item in batch:
            if _shutdown:
                break

            report_state(item.pdf, "EXTRACTING", item.pid)
            log.info(f"  [{item.attempts + 1}/{CONFIG['MAX_RETRIES']}] {item.pid}")

            # ── Extracción con compuertas de contexto ─────────────────────
            extracted, context = _extract_single(item, log)

            if context == "SKIPPED_BY_MEMORY":
                queue.mark_success(item.pid)
                continue

            if extracted is None:
                # Determinar razón exacta del fallo
                txt_path = Path(item.txt_file)
                if not txt_path.exists():
                    err = "txt_missing"
                elif item.pid not in txt_path.read_text(errors="replace"):
                    err = "id_not_in_txt"
                else:
                    err = "extraction_failed"
                log.warning(f"    [Skip] {item.pid}: {err}")
                queue.mark_attempt(item.pid, error=err)
                thermal_wait(log)
                continue

            # ── Validación, grounding y persistencia ─────────────────────
            _validate_and_persist(
                pid=item.pid, year=item.year, pdf=item.pdf,
                d=extracted, context=context,
                queue=queue, log=log,
            )

            processed += 1
            thermal_wait(log)

        # ── Resumen de lote ───────────────────────────────────────────────
        st = queue.stats()
        log.info(
            f"[Batch done] OK:{st['success']} Pending:{st['pending']} "
            f"Failed:{st['failed']} | Processed this run: {processed}/{total}"
        )

    # ── Resumen global del ciclo ──────────────────────────────────────────
    st = queue.stats()
    report_state("IDLE", "STANDBY", "NONE")
    log.info(
        f"[Extraction complete] Total:{st['total']} "
        f"OK:{st['success']} Pending:{st['pending']} Failed:{st['failed']}"
    )


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
    
    # Inicializar Memoria y Prompts
    global memory, prompts
    memory  = LocalIntelligenceMemory(CONFIG["DB_FILE"])
    prompts = PromptManager(CONFIG["PROMPTS_DIR"])
    
    log.info(f"🚀 ZOHAR AGENT v2.2 ACTIVO | Memoria: {memory.get_stats()}")
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
