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
import hashlib, asyncio, httpx, duckdb
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional, Any, List
# Cache async in-memory (reemplaza aiocache — sin dependencias externas)
import functools
def cached(ttl: int = 300, **_kwargs):
    """Decorador de cache async in-memory con TTL (segundos).
    Drop-in replacement de aiocache.cached para funciones async.
    """
    def decorator(fn):
        _cache: dict = {}
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            now = time.monotonic()
            if key in _cache:
                result, ts = _cache[key]
                if now - ts < ttl:
                    return result
            result = await fn(*args, **kwargs)
            _cache[key] = (result, now)
            return result
        wrapper.cache_clear = lambda: _cache.clear()
        return wrapper
    return decorator

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from supabase import create_client, Client
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_PUBLISHABLE_KEY")
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
    from google.genai.errors import APIError
    HAS_GEMINI = True
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    gemini_client = None
    if GEMINI_API_KEY:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
except ImportError:
    HAS_GEMINI = False
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
    "MAX_LOG_SIZE_MB":   50,
    # Menos contexto para modelos pequeños → menos ruido tabular
    "CONTEXT_CHARS":     int(os.environ.get("ZOHAR_CONTEXT_CHARS", "2500")),
    
    # Extra context data
    "ORDENAMIENTOS_CSV": AGENT_DIR.parent / "ordenamientos_ecologicos_expedidos.csv",
    "HISTORIC_DATA_JSON": AGENT_DIR / "semarnat_historic_consultations.json",
    "AIR_QUALITY_CSV": AGENT_DIR.parent / "d3_aire01_49_1.csv",

    # Google Cloud Vision
    "VISION_API_KEY":    os.environ.get("GEMINI_API_KEY"),
    "VISION_URL":        "https://vision.googleapis.com/v1/images:annotate",

    # Gemini Config
    "GEMINI_MODEL":      "gemini-3-flash-preview",

    # Server Identity
    "SERVER_NAME":       os.environ.get("SERVER_NAME", "main-server"),

    # Ciclo de monitoreo
    "POLL_INTERVAL_MIN": 30,
    "YEARS":             [2026],
    "DRY_RUN":           False,
    "DAEMON_MODE":       False,
    "HEARTBEAT_FILE":    HOME / ".zohar_heartbeat",
    "HEARTBEAT_TIMEOUT": 30, # segundos
    # TONL-A2: Max tokens separado para LLM local — el JSON de salida no supera 500 tokens
    "MAX_TOKENS_EXTRACT": int(os.environ.get("ZOHAR_MAX_TOKENS_EXTRACT", "500")),
    "MAX_TOKENS_GEMINI":  int(os.environ.get("ZOHAR_MAX_TOKENS_GEMINI", "2000")),
}

# ─────────────────────────────────────────────────────────
# MOTORES DE ALTO RENDIMIENTO (STRATEGY 1)
# ─────────────────────────────────────────────────────────
# Semáforo: limitado a 2 para Ryzen 5 + LLM local compartiendo núcleos (TONL-A1)
extraction_semaphore = asyncio.Semaphore(2)
# Cliente HTTP global para reutilización de conexiones (pooling)
http_client: Optional[httpx.AsyncClient] = None

# Inicializar DuckDB (Storage local de alto rendimiento)
DUCK_DB_FILE = CONFIG["WORK_DIR"] / "zohar_warehouse.duckdb"
DUCK_DB_FILE.parent.mkdir(parents=True, exist_ok=True)

def get_duck_conn():
    try:
        return duckdb.connect(str(DUCK_DB_FILE))
    except Exception as e:
        logging.warning(f"⚠️ DuckDB locked ({e}). Usando modo in-memory.")
        return duckdb.connect(":memory:")

duck_conn = get_duck_conn()

duck_conn.execute("""
    CREATE TABLE IF NOT EXISTS fragments_cache (
        hash TEXT PRIMARY KEY,
        result TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
duck_conn.execute("""
    CREATE TABLE IF NOT EXISTS project_warehouse (
        pid TEXT PRIMARY KEY,
        data JSON,
        grounded BOOLEAN,
        audit_trace TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

duck_conn.execute("""
    CREATE TABLE IF NOT EXISTS environmental_zoning (
        id INTEGER PRIMARY KEY,
        estado TEXT,
        programa TEXT,
        modalidad TEXT,
        expedicion TEXT,
        superficie_ha DOUBLE,
        fecha DATE
    )
""")

duck_conn.execute("""
    CREATE TABLE IF NOT EXISTS historic_consultations (
        clave TEXT PRIMARY KEY,
        modalidad TEXT,
        promovente TEXT,
        proyecto TEXT,
        ubicacion TEXT,
        sector TEXT,
        fechas TEXT,
        anio INTEGER,
        links JSON
    )
""")

duck_conn.execute("""
    CREATE TABLE IF NOT EXISTS air_quality_emissions (
        entidad TEXT,
        municipio TEXT,
        tipo_fuente TEXT,
        so2 DOUBLE,
        co DOUBLE,
        nox DOUBLE,
        cov DOUBLE,
        pm10 DOUBLE,
        pm2_5 DOUBLE,
        nh3 DOUBLE,
        entidad_nombre TEXT
    )
""")

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
                        year=int(v.get("year", 2026)),
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
            item.last_error = str(error)[:120]
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
                if "coordenadas" not in cols: conn.execute("ALTER TABLE projects ADD COLUMN coordenadas TEXT")

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
                name_prefix = f"{str(project_name)[:20]}%"
                prom_prefix = f"{str(promovente)[:15]}%"
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
        log = logging.getLogger("zohar")
        try:
            is_grounded = str(d.get("grounded", "False")).lower() == "true"
            if d.get("fuentes_web"): is_grounded = True

            # Normalizar fuentes a JSON string para SQLite
            sources_json = json.dumps(d.get("fuentes_web", []))

            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO projects 
                    (pid, year, promovente, proyecto, estado, municipio, sector, insight, reasoning, context_snippet, grounded, sources, confidence_score, coordenadas)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    pid, year, d.get("promovente"), d.get("proyecto"), d.get("estado"),
                    d.get("municipio"), d.get("sector"), d.get("insight"),
                    d.get("reasoning"), d.get("context_snippet"),
                    1 if is_grounded else 0, sources_json,
                    score, d.get("COORDENADAS") or d.get("coordenadas")
                ))

            # ── SYNC EN TIEMPO REAL A SUPABASE ────────────────────────────────
            if supabase_client:
                try:
                    # Parsear alertas_noticias si viene como string JSON
                    alertas = d.get("alertas_noticias", [])
                    if isinstance(alertas, str):
                        try: alertas = json.loads(alertas)
                        except Exception: alertas = []

                    record = {
                        "id_proyecto":      pid,
                        "anio":             year,
                        "promovente":       d.get("promovente"),
                        "proyecto":         d.get("proyecto"),
                        "estado":           d.get("estado"),
                        "municipio":        d.get("municipio"),
                        "sector":           d.get("sector"),
                        "insight":          d.get("insight"),
                        "coordenadas":      d.get("COORDENADAS") or d.get("coordenadas"),
                        "poligono":         d.get("poligono"),
                        "grounded":         is_grounded,
                        "audit_status":     d.get("audit_status", "pending"),
                        "confidence_score": score,
                        "fuentes_web":      d.get("fuentes_web", []),
                        "sources":          d.get("fuentes_web", []),
                        "riesgo_civil":     d.get("riesgo_civil"),
                        "sancion_profepa":  d.get("sancion_profepa"),
                        "alertas_noticias": alertas if isinstance(alertas, list) else [],
                    }
                    # Eliminar campos None para evitar errores de tipo en Supabase
                    record = {k: v for k, v in record.items() if v is not None}

                    supabase_client.table("proyectos").upsert(
                        record, on_conflict="id_proyecto"
                    ).execute()
                    log.debug(f"    ☁️  Supabase sync OK → {pid}")
                except Exception as sb_err:
                    # No detener el agente si falla Supabase — solo loguear
                    log.warning(f"    ⚠️  Supabase sync falló para {pid}: {sb_err}")

        except Exception as e:
            log.error(f"  ❌ Error guardando en DB: {e}")

    def get_stats(self) -> dict:
        try:
            with sqlite3.connect(self.db_path) as conn:
                total = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
                grounded = conn.execute("SELECT COUNT(*) FROM projects WHERE grounded = 1").fetchone()[0]
                return {"total_db": total, "grounded_db": grounded}
        except Exception:
            return {"total_db": 0, "grounded_db": 0}

def sync_to_warehouse(log: logging.Logger):
    """
    Sincroniza los datos de SQLite a DuckDB para analítica de alto rendimiento.
    Estrategia 1: Automated Data Warehouse.
    """
    try:
        import duckdb
        warehouse_path = CONFIG["WORK_DIR"] / "zohar_warehouse.duckdb"
        con = duckdb.connect(str(warehouse_path))
        
        # Cargamos extensión de SQLite para DuckDB
        con.execute("INSTALL sqlite; LOAD sqlite;")
        
        # Importar datos de la base operacional (SQLite)
        # Usamos una vista o tabla temporal para el merge
        con.execute(f"ATTACH '{CONFIG['DB_FILE']}' AS ops (TYPE SQLITE);")
        
        # Crear tabla si no existe
        con.execute("CREATE TABLE IF NOT EXISTS warehouse_projects AS SELECT * FROM ops.projects WHERE 1=0")
        
        # Merge incremental
        con.execute("""
            INSERT INTO warehouse_projects 
            SELECT * FROM ops.projects 
            WHERE pid NOT IN (SELECT pid FROM warehouse_projects)
        """)
        
        log.info(f"📊 Warehouse: {con.execute('SELECT COUNT(*) FROM warehouse_projects').fetchone()[0]} registros en DuckDB.")
        con.close()
    except Exception as e:
        log.error(f"  ❌ Warehouse Error: {e}")

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

class PortalMetadataCache:
    """Cache persistente para evitar latencia extrema del portal SEMARNAT."""
    def __init__(self, cache_file: Path):
        self.path = cache_file
        self._cache: dict[str, Any] = {}
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                self._cache = json.loads(self.path.read_text())
            except Exception:
                self._cache = {}

    def get(self, pid: str) -> Optional[dict]:
        data = self._cache.get(pid)
        return data if data else None

    def set(self, pid: str, data: dict):
        if not data: return
        self._cache[pid] = data
        try:
            self.path.write_text(json.dumps(self._cache, indent=2))
        except Exception:
            pass

# ─────────────────────────────────────────────────────────
# GEOSPATIAL & HISTORICAL ADVISORS (Strategy 1 - Data Enrichment)
# ─────────────────────────────────────────────────────────
class GeospatialAdvisor:
    """Proporciona contexto sobre ordenamientos ecológicos aplicables."""
    def __init__(self, duck_conn):
        self.con = duck_conn
        self._load_data()

    def _load_data(self):
        csv_path = CONFIG["ORDENAMIENTOS_CSV"]
        if not csv_path.exists():
            logging.warning(f"⚠️ {csv_path} no encontrado")
            return
        
        try:
            # Cargar CSV a DuckDB si está vacío
            count = self.con.execute("SELECT COUNT(*) FROM environmental_zoning").fetchone()[0]
            if count == 0:
                # Usamos read_csv_auto con skip=1 si es necesario, o dejamos que duckdb lo detecte
                self.con.execute(f"INSERT INTO environmental_zoning SELECT * FROM read_csv_auto('{csv_path}', header=True)")
                new_count = self.con.execute("SELECT COUNT(*) FROM environmental_zoning").fetchone()[0]
                logging.info(f"📍 GeospatialAdvisor: {new_count} programas cargados.")
        except Exception as e:
            logging.error(f"❌ Error al cargar ordenamientos: {e}")

    def get_applicable_programs(self, estado: str, municipio: str = "") -> List[dict]:
        """Busca programas de ordenamiento aplicables por estado y municipio."""
        if not estado: return []
        
        query = "SELECT * FROM environmental_zoning WHERE estado ILIKE ?"
        params = [f"%{estado}%"]
        
        if municipio:
            query += " OR programa ILIKE ?"
            params.append(f"%{municipio}%")
            
        try:
            res = self.con.execute(query, params).fetchall()
            cols = [d[0] for d in self.con.description]
            return [dict(zip(cols, row)) for row in res]
        except Exception:
            return []

class HistoricalConsultationAdvisor:
    """Busca antecedentes en el portal de consultas públicas."""
    def __init__(self, duck_conn):
        self.con = duck_conn
        self._load_local_cache()

    def _load_local_cache(self):
        json_path = CONFIG["HISTORIC_DATA_JSON"]
        if not json_path.exists(): return
        
        try:
            # TONL-C2: Verificar si ya hay datos antes de intentar insertar 13k+ registros
            count = self.con.execute("SELECT COUNT(*) FROM historic_consultations").fetchone()[0]
            if count > 0:
                logging.info(f"📋 HistoricalAdvisor: {count} registros ya en DuckDB (skip reload)")
                return

            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Upsert incremental
            for entry in data:
                self.con.execute("""
                    INSERT OR IGNORE INTO historic_consultations 
                    (clave, modalidad, promovente, proyecto, ubicacion, sector, fechas, anio, links)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    entry.get("clave"), entry.get("modalidad"), entry.get("promovente"),
                    entry.get("proyecto"), entry.get("ubicacion"), entry.get("sector"),
                    entry.get("fechas"), entry.get("anio"), json.dumps(entry.get("links"))
                ])
        except Exception as e:
            logging.error(f"❌ Error al cargar histórico: {e}")

    def find_by_pid(self, pid: str) -> Optional[dict]:
        try:
            res = self.con.execute("SELECT * FROM historic_consultations WHERE clave = ?", [pid]).fetchone()
            if res:
                cols = [d[0] for d in self.con.description]
                return dict(zip(cols, res))
        except Exception:
            pass
        return None

class AirQualityAdvisor:
    """Proporciona datos sobre emisiones atmosféricas históricas por municipio."""
    def __init__(self, duck_conn):
        self.con = duck_conn
        self._load_data()

    def _load_data(self):
        csv_path = CONFIG["AIR_QUALITY_CSV"]
        if not csv_path.exists():
            logging.warning(f"⚠️ {csv_path} no encontrado")
            return
        
        try:
            count = self.con.execute("SELECT COUNT(*) FROM air_quality_emissions").fetchone()[0]
            if count == 0:
                self.con.execute(f"INSERT INTO air_quality_emissions SELECT * FROM read_csv_auto('{csv_path}', header=True)")
                new_count = self.con.execute("SELECT COUNT(*) FROM air_quality_emissions").fetchone()[0]
                logging.info(f"💨 AirQualityAdvisor: {new_count} registros de emisiones cargados.")
        except Exception as e:
            logging.error(f"❌ Error al cargar aire: {e}")

    def get_aggregated_emissions(self, municipio: str, entidad: str = "") -> dict:
        """Devuelve promedios y máximos históricos resumidos (Optimización TONL)."""
        query = """
            SELECT 
                AVG(so2) as avg_so2, MAX(so2) as max_so2,
                AVG(nox) as avg_nox, MAX(nox) as max_nox,
                AVG(pm2_5) as avg_pm25, MAX(pm2_5) as max_pm25
            FROM air_quality_emissions 
            WHERE municipio ILIKE ?
        """
        params = [f"%{municipio}%"]
        if entidad:
            query += " AND entidad ILIKE ?"
            params.append(f"%{entidad}%")
        
        try:
            res = self.con.execute(query, params).fetchone()
            if not res or res[0] is None: return {}
            return {
                "avg": {"so2": round(res[0], 2), "nox": round(res[2], 2), "pm25": round(res[4], 2)},
                "max": {"so2": round(res[1], 2), "nox": round(res[3], 2), "pm25": round(res[5], 2)}
            }
        except Exception:
            return {}

    def generate_environmental_report(self, municipio: str, project_id: str) -> dict:
        """Genera un reporte ejecutivo con lógica de despacho dual (HITL)."""
        data = self.get_aggregated_emissions(municipio)
        if not data: 
            return {
                "timestamp": datetime.datetime.now().isoformat(),
                "cycle_2026": True,
                "pid": project_id,
                "execution_path": "SKIPPED_NO_DATA"
            }

        # Límites NOM (Placeholders técnicos)
        # NOM-025-SSA1-2021: PM2.5 límite anual 10 µg/m³ (usamos 25 como límite de alerta 24h)
        THRESHOLDS = {"so2": 40.0, "nox": 70.0, "pm25": 25.0}
        violations = []
        risk_score = 0

        for m, limit in THRESHOLDS.items():
            current = data["avg"].get(m, 0)
            if current > limit:
                excess_pct = ((current - limit) / limit) * 100
                violations.append({"metric": m, "value": current, "limit": limit, "excess_pct": round(excess_pct, 2)})
                risk_score += excess_pct

        # Regla de Negocio: >20% exceso en cualquier métrica -> Firma Manual
        path = "AUTONOMOUS"
        if any(v["excess_pct"] > 20 for v in violations) or risk_score > 50:
            path = "CRITICAL_SIGNATURE_REQUIRED"

        return {
            "timestamp": datetime.datetime.now().isoformat(),
            "cycle_2026": True,
            "pid": project_id,
            "metrics": data,
            "violations": violations,
            "risk_score": round(risk_score, 2),
            "execution_path": path
        }

# Instancias Globales
memory: Optional[LocalIntelligenceMemory] = None
prompts: Optional[PromptManager] = None
portal_cache: Optional[PortalMetadataCache] = None
geospatial: Optional[GeospatialAdvisor] = None
historical: Optional[HistoricalConsultationAdvisor] = None
air_quality: Optional[AirQualityAdvisor] = None

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
TODA TU SALIDA DEBE SER EN ESPAÑOL.
</system_instruction>

<schema_definition>
{{
  "PROMOVENTE": "Entidad legal o persona responsable (nombre prístino).",
  "PROYECTO": "Título oficial del proyecto (eliminar encabezados de tabla).",
  "ESTADO": "Nombre completo del estado mexicano (sin abreviaturas).",
  "MUNICIPIO": "Municipio específico.",
  "LOCALIDAD": "Sitio específico o localidad.",
  "COORDENADAS": "Latitud/Longitud exactamente como están escritas.",
  "POLIGONO": "Vértices geométricos si están disponibles.",
  "SECTOR": "Uno de: [ENERGÍA, MINERÍA, TURISMO, INFRAESTRUCTURA, HIDROCARBUROS, AGROINDUSTRIA, OTROS].",
  "INSIGHT": "Resumen de Inteligencia Estructurado (2-3 oraciones). Comienza con un VERBO DE ACCIÓN en español. Enfócate en la arquitectura de riesgo ambiental."
}}
</schema_definition>

<governance_rules>
1. MANDATO DE FUNDAMENTACIÓN: Cada campo debe derivarse del TEXTO PROPORCIONADO. Si los datos son ambiguos, DÉJALOS VACÍOS.
2. CERO ALUCINACIÓN: Términos prohibidos: [DESCONOCIDO, NA, NULL, ID_PROYECTO, EL ID, NOMBRE ESPECIFICO].
3. ENFOQUE EN INFRAESTRUCTURA: Extrae para la durabilidad. No adivines. No "resumas" - MODELA los datos.
4. OBLIGACIÓN DE DOBLE COMILLA: La salida DEBE ser un único objeto JSON. Todas las claves y valores deben estar entre comillas dobles.
5. IDIOMA: Genera el INSIGHT y cualquier texto descriptivo estrictamente en ESPAÑOL.
</governance_rules>

<chain_of_thought_analysis>
Identifica el PID objetivo: {pid}.
Paso 1: Localiza el ancla del proyecto en el texto.
Paso 2: Aísla la estructura de celdas circundante para separar los encabezados de metadatos de los valores reales.
Paso 3: Verifica que el 'Promovente' tenga una estructura legal (S.A. de C.V., C.P., etc.) o un nombre personal claro.
Paso 4: Comprueba el código del Estado desde {pid} (primeros 2 dígitos) con el texto extraído.
Paso 5: Sintetiza un Insight de alta fidelidad en ESPAÑOL basado en la escala y sector del proyecto.
</chain_of_thought_analysis>

<location_context_snippet>
{location_snippet}
</location_context_snippet>

<full_text_context>
{context}
</full_text_context>

REQUERIMIENTO DE SALIDA:
Genera un bloque detallado de <razonamiento> en español seguido de un bloque limpio <output_json> que contenga solo el JSON.
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
        log.info(f"🌡️ {t}°C → enfriamiento {CONFIG['COOL_DOWN_HOT']}s")
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
                        log.info("Infraestructura de LLM validada con éxito")
                    return True
        except Exception:
            pass
        if i == 0:
            log.warning("Latencia detectada en servicio LLM - esperando respuesta...")
        time.sleep(5)
    log.error("Servicio LLM no disponible (verificar: curl http://127.0.0.1:8001/v1/models)")
    return False


# ─────────────────────────────────────────────────────────
# HTTP HELPER (Async con pool)
# ─────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Accept": "text/html,application/pdf,*/*",
}

async def http_get(url: str, timeout: int = 45, binary: bool = False):
    """
    GET asíncrono robusto usando la piscina global http_client.
    """
    global http_client
    if http_client is None:
        http_client = httpx.AsyncClient(headers=HEADERS, timeout=timeout, follow_redirects=True)
    
    MAX_RETRY = 2
    for attempt in range(MAX_RETRY + 1):
        try:
            resp = await http_client.get(url)
            resp.raise_for_status()
            return resp.content if binary else resp.text
        except Exception as e:
            if attempt < MAX_RETRY:
                await asyncio.sleep(2 * (attempt + 1))
                continue
            return None
    return None

def http_get_sync(url: str, timeout: int = 45, binary: bool = False):
    """Fallback síncrono para lugares donde no se puede usar await."""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
            return data if binary else data.decode("utf-8", errors="replace")
    except Exception:
        return None


# ─────────────────────────────────────────────────────────
# ESTADO del agente (visible en el dashboard :8081)
# ─────────────────────────────────────────────────────────
def get_perf_metrics():
    """Obtiene métricas de rendimiento del sistema local (Ryzen 5)."""
    cpu_temp = "N/A"
    uptime_str = "N/A"
    llama_ok = False
    disk_avail = "N/A"
    mem_used = 0
    
    try:
        # CPU Temp (sensors)
        try:
            sensors = subprocess.check_output(['sensors'], stderr=subprocess.STDOUT).decode()
            match = re.search(r'(?:CPU|temp1|Tdie):\s+\+?([\d.]+)', sensors)
            if match: cpu_temp = f"{match.group(1)}°C"
        except: pass
        
        # Uptime (/proc/uptime)
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.readline().split()[0])
                hrs = int(uptime_seconds // 3600)
                mins = int((uptime_seconds % 3600) // 60)
                secs = int(uptime_seconds % 60)
                uptime_str = f"{hrs:02}:{mins:02}:{secs:02}"
        except: pass
        
        # Llama Health
        try:
            with urllib.request.urlopen(CONFIG["LLAMA_HEALTH"], timeout=2) as r:
                llama_ok = (r.status == 200)
        except: pass

        # Disk Avail
        try:
            import shutil
            _, _, free = shutil.disk_usage("/")
            disk_avail = f"{free // (2**30)} GB Available"
        except: pass

        # Mem Used
        try:
            if os.path.exists("/proc/meminfo"):
                with open("/proc/meminfo", "r") as f:
                    lines = f.readlines()
                    total = int(lines[0].split()[1])
                    available = int(lines[2].split()[1])
                    mem_used = int(((total - available) / total) * 100)
        except: pass
            
    except Exception: pass
    return cpu_temp, uptime_str, llama_ok, disk_avail, mem_used

def rotate_logs():
    """Rota el archivo de logs si excede el tamaño máximo."""
    log_file = CONFIG["LOG_FILE"]
    if log_file.exists() and log_file.stat().st_size > CONFIG["MAX_LOG_SIZE_MB"] * 1024 * 1024:
        try:
            backup = log_file.with_suffix(".jsonl.bak")
            log_file.rename(backup)
            # El logger volverá a crear el archivo en la siguiente escritura
        except Exception:
            pass

def get_system_load() -> float:
    """Retorna el load average del sistema (1 min)."""
    try:
        return os.getloadavg()[0]
    except Exception:
        return 0.0

def report_state(pdf: str, action: str, target: str, message: str = ""):
    cpu_temp, uptime_str, llama_ok, disk_avail, mem_used = get_perf_metrics()
    state = {
        "pdf":    pdf,
        "action": action,
        "target": target,
        "time":   datetime.datetime.now().strftime("%H:%M:%S"),
        "cpu_temp": cpu_temp,
        "uptime":   uptime_str,
        "llama_ok": llama_ok,
        "disk_avail": disk_avail,
        "mem_used": mem_used
    }
    try:
        CONFIG["STATE_FILE"].write_text(json.dumps(state))
        
        # Estrategia A: Espejo en Tiempo Real (Heartbeat a Supabase)
        if supabase_client:
            def _sync_cloud_state(s):
                try:
                    # Usamos id fijo 1 para que sea un registro único de monitoreo
                    payload = {
                        "server_name": s["server_name"] if "server_name" in s else CONFIG["SERVER_NAME"],
                        "pdf": s["pdf"],
                        "action": s["action"],
                        "target": s["target"],
                        "cpu_temp": s["cpu_temp"],
                        "uptime": s["uptime"],
                        "llama_ok": s["llama_ok"],
                        "disk_avail": s["disk_avail"],
                        "mem_used": s["mem_used"],
                        "agent_alive": True,
                        "last_seen": datetime.datetime.now().isoformat()
                    }
                    if supabase_client:
                        try:
                            # Upsert por server_name (que es único ahora)
                            supabase_client.table("agente_status").upsert(payload, on_conflict="server_name").execute()
                        except Exception as e:
                            # Loguear error de Supabase si es necesario, pero no detener
                            pass
                except Exception:
                    pass
            
            import threading
            threading.Thread(target=_sync_cloud_state, args=(state,), daemon=True).start()
            
    except Exception:
        pass

def is_dashboard_alive() -> bool:
    """Verifica si el dashboard está abierto basándose en el archivo de heartbeat."""
    hb_file = CONFIG["HEARTBEAT_FILE"]
    if not hb_file.exists():
        return False
    try:
        mtime = hb_file.stat().st_mtime
        return (time.time() - mtime) < CONFIG["HEARTBEAT_TIMEOUT"]
    except Exception:
        return False

def check_pause_flag() -> bool:
    """Verifica si el agente debe pausarse según la bandera en Supabase."""
    if not supabase_client:
        return False
    try:
        # Prioridad 1: Pausa global (id=1 o server_name='GLOBAL')
        # Prioridad 2: Pausa específica de este servidor
        res = supabase_client.table("agente_status").select("is_paused").or_(f"id.eq.1,server_name.eq.{CONFIG['SERVER_NAME']}").execute()
        if res.data:
            # Si cualquiera de los registros encontrados dice paused=True, nos pausamos
            return any(r.get("is_paused", False) for r in res.data)
    except Exception:
        pass
    return False

def record_usage(model: str, prompt_tokens: int, completion_tokens: int):
    """Registra el uso de tokens en Supabase."""
    if not supabase_client:
        return
    
    total = prompt_tokens + completion_tokens
    # Estimación simple de costo (ajustar según modelo)
    # Gemini Flash: $0.1 / 1M input, $0.4 / 1M output (aprox)
    # Llama local: $0 (pero lo registramos para consumo de recursos)
    cost = 0.0
    if "gemini" in model.lower():
        cost = (prompt_tokens * 0.1 / 1_000_000) + (completion_tokens * 0.4 / 1_000_000)
    
    payload = {
        "server_name": CONFIG["SERVER_NAME"],
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total,
        "estimated_cost": cost
    }
    
    def _sync_usage():
        try:
            supabase_client.table("ai_usage").insert(payload).execute()
        except Exception:
            pass
            
    import threading
    threading.Thread(target=_sync_usage, daemon=True).start()


# ─────────────────────────────────────────────────────────
# PASO 1: MONITOR — detectar nuevas Gacetas
# ─────────────────────────────────────────────────────────
async def fetch_pdf_links(year: int, seen: SeenGacetas, log: logging.Logger) -> list[str]:
    """
    Descarga el índice de gacetas del año y retorna lista de
    URLs de PDF usando Selenium y Pandas para garantizar recolección.
    """
    url = CONFIG["GACETA_LIST_URL"].format(year=year)
    report_state("—", "MONITOREANDO", f"Gaceta {year} (Selenium)")
    log.info(f"🔍 Verificando Gaceta {year} (HTTP First): {url}")
    
    async def _get_html():
        html = await http_get(url, timeout=60)
        
        if html is None or "document.write" in html or len(html) < 500:
            log.warning(f"  ⚠️ HTTP insuficiente o JS detectado, usando Selenium (Pesado)...")
            try:
                chrome_options = Options()
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.binary_location = '/usr/bin/google-chrome-stable'
                driver_path = "/usr/bin/chromedriver"
                if not os.path.exists(driver_path): driver_path = "/usr/local/bin/chromedriver"
                
                service = Service(executable_path=driver_path)
                driver = webdriver.Chrome(service=service, options=chrome_options)
                driver.set_page_load_timeout(45)
                driver.get(url)
                time.sleep(5)
                src = driver.page_source
                driver.quit()
                return src
            except Exception as e:
                log.warning(f"  ❌ Fallo total: no se pudo acceder a la Gaceta {year} ({e})")
                return None
        return html

    # Corregir la llamada a to_thread ya que _get_html ahora es async
    html = await _get_html()
    if not html:
        return []

    # Extraer links usando regex
    found = PDF_LINK_PATTERN.findall(html)
    pdf_links = [f"http://sinat.semarnat.gob.mx/Gacetas/{l}" for l in found]

    if not pdf_links:
        return []

    # TONL-C4: Usar sorted reverse=True para ir de lo más reciente para atrás
    pdf_links = sorted(set(pdf_links), reverse=True)
    log.info(f"  📄 {len(pdf_links)} PDFs encontrados usando métodos avanzados.")
    return pdf_links


# ─────────────────────────────────────────────────────────
# PASO 2: DISCOVER — descargar PDF, extraer IDs
# ─────────────────────────────────────────────────────────
# TONL-C3: Cache de PIDs del CSV en memoria como set para O(1) lookup
_pid_csv_cache: Optional[set] = None

def _build_pid_csv_cache():
    """Carga el CSV de histórico UNA sola vez en un set para búsquedas rápidas."""
    global _pid_csv_cache
    p = CONFIG["CSV_FILE"]
    if not p.exists():
        _pid_csv_cache = set()
        return
    try:
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            next(reader, None)  # Saltar cabecera
            _pid_csv_cache = {row[1].strip() for row in reader if len(row) > 1}
        logging.getLogger("zohar").info(f"📂 CSV PID cache: {len(_pid_csv_cache)} registros indexados")
    except Exception as e:
        logging.getLogger("zohar").error(f"  ⚠️ Error construyendo cache CSV: {e}")
        _pid_csv_cache = set()

def pid_in_csv(pid: str) -> bool:
    """Busca el PID en el cache en memoria O(1). Cachea en el primer uso."""
    global _pid_csv_cache
    if _pid_csv_cache is None:
        _build_pid_csv_cache()
    return pid.strip() in _pid_csv_cache

async def process_pdf(pdf_url: str, year: int, queue: PersistentQueue,
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
        data = await http_get(pdf_url, timeout=90, binary=True)
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
    all_ids = sorted(set(ID_PATTERN.findall(txt)))
    # Filtro estricto: Enfocarse únicamente en proyectos de Ensenada (Baja California = código '02')
    ids = [pid for pid in all_ids if "2026" in pid and pid.startswith("02")]

    MAX_IDS_PER_PDF = 10 # No saturar la cola, avanzar gradual
    new_count: int = 0
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
                coords.append(str(f"{d:.5f}"))
            return ", ".join(coords)
        return text

    raw_coord = _normalize_coords(raw_coord)
    
    # 2. Forzar Estado correcto según los 2 primeros dígitos del PID (Standard SEMARNAT)
    state_code = str(pid)[:2]
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
             data["insight"] = f"Análisis técnico del proyecto: {str(proj_title)[:150]}..."
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
            ai_is_deficient = len(ai_val or "") < 4
            portal_enriches = len(official_val or "") > len(ai_val or "") + 5
            if ai_is_deficient or portal_enriches:
                if len(ai_val) > 3:
                    log.debug(f"    Grounding {target}: '{ai_val}' -> '{official_val}'")
                extracted[target] = official_val
    
    # ── ENRIQUECIMIENTO GEOSPATIAL ────────────────────────────────
    if geospatial:
        estado = extracted.get("estado", "")
        municipio = extracted.get("municipio", "")
        programs = geospatial.get_applicable_programs(estado, municipio)
        if programs:
            extracted["ordenamientos_aplicables"] = [p["programa"] for p in programs[:3]]
            log.debug(f"    📍 Geospatial Grounding: {len(programs)} programas hallados")

    # ── ANTECEDENTES HISTÓRICOS ──────────────────────────────────
    # Se ha eliminado la base de datos histórica a petición del usuario.


    # ── CALIDAD DEL AIRE ────────────────────────────────────────
    if air_quality:
        mun = extracted.get("municipio", "")
        ent = extracted.get("estado", "")
        profile = air_quality.get_emissions_profile(mun, ent)
        if profile:
            # Resumir emisiones críticas (ej. NOx y PM2.5 de fuentes fijas)
            fixed_source = next((p for p in profile if "fijas" in p["tipo_fuente"].lower()), None)
            if fixed_source:
                extracted["emisiones_criticas_zona"] = {
                    "SO2": fixed_source["so2"],
                    "NOx": fixed_source["nox"],
                    "PM2.5": fixed_source["pm2_5"]
                }
                log.debug(f"    💨 Air Quality Grounding: Perfil hallado para {mun}")

    return extracted

# Los prompts se cargarán dinámicamente usando PromptManager





async def _llm_call(messages: list, max_tokens: int = None, stop: Optional[List[str]] = None, log: Optional[logging.Logger] = None) -> Optional[str]:
    """
    Llamada asíncrona al LLM en formato OpenAI chat/completions.
    TONL-C1: Reutiliza http_client global para evitar TCP handshake por llamada.
    """
    global http_client
    if http_client is None:
        http_client = httpx.AsyncClient(headers=HEADERS, timeout=CONFIG["LLAMA_TIMEOUT"], follow_redirects=True)

    # TONL-A2: Usar max_tokens especializados si no se especifica
    if max_tokens is None:
        max_tokens = CONFIG["MAX_TOKENS_EXTRACT"]

    payload = {
        "model":       CONFIG["MODEL"],
        "messages":    messages,
        "temperature": CONFIG["TEMPERATURE"],
        "max_tokens":  max_tokens,
    }
    # Stops recomendados para modelos estilo Mistral/llama.cpp
    default_stops = ["</output_json>", "</razonamiento>"]
    if stop:
        payload["stop"] = stop + default_stops
    else:
        payload["stop"] = default_stops

    try:
        resp = await http_client.post(CONFIG["LLAMA_URL"], json=payload)
        resp.raise_for_status()
        data = resp.json()
        
        # Registrar consumo
        usage = data.get("usage", {})
        if usage:
            record_usage(CONFIG["MODEL"], usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
            
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        if log:
            log.warning(f"    Error en llamada LLM: {e}")
        return None


def extract_with_gemini(pid: str, context: str, log: logging.Logger) -> Optional[dict]:
    """
    Extracción Élite con Gemini Pro + Google Search Grounding.
    """
    if not gemini_client:
        return None

    # ── CACHÉ SEMÁNTICA (STRATEGY 1) ──────────────────────────────────
    fragment_hash = hashlib.sha256(context.encode()).hexdigest()
    cached_row = duck_conn.execute("SELECT result FROM fragments_cache WHERE hash = ?", [fragment_hash]).fetchone()
    if cached_row:
        log.info(f"    🎯 Cache Hit (Semantic) para {pid}")
        return json.loads(cached_row[0])

    try:
        # ── BÚSQUEDA WEB PROFUNDA (Feature 1: Deep Grounding + Civil Alerts) ──
        # Extraer promovente básico del contexto para búsqueda dirigida
        promovente_hint = ""
        for line in context.split("\n"):
            l = line.lower()
            if "promovente" in l or "empresa" in l:
                promovente_hint = line.strip()
                break

        prompt = f"""
        Actúa como un Líder de Inteligencia Senior de Esoteria. Tu misión es auditar y verificar el proyecto {pid}
        utilizando Google Search de forma EXHAUSTIVA para obtener datos reales y detectar señales de riesgo.
        TODA LA SALIDA DEBE SER EN ESPAÑOL.

        CONTEXTO (NO VERIFICADO):
        {context}

        PROTOCOLO DE INVESTIGACIÓN DE 3 CAPAS (ejecuta TODAS usando Google Search):

        CAPA 1 — VERIFICACIÓN BASE:
        Busca en Google: '{pid} SEMARNAT MIA' y '{promovente_hint} impacto ambiental México'
        Confirma: ¿Existe el proyecto? ¿Coincide ubicación, sector y nombre del promovente?

        CAPA 2 — INTELIGENCIA DE RIESGO CIVIL (NUEVO):
        Busca: '{promovente_hint} oposición vecinal' | '{promovente_hint} manifestación ambiental' |
               '{promovente_hint} amparo ambiental' | 'proyecto {pid} comunidades'
        Si encuentras noticias de conflicto social, captúralas en 'alertas_noticias'.

        CAPA 3 — AUDITORÍA PROFEPA (NUEVO):
        Busca: '{promovente_hint} PROFEPA multa sanción' | '{promovente_hint} clausura ambiental' |
               '{promovente_hint} inspección federal'
        Si hay antecedentes de sanción, captúralos en 'sancion_profepa'.

        REGLAS DE GOBERNANZA:
        1. insight: 2-3 oraciones en español empezando con verbo de acción resumiendo hallazgos clave.
        2. riesgo_civil: "ALTO" | "MEDIO" | "BAJO" | "NINGUNO" — según oposición encontrada.
        3. sancion_profepa: descripción breve de la sanción o "Sin antecedentes".
        4. alertas_noticias: lista de titulares encontrados (o lista vacía []).
        5. JSON VÁLIDO OBLIGATORIO. Usa null para campos sin datos.
        6. IDIOMA: Todo en ESPAÑOL.
        7. coordenadas: Si encuentras lat/lon en fuentes, inclúyelas en formato "LAT, LON".

        SCHEMA (devuelve SOLO este JSON, sin markdown):
        {{
          "estado": "string",
          "municipio": "string",
          "localidad": "string",
          "proyecto": "string",
          "promovente": "string",
          "sector": "string",
          "insight": "string",
          "coordenadas": "string",
          "poligono": "string",
          "riesgo_civil": "ALTO|MEDIO|BAJO|NINGUNO",
          "sancion_profepa": "string",
          "alertas_noticias": ["titular 1", "titular 2"]
        }}
        """

        # Definición explícita de genai.types.Tool con Google Search
        search_tool = types.Tool(
            google_search=types.GoogleSearch()
        )

        response = gemini_client.models.generate_content(
            model=CONFIG["GEMINI_MODEL"],
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[search_tool]
            )
        )

        raw = response.text
        
        # Registrar consumo Gemini
        if response.usage_metadata:
            record_usage(
                CONFIG["GEMINI_MODEL"], 
                response.usage_metadata.prompt_token_count, 
                response.usage_metadata.candidates_token_count
            )

        # Extracción JSON robusta para evitar "Expecting value: line 1 column 1"
        json_match = None
        m = re.search(r'```json\s*(.*?)\s*```', raw, re.DOTALL)
        if m:
            json_match = m.group(1).strip()
        
        if not json_match:
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                json_match = raw[start : end + 1].strip()

        if not json_match:
            log.warning("    Gemini devolvió una estructura inválida, recurriendo a Mistral.")
            return None

        extracted = json.loads(json_match)
        if isinstance(extracted, list) and len(extracted) > 0:
            extracted = extracted[0]
            
        if not isinstance(extracted, dict):
            log.warning(f"    Gemini devolvió un formato inválido: {type(extracted)}")
            return None

        # Normalizar claves y valores (convertir a str excepto listas de fuentes)
        extracted = {k.lower().strip(): v for k, v in extracted.items()}
        for k, v in extracted.items():
            if k != "fuentes_web":
                extracted[k] = str(v).strip()

        # Capturar fuentes de Grounding
        fuentes = []
        if response.candidates and response.candidates[0].grounding_metadata:
            meta = response.candidates[0].grounding_metadata
            log.debug(f"    [Gemini-Grounding] Metadatos hallados: {meta}")
            
            # Opción 1: grounding_chunks
            if meta.grounding_chunks:
                for chunk in meta.grounding_chunks:
                    if chunk.web:
                        fuentes.append({
                            "uri": chunk.web.uri,
                            "title": getattr(chunk.web, 'title', 'Fuente Externa')
                        })
            
            # Fallback a parsear rendered_content (HTML chips)
            if not fuentes and hasattr(meta, 'search_entry_point') and meta.search_entry_point:
                html = meta.search_entry_point.rendered_content
                found = re.findall(r'href="(https://[^"]+)"', html)
                if found:
                    for url in found:
                        if not any(f["uri"] == url for f in fuentes):
                            fuentes.append({"uri": url, "title": "Portal de Transparencia / Google Search"})
            
        if fuentes:
            extracted["fuentes_web"] = fuentes
            log.info(f"    ✨ Grounding exitoso: {len(fuentes)} fuentes halladas")

        # Guardar en caché semántica
        duck_conn.execute("INSERT OR IGNORE INTO fragments_cache (hash, result) VALUES (?, ?)", 
                         [fragment_hash, json.dumps(extracted)])

        return extracted

    except Exception as e:
        log.warning(f"    Gemini Error: {e}")
        return None


# ── PIPELINE DE EXTRACCIÓN (DOCTORAL) ─────────────────────
async def _extract_with_ai_async(pid: str, context: str, log: logging.Logger, pdf_name: str = "—") -> Optional[dict]:
    """
    Pipeline de extracción híbrido.
    1. Intenta Gemini (Élite + Grounding por Chunks).
    2. Si falla, cae a Mistral Local (estándar Doctoral).
    """

    # ── INTENTO ÉLITE: Gemini + Grounding ────────────────────────────────
    if gemini_client:
        log.info(f"    ✨ Intentando extracción Élite (Gemini + Grounding) para {pid}")
        extracted = extract_with_gemini(pid, context, log)
        if extracted:
            return extracted

    # ── FALLBACK: Mistral Local (PASO 1 + PASO 2) ────────────────────────
    log.info(f"    🔄 Recurriendo a Inferencia Local (Mistral) para {pid}")
    
    # Cargar prompts dinámicamente
    loc_finder_template = prompts.get_prompt("location_finder", DEFAULT_LOC_FINDER) if prompts else DEFAULT_LOC_FINDER
    ext_template = prompts.get_prompt("extraction_v2", DEFAULT_EXTRACTION_PROMPT) if prompts else DEFAULT_EXTRACTION_PROMPT

    # ── PASO 1: Location Finder (Desambiguación Preliminar) ─────────────
    loc_prompt = loc_finder_template.format(pid=pid, context=context)
    location_snippet = await _llm_call(
        messages=[{"role": "user", "content": loc_prompt}],
        max_tokens=400,
        log=log,
    ) or "NO_HALLADO"

    log.debug(f"    [Loc-Finder] Fragmento: {str(location_snippet)[:100]!r}...")

    # ── PASO 2: Extracción Doctoral con CoT ─────────────────────────────
    ext_prompt = ext_template.format(
        pid=pid,
        location_snippet=location_snippet,
        context=str(context)[:CONFIG["CONTEXT_CHARS"]],
    )

    for attempt in range(1, CONFIG["MAX_RETRIES"] + 1):
        raw = await _llm_call(
            messages=[
                {
                    "role": "system",
                    "content": "Eres un Arquitecto de Inteligencia de Esoteria. Tu salida DEBE ser un bloque <razonamiento> y un bloque <output_json>."
                },
                {"role": "user", "content": ext_prompt},
            ],
            max_tokens=CONFIG["MAX_TOKENS"],
            log=log,
        )

        if not raw:
            log.warning(f"    Anomalía de inferencia (intento {attempt})")
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
                json_match = str(raw)[start : end + 1].strip()
        
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
                log.debug(f"    Alerta del Auditor JSON (intento {attempt}): {e} — fragmento: {str(json_match)[:100]!r}")
                time.sleep(2)
                continue

        log.debug(f"    No se encontró bloque JSON en la respuesta (intento {attempt})")
        time.sleep(2)

    return None


def extract_with_ai(pid: str, context: str, log: logging.Logger, pdf_name: str = "—") -> Optional[dict]:
    """
    Wrapper síncrono para compatibilidad con la suite de tests (pytest).
    Internamente delega al pipeline asíncrono.
    """
    import asyncio

    return asyncio.run(_extract_with_ai_async(pid, context, log, pdf_name))



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
async def fetch_portal_docs(pid: str, log: logging.Logger) -> dict:
    """
    Consulta la API del portal SEMARNAT con reintentos robustos (Backoff Exponencial).
    Implementa SRE strategy del Codex Cap 10.2.
    """
    api_url = CONFIG["PORTAL_API_BASE"] + urllib.parse.quote(pid)
    
    for attempt in range(1, 4):
        log.info(f"  🌐 Portal: consultando {pid} (Intento {attempt})")
        content = await http_get(api_url, timeout=35 * attempt) # Timeout creciente
        
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
    # download_document no es async en este contexto para simplificar, pero usamos call asíncrono interno
    data = http_get_sync(doc_url, timeout=120, binary=True)
    if data and data[:4] == b'%PDF':
        save_path.write_bytes(data)
        log.info(f"  ✅ Guardado: {save_path}")
        return save_path
    else:
        log.warning(f"  ⚠️ Respuesta inválida para {doc_type} ({pid})")
        return None


async def extract_with_vision(pid: str, year: int, pdf_name: str, log: logging.Logger) -> Optional[dict]:
    """Extrae datos usando Gemini Vision (multimodal) para OCR + Análisis."""
    if not gemini_client:
        return None
        
    try:
        work_dir = CONFIG["WORK_DIR"] / str(year)
        pdf_path = work_dir / pdf_name
        if not pdf_path.exists(): return None
        
        log.info(f"  👁️  Activando Gemini Vision para {pid}...")
        
        if 'convert_from_path' not in globals():
            log.warning("  ⚠️ pdf2image/poppler no disponible")
            return None

        # Escanear páginas: 1-3 para texto, página 1 para mapa/croquis
        images = convert_from_path(str(pdf_path), first_page=1, last_page=4, dpi=200)

        full_text = ""
        geo_coords = None

        from io import BytesIO
        for i, img in enumerate(images):
            img.thumbnail((2000, 2000))
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=85)
            img_bytes = buf.getvalue()
            img_part = types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")

            # ── CAPA 1: Extracción de texto ──────────────────────────────────
            response_text = gemini_client.models.generate_content(
                model='gemini-3-flash-preview',
                contents=[
                    "Extrae TODO el texto visible en esta página de la Gaceta SEMARNAT. "
                    "Preserva formato de tablas. Si hay coordenadas geográficas (UTM, decimal o DMS), inclúyelas.",
                    img_part
                ]
            )
            if response_text.text:
                full_text += f"\n--- PÁGINA {i+1} ---\n{response_text.text}"

            # ── CAPA 2: Extractor de Coordenadas por Visión (Feature 2) ─────
            # Solo analizar imágenes que parecen contener mapas (generalmente páginas 2-4)
            if i >= 1 and geo_coords is None:
                response_geo = gemini_client.models.generate_content(
                    model='gemini-3-flash-preview',
                    contents=[
                        """Analiza esta imagen. Si contiene un mapa, croquis de ubicación, polígono o
                        coordenadas geográficas de cualquier sistema (decimal, DMS, UTM):
                        1. Extrae las coordenadas del punto central o centroide del área del proyecto.
                        2. Convierte al formato decimal: LAT, LON (ej: 19.4326, -99.1332).
                        3. Si hay un polígono, extrae los vértices como lista de pares LAT,LON.
                        4. Si NO hay mapa ni coordenadas, responde exactamente: NO_MAPA
                        Responde SOLO con el JSON: {"lat_lon": "LAT, LON", "poligono": [[lat,lon],...]} o NO_MAPA""",
                        img_part
                    ]
                )
                if response_geo.text and "NO_MAPA" not in response_geo.text:
                    raw_geo = response_geo.text.strip()
                    try:
                        # Extraer JSON del resultado de visión
                        gm = re.search(r'\{.*\}', raw_geo, re.DOTALL)
                        if gm:
                            geo_data = json.loads(gm.group(0))
                            geo_coords = geo_data.get("lat_lon")
                            if geo_coords:
                                log.info(f"  🗺️  Coordenadas extraídas por Visión para {pid}: {geo_coords}")
                    except Exception:
                        pass

        if not full_text:
            log.warning(f"  ⚠️ No se obtuvo inteligencia visual para {pid}")
            return None

        # Añadir coordenadas al contexto si se encontraron
        if geo_coords:
            full_text += f"\n\n[COORDENADAS EXTRAÍDAS POR VISIÓN]: {geo_coords}"

        log.info(f"  🧠 Procesando texto de visión con Gemini para {pid}...")
        result = await _extract_with_ai_async(pid, full_text, log)

        # Enriquecer resultado con coordenadas georreferenciadas si el extractor de texto no las capturó
        if result and geo_coords and not result.get("coordenadas"):
            result["coordenadas"] = geo_coords

        return result

    except Exception as e:
        log.error(f"  ❌ Error crítico en Vision Pipeline: {e}")
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

def audit_record(pid: str, d: dict, log: logging.Logger) -> tuple[int, list[str]]:
    """
    Auditor de Calidad (Strategy 2).
    Verifica consistencia interna y externa.
    """
    penalties = []
    penalty_score = 0
    
    # 1. Consistencia del Código de Estado (Pilar de Integridad)
    pid_state_code = str(pid)[:2]
    expected_state = STATE_CODES.get(pid_state_code)
    extracted_state = str(d.get("estado", "")).upper()
    
    if expected_state and expected_state not in extracted_state:
        # Penalización severa por inconsistencia geográfica
        penalty_score += 25
        penalties.append(f"state_mismatch: PID is {pid_state_code}({expected_state})")
        
    return penalty_score, penalties

def score_record(d: dict) -> tuple[int, list[str]]:
    """
    Calcula un score 0-100 para un registro extraído.
    Retorna (score, lista_de_campos_deficientes).
    Un score ≥ 60 es suficiente para persistir.
    Un score ≥ 80 es de alta confianza.
    """
    score_val: int = 0
    deficient: List[str] = []

    for field, weight in FIELD_WEIGHTS.items():
        val = str(d.get(field, "")).strip().lower()
        if val and val not in PLACEHOLDER_TERMS and len(val) > 2:
            score_val += int(weight)
        else:
            deficient.append(field)

    # Bonus: insight largo y específico
    insight = str(d.get("insight", "")).strip()
    if len(insight) > 80:
        score_val = min(100, score_val + 5)

    # Bonus: coordenadas o polígono presentes
    if d.get("coordenadas") or d.get("poligono"):
        score_val = min(100, score_val + 5)

    return score_val, deficient


async def _repair_missing_fields(pid: str, context: str, d: dict,
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

    raw = await _llm_call(
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
                    log.debug(f"    [Repair] {field} → '{str(patch[field])[:60]}'")
        except json.JSONDecodeError:
            pass
    return d


async def _validate_and_persist(pid: str, year: int, pdf: str, d: dict,
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
    
    # ── Paso 1.5: Auditoría de Calidad (Strategy 2) ───────────────────
    audit_penalty, audit_notes = audit_record(pid, d, log)
    if audit_penalty > 0:
        score -= audit_penalty
        log.warning(f"    [Audit] {pid} penalización -{audit_penalty} por: {audit_notes}")

    log.debug(f"    [Gate-1] {pid} score={score} deficient={deficient}")

    # ── Paso 2: Grounding con portal antes de reparar ────────────────────
    portal_data = await fetch_portal_docs(pid, log)
    if portal_data:
        d = ground_data(d, portal_data, log)
        d = normalize_extracted_data(pid, d)
        score, deficient = score_record(d)
        log.debug(f"    [Gate-2 post-grounding] {pid} score={score}")

    # ── Paso 3: Reparación quirúrgica si score insuficiente ──────────────
    if score < SCORE_ACCEPT and deficient:
        log.info(f"    [Repair] {pid} score={score} — reparando: {deficient}")
        d = await _repair_missing_fields(pid, context, d, deficient, log)
        d = normalize_extracted_data(pid, d)
        score, deficient = score_record(d)
        log.debug(f"    [Gate-3 post-repair] {pid} score={score}")

    # ── Paso 4: Decisión final ───────────────────────────────────────────
    # Filtro ESTRICTO: Únicamente Ensenada
    if "ENSENADA" not in str(d.get("municipio", "")).upper():
        log.info(f"    [REJECT] {pid} ignorado (Municipio: {d.get('municipio')}, requiere ENSENADA)")
        queue.mark_success(pid) # Para no reintentarlo
        return False

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
                log.info(f"    [Traza] Vinculado a inteligencia previa: {dup['pid']} ({dup['year']})")
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
    year = d.get("year", 2026)
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


async def _extract_single(item, log: logging.Logger) -> tuple[Optional[dict], str]:
    """
    Extrae datos para un único QueueItem asíncronamente.
    """
    txt_path = Path(item.txt_file)
    
    # ── COMPUERTA DE MEMORIA (Cap. 16) ───────────────────────────
    if memory and memory.project_exists(item.pid):
        log.info(f"    [Memoria] {item.pid} hallado en inteligencia local — omitiendo")
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
    raw_ctx = str(txt)[max(0, idx - half): idx + half]
    context = re.sub(r'\s+', ' ', raw_ctx).strip()

    # Verificación de densidad: si hay menos de 50 chars únicas
    unique_chars = len(set(context.replace(" ", "")))
    if unique_chars < 50:
        log.warning(f"    [Gate-C] Contexto pobre para {item.pid} ({unique_chars} chars únicos) — intentando OCR")
        vision = await extract_with_vision(item.pid, item.year, item.pdf, log)
        return vision, context

    # Extracción principal con IA
    extracted = await _extract_with_ai_async(item.pid, context, log)

    # Fallback Vision OCR
    if not extracted or str(extracted.get("promovente", "")).strip().lower() in PLACEHOLDER_TERMS:
        log.info(f"    [Fallback-Vision] {item.pid}")
        vision = await extract_with_vision(item.pid, item.year, item.pdf, log)
        if vision:
            extracted = vision

    return extracted, context


async def run_extraction(queue: PersistentQueue, log: logging.Logger):
    """
    Orquestador de extracción asíncrona con procesamiento paralelo limitado por semáforo.
    """
    pending = queue.pending()
    if not pending:
        log.info("Queue vacía — sin trabajo pendiente")
        return

    total = len(pending)
    log.info(f"[Extracción] {total} identificadores — Modo concurrente")

    async def process_item(item):
        if _shutdown: return
        async with extraction_semaphore:
            report_state(item.pdf, "EXTRAYENDO", item.pid)
            log.info(f"  [{item.attempts + 1}/{CONFIG['MAX_RETRIES']}] {item.pid} (Async)")

            extracted, context = await _extract_single(item, log)

            if context == "SKIPPED_BY_MEMORY":
                queue.mark_success(item.pid)
                return

            if extracted is None:
                txt_path = Path(item.txt_file)
                err = "extraction_failed"
                if not txt_path.exists(): err = "txt_missing"
                log.warning(f"    [Skip] {item.pid}: {err}")
                queue.mark_attempt(item.pid, error=err)
                return

            await _validate_and_persist(
                pid=item.pid, year=item.year, pdf=item.pdf,
                d=extracted, context=context,
                queue=queue, log=log,
            )

    tasks = [process_item(item) for item in pending]
    await asyncio.gather(*tasks)

    st = queue.stats()
    report_state("INACTIVO", "ESPERA", "NINGUNO")
    log.info(
        f"[Extracción completada] Total:{st['total']} "
        f"OK:{st['success']} Pendientes:{st['pending']} Fallidos:{st['failed']}"
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
        name = str(doc.get("tipo") or doc.get("name") or "").lower()
        if not url:
            continue
        for doc_type, keys in doc_map.items():
            if any(str(k) in name for k in keys):
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
async def main():
    # Soporte para argumentos: --year 2026 o --daemon
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
    
    if "--check-new" in sys.argv:
        all_new_links = []
        for year in target_years:
            if _shutdown: break
            log.info(f"🔎 Buscando novedades en Gaceta Ecológica {year}...")
            links = await fetch_pdf_links(year, seen, log)
            all_new_links.extend(links)
        
        path = Path("/tmp/zohar_new_gacetas.json")
        path.write_text(json.dumps({"ts": datetime.datetime.now().isoformat(), "new_count": len(all_new_links), "links": all_new_links}))
        log.info(f"✅ CHECK COMPLETO: {len(all_new_links)} nuevas publicaciones detectadas.")
        sys.exit(0)
    
    # Inicializar Memoria y Prompts
    global memory, prompts, portal_cache, geospatial, historical, air_quality
    memory  = LocalIntelligenceMemory(CONFIG["DB_FILE"])
    prompts = PromptManager(CONFIG["PROMPTS_DIR"])
    portal_cache = PortalMetadataCache(CONFIG["DOCS_DIR"] / "portal_cache.json")
    geospatial = GeospatialAdvisor(duck_conn)
    historical = HistoricalConsultationAdvisor(duck_conn)
    air_quality = AirQualityAdvisor(duck_conn)
    
    log.info(f"🚀 ZOHAR AGENT v2.2 ACTIVO | Memoria: {memory.get_stats()}")
    log.info(f"  ZOHAR AGENT v2.2  |  Años: {target_years[0]}...{target_years[-1]}  |  DRY_RUN:{CONFIG['DRY_RUN']}")
    st = queue.stats()
    log.info(f"  Queue: {st}")
    log.info("═" * 58)

    CONFIG["DOCS_DIR"].mkdir(parents=True, exist_ok=True)

    async def run_cycle():
        # 🔍 PRIMERO: monitorear años para nuevos PDFs (de lo más reciente a lo más viejo)
        for year in target_years:
            if _shutdown: break
            log.info(f"Monitoring temporal index for year {year}...")
            pdf_links = await fetch_pdf_links(year, seen, log)
            # Orden descendente
            pdf_links.sort(reverse=True)
            total_new = 0
            for url in pdf_links:
                if _shutdown: break
                n = await process_pdf(url, year, queue, log)
                total_new += n
            if total_new > 0:
                log.info(f"Ingestion successful: {year}: {total_new} new identifiers cataloged")

        # ⚡ DESPUÉS: Tomar las claves e ingresarlas para revisión (Extracción)
        if not _shutdown:
            await run_extraction(queue, log)

    if CONFIG["DAEMON_MODE"]:
        log.info(f"HIGH-THROUGHPUT BATCH ESCALATION ACTIVE — Processing temporal index: {target_years}")
        while not _shutdown:
            # 0. Verificar si el agente está en modo pausa
            if check_pause_flag():
                log.info("⏸️ Agente en modo PAUSA por comando central. Esperando 30s...")
                report_state("PAUSED", "IDLE", "PAUSED BY USER")
                await asyncio.sleep(30)
                continue

            # 1. Forzar recarga de cola desde disco
            queue = PersistentQueue(CONFIG["QUEUE_FILE"])
            pending_count = len(queue.pending())
            
            # 2. Si hay trabajo, procesar SIN DESCANSO (si el dashboard está vivo)
            if pending_count > 0:
                if is_dashboard_alive():
                    log.info(f"Initiating extraction cycle: {pending_count} identifiers queued.")
                    await run_extraction(queue, log)
                    continue
                else:
                    log.info("Zohar Dashboard connection lost. Standing by for heartbeat...")
                    await asyncio.sleep(5)
                    continue
            
            # 3. Si no hay trabajo de IA, buscar gacetas nuevas
            log.info("Queue empty. Initiating search for new datasets...")
            await run_cycle()
            
            # 4. Solo dormir si REALMENTE no hay nada más que hacer
            if len(queue.pending()) == 0:
                rotate_logs()
                load = get_system_load()
                # Throttling dinámico: si el load es alto, dormimos más
                base_poll = CONFIG["POLL_INTERVAL_MIN"]
                if load > 4.0:
                    base_poll *= 2
                    log.warning(f"⚠️ Alto load ({load}): Duplicando tiempo de espera.")
                
                poll_s = base_poll * 60
                log.info(f"No pending operations. Standby mode active for {base_poll} minutes.")
                for _ in range(poll_s):
                    if _shutdown: break
                    # Verificar pausa durante el sueño largo
                    if _ % 30 == 0 and check_pause_flag():
                         break
                    await asyncio.sleep(1)
    else:
        await run_cycle()

    log.info("Agent process terminated gracefully.")


if __name__ == "__main__":
    asyncio.run(main())
