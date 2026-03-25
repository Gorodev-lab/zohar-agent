import os
import sqlite3
import pandas as pd
import re
import urllib.request
import datetime
import json
import subprocess
import shutil
import duckdb
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from supabase import create_client, Client
from dotenv import load_dotenv

try:
    import psutil
    _PSUTIL_OK = True
except ImportError:
    _PSUTIL_OK = False

# Cargar variables de entorno
ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(ENV_PATH)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase_client: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)

from api.routes import air_quality

app = FastAPI(title="Zohar Intelligence API")

# Registro de Routers
app.include_router(air_quality.router)

# Configuración de Rutas
HOME = Path(os.path.expanduser("~"))
BASE_DIR = Path(__file__).parent.parent
DB_PATH = HOME / "zohar_intelligence.db"
DUCK_PATH = HOME / "zohar_warehouse.duckdb"
CSV_PATH = HOME / "zohar_historico_proyectos.csv"
STATE_FILE = HOME / "zohar_agent_state.json"
QUEUE_FILE = BASE_DIR / "agent" / "zohar_queue.json"
LOG_FILE = BASE_DIR / "agent" / "zohar_agent.jsonl"
HISTORIC_FILE = BASE_DIR / "agent" / "semarnat_historic_consultations.json"
DASHBOARD_DIR = BASE_DIR / "dashboard_legacy"

# TONL-C5: Cache módulo-level para el JSON histórico completo
# Evita leer y parsear el archivo (672KB, 848 registros) en cada request HTTP
_historic_cache: list = None

# Bases para resolver URLs relativas en los links del JSON
_SEMARNAT_GIS_BASE = "https://gisviewer.semarnat.gob.mx"
_SEMARNAT_APPS_BASE = "https://apps1.semarnat.gob.mx"

def _normalize_links(links_raw, clave: str) -> dict:
    """Normaliza todos los links para que sean URLs absolutas verificables.
    - Resuelve paths relativos (/Gacetas/..., /expediente/...)
    - Fuerza https en todos los links
    - Reemplaza mapas.semarnat.gob.mx genérico por el visor con clave específica
    """
    if not links_raw or not isinstance(links_raw, dict):
        return {}
    
    normalized = {}
    for key, url in links_raw.items():
        if not isinstance(url, str) or not url.strip():
            continue
        url = url.strip()
        
        # 1. Resolver URLs relativas
        if url.startswith('/'):
            # /Gacetas/... y /expediente/... viven en el GIS viewer
            url = _SEMARNAT_GIS_BASE + url
        
        # 2. Reemplazar visor genérico (mapas.semarnat.gob.mx/) por el visor con clave
        if 'mapas.semarnat.gob.mx' in url and '?' not in url:
            url = f"{_SEMARNAT_GIS_BASE}/Aplicaciones/Tramites/ConsultaN.html?idS={clave}"
        
        # 3. Forzar HTTPS
        if url.startswith('http://'):
            url = 'https://' + url[7:]
        
        # 4. Corregir Gacetas sin prefijo completo (e.g. "Gacetas/archivos...")
        if url.startswith('Gacetas/') or url.startswith('gacetas/'):
            url = f"{_SEMARNAT_GIS_BASE}/{url}"
        
        normalized[key] = url
    
    return normalized

def _get_historic_all() -> list:
    """Carga TODOS los registros del JSON histórico (848 registros, todos los años).
    Los de 2026 se marcan como CONCLUIDO_2026, el resto como HISTORICO.
    Todos los links se normalizan a URLs absolutas."""
    global _historic_cache
    if _historic_cache is not None:
        return _historic_cache
    result = []
    if HISTORIC_FILE.exists():
        try:
            with open(HISTORIC_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for item in data:
                anio = str(item.get("anio", ""))
                if anio != "2026":
                    continue
                clave = item.get("clave", "")
                result.append({
                    "Clave":     clave,
                    "Modalidad": item.get("modalidad", ""),
                    "Promovente":item.get("promovente", ""),
                    "Proyecto":  item.get("proyecto", ""),
                    "Ubicacion": item.get("ubicacion", ""),
                    "Sector":    item.get("sector", ""),
                    "Fecha":     item.get("fechas", ""),
                    "Año":       anio,
                    "Estatus":   "CONCLUIDO_2026",
                    "links":     _normalize_links(item.get("links", {}), clave)
                })
        except Exception as e:
            print(f"Error building historic cache: {e}")
    _historic_cache = result
    return _historic_cache

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir Frontend
@app.get("/aire", response_class=HTMLResponse)
async def get_air_map():
    with open(DASHBOARD_DIR / "air_map.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def get_index():
    index_path = DASHBOARD_DIR / "index.html"
    if index_path.exists():
        return index_path.read_text()
    return "Error: No se encontró el archivo index.html del Dashboard"

@app.get("/aire", response_class=HTMLResponse)
async def get_aire():
    aire_path = DASHBOARD_DIR / "aire.html"
    if aire_path.exists():
        return aire_path.read_text()
    return "Error: No se encontró aire.html"

# Mount para archivos estáticos internos (si los hubiera)
# app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

HEARTBEAT_FILE = HOME / ".zohar_heartbeat"

def touch_heartbeat():
    try:
        HEARTBEAT_FILE.touch()
    except:
        pass

@app.get("/api/status")
async def get_status():
    touch_heartbeat()
    temp = "N/A"
    try:
        out = subprocess.check_output(['sensors'], text=True)
        m = re.search(r'(?:CPU|temp1|Tdie):\s+\+?([\d\.]+)', out)
        if m: temp = f"{m.group(1)}°C"
    except: pass
    
    llama_ok, _ = _check_service("http://127.0.0.1:8001/v1/models")
    agent_running = _is_agent_alive()
    
    return {
        "cpu_temp": temp,
        "llama_status": "En línea" if llama_ok else "Fuera de línea",
        "agent_running": agent_running,
        "llama_ok": llama_ok,
        "mode": "híbrido-local"
    }

@app.get("/api/agent_state")
async def get_agent_state():
    touch_heartbeat()
    is_vercel = os.environ.get("VERCEL") == "1"
    if is_vercel and supabase_client:
        try:
            res = supabase_client.table("agente_status").select("*").eq("id", 1).execute()
            if res.data:
                s = res.data[0]
                return {"pdf": s["pdf"], "action": s["action"], "target": s["target"], "time": s.get("last_seen", "")[-8:]}
        except: pass
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except: pass
    return {"pdf": "INACTIVO", "action": "ESPERA", "target": "NINGUNO"}

@app.get("/api/projects")
async def get_projects():
    touch_heartbeat()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # Filtrado estricto para 2026 según requerimiento del usuario
            df = pd.read_sql_query("SELECT * FROM projects WHERE year = 2026 ORDER BY created_at DESC LIMIT 200", conn)
            
            # Normalizar nombres de columnas a mayúsculas para el Dashboard
            df.columns = [c.upper() for c in df.columns]
            df = df.rename(columns={"PID": "ID_PROYECTO", "YEAR": "ANIO"})
            json_str = df.to_json(orient="records")
            records = json.loads(json_str)
            for r in records:
                pid = r.get("ID_PROYECTO")
                if pid:
                    r["links"] = {
                        "Visor Geográfico": f"{_SEMARNAT_GIS_BASE}/Aplicaciones/Tramites/ConsultaN.html?idS={pid}"
                    }
            return records
    except Exception as e:
        print(f"Error fetching projects: {e}")
        return []

@app.get("/proyectos/{pid}")
async def get_project_detail(pid: str):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            res = conn.execute("SELECT * FROM projects WHERE pid = ?", (pid,)).fetchone()
            if not res:
                raise HTTPException(status_code=404, detail="Proyecto no hallado")
            return dict(res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/proyectos/{pid}/report")
async def get_project_report(pid: str):
    try:
        # 1. Obtener ubicación del proyecto
        with sqlite3.connect(DB_PATH) as conn:
            res = conn.execute("SELECT municipio, year FROM projects WHERE pid = ?", (pid,)).fetchone()
            if not res: raise HTTPException(status_code=404, detail="Proyecto no hallado")
            municipio, year = res

        # 2. Consultar DuckDB para el reporte ambiental
        # (Usamos lógica directa para simplificar sin re-importar la clase entera del agente)
        with duckdb.connect(str(DUCK_PATH)) as d_conn:
            # Agregación
            agg = d_conn.execute("""
                SELECT AVG(so2), MAX(so2), AVG(nox), MAX(nox), AVG(pm2_5), MAX(pm2_5)
                FROM air_quality_emissions WHERE municipio ILIKE ?
            """, (f"%{municipio}%",)).fetchone()
            
            if not agg or agg[0] is None:
                return {"pid": pid, "execution_path": "SKIPPED_NO_DATA"}

            data = {
                "avg": {"so2": round(agg[0], 2), "nox": round(agg[2], 2), "pm25": round(agg[4], 2)},
                "max": {"so2": round(agg[1], 2), "nox": round(agg[3], 2), "pm25": round(agg[5], 2)}
            }

            # Lógica de reporte
            THRESHOLDS = {"so2": 40.0, "nox": 70.0, "pm25": 25.0}
            violations = []
            risk_score = 0
            for m, limit in THRESHOLDS.items():
                current = data["avg"].get(m, 0)
                if current > limit:
                    pct = ((current - limit) / limit) * 100
                    violations.append({"metric": m, "value": current, "limit": limit, "excess_pct": round(pct, 2)})
                    risk_score += pct

            path = "AUTONOMOUS"
            if violations and any(float(v["excess_pct"]) > 20.0 for v in violations):
                path = "CRITICAL_SIGNATURE_REQUIRED"
            elif risk_score > 50.0:
                path = "CRITICAL_SIGNATURE_REQUIRED"
            
            return {
                "timestamp": datetime.datetime.now().isoformat(),
                "cycle_2026": year == 2026,
                "pid": pid,
                "metrics": data,
                "violations": violations,
                "risk_score": round(risk_score, 2),
                "execution_path": path
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/historic_consultations")
async def get_historic_consultations():
    touch_heartbeat()
    # TONL-C5: Usar cache módulo-level (cargado una sola vez en el primer request)
    combined_data = list(_get_historic_all())
    
    # Merge Live 2026 Data from SQLite
    if DB_PATH.exists():
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT pid, modalidad, promovente, proyecto, estado, municipio, sector, year, created_at, sources
                FROM projects 
                WHERE year = 2026
                ORDER BY created_at DESC
            """)
            live_rows = cursor.fetchall()
            
            existing_claves = {str(item["Clave"]).strip().upper() for item in combined_data if item.get("Clave")}
            
            for row in live_rows:
                clave = str(row["pid"]).strip().upper()
                if clave not in existing_claves:
                    links_raw = row["sources"]
                    links = {}
                    try:
                        if isinstance(links_raw, str):
                            links_list = json.loads(links_raw)
                            if isinstance(links_list, list):
                                for i, l in enumerate(links_list):
                                    links[f"Source {i+1}"] = l
                            elif isinstance(links_list, dict):
                                links = links_list
                    except: pass

                    combined_data.insert(0, {
                        "Clave": row["pid"],
                        "Modalidad": row["modalidad"],
                        "Promovente": row["promovente"],
                        "Proyecto": row["proyecto"],
                        "Ubicacion": f"{row['estado']}, {row['municipio']}",
                        "Sector": row["sector"],
                        "Fecha": row["created_at"],
                        "Áño": row["year"],
                        "Estatus": "EXTRACTED_LIVE_2026",
                        "links": links
                    })
            conn.close()
        except Exception as e:
            print(f"Error merging live data: {e}")

    return combined_data

@app.get("/api/csv_data")
async def get_csv_data(type: str = "regulatory"):
    """
    Lee datos. Para aire, lee de DuckDB en lugar del CSV para usar el "grounding" local.
    """
    try:
        if type == 'air_quality':
            # Priorizar DuckDB (Estrategia B de Warehouse)
            if DUCK_PATH.exists():
                try:
                    import duckdb
                    with duckdb.connect(str(DUCK_PATH), read_only=True) as conn:
                        df = conn.execute("SELECT * FROM aire_emisiones").df()
                        # Renombrar columnas para compatibilidad UI (el CSV original tiene espacios o nombres largos)
                        # La UI usa: ['Entidad_federativa', 'Municipio', 'Tipo_de_Fuente', 'SO_2', 'CO', 'NOx', 'COV', 'PM_010', 'PM_2_5', 'NH_3', 'lat', 'lon']
                        df = df.rename(columns={
                            "entidad": "Entidad_federativa",
                            "municipio": "Municipio",
                            "fuente": "Tipo_de_Fuente",
                            "so2": "SO_2", "co": "CO", "nox": "NOx", "cov": "COV",
                            "pm10": "PM_010", "pm25": "PM_2_5", "nh3": "NH_3"
                        })
                        df = df.fillna("")
                        return df.to_dict(orient='records')
                except Exception as e:
                    print(f"⚠️ DuckDB error: {e}")
            
            # Fallback a Snapshot JSON (Ideal para Vercel)
            snapshot = DASHBOARD_DIR / "aire_snapshot.json"
            if snapshot.exists():
                import json
                with open(snapshot, 'r') as f:
                    return json.load(f)

            # Fallback al CSV original (grounding heredado)
            if not CSV_PATH.exists():
                raise HTTPException(status_code=404, detail="Fuente de datos no encontrada")
            
            df = pd.read_csv(CSV_PATH)
            return df.to_dict(orient='records')
        else:
            file_map = {
                "regulatory":  BASE_DIR / "ordenamientos_ecologicos_expedidos.csv",
                "financial":   BASE_DIR / "ingresos_2024.csv"
            }
            target_file = file_map.get(type)
            if not target_file or not target_file.exists():
                return []

            df = pd.read_csv(target_file)
            df.columns = [c.strip() for c in df.columns]
            df = df.iloc[:200].fillna("")
            return df.to_dict(orient="records")
    except Exception as e:
        print(f"Error reading data {type}: {e}")
        return []

@app.post("/api/control/{service}/{action}")
async def control_service(service: str, action: str):
    touch_heartbeat()
    valid_actions = ["start", "stop", "restart", "retry-failed"]
    if action not in valid_actions:
        raise HTTPException(status_code=400, detail="Acción no válida")
        
    if service == "agent":
        ctl_script = BASE_DIR / "agent" / "zohar_ctl.sh"
        if not ctl_script.exists():
            raise HTTPException(status_code=500, detail="Script de control no encontrado")
        
        try:
            # Map restart to stop then start
            if action == "restart":
                subprocess.run([str(ctl_script), "stop"], check=False)
                subprocess.run([str(ctl_script), "start"], check=False)
                return {"status": "ok", "msg": "Agente reiniciado"}
            
            subprocess.run([str(ctl_script), action], check=False)
            return {"status": "ok", "msg": f"Comando {action} ejecutado para agente"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    elif service in ["llm", "ocr"]:
        # Mock para LLM y OCR por ahora, o ejecutar comandos systemctl si existen
        # Aquí simularemos el éxito
        return {"status": "ok", "msg": f"Simulación: Comando {action} ejecutado para {service.upper()}"}
    
    raise HTTPException(status_code=404, detail="Servicio no encontrado")

@app.get("/api/diagnostics")
async def get_diagnostics():
    touch_heartbeat()
    # Real-time process stats
    stats = {}
    try:
        # CPU/Mem for agent
        agent_pid = None
        try:
            agent_pid = subprocess.check_output(["pgrep", "-f", "zohar_agent_v2"], text=True).strip()
        except: pass
        
        if agent_pid:
            top = subprocess.check_output(["ps", "-p", agent_pid, "-o", "%cpu,%mem,cmd"], text=True).splitlines()
            if len(top) > 1:
                cpu, mem, cmd = top[1].strip().split(None, 2)
                stats["agent"] = {"cpu": cpu, "mem": mem, "running": True}
        else:
            stats["agent"] = {"running": False}
            
        # Queue stats
        if QUEUE_FILE.exists():
            q = json.loads(QUEUE_FILE.read_text())
            stats["queue"] = {
                "total": len(q),
                "success": sum(1 for v in q.values() if v.get("status") == "success"),
                "pending": sum(1 for v in q.values() if v.get("status") == "pending"),
                "failed": sum(1 for v in q.values() if v.get("status") == "failed"),
            }
            if stats["queue"]["total"] > 0:
                stats["queue"]["progress_pct"] = round((stats["queue"]["success"] / stats["queue"]["total"]) * 100, 1)
    except:
        pass
        
    return {
        "ts": datetime.datetime.now().isoformat(),
        "services": stats,
        "mode": "arch-linux-terminal-v2"
    }

@app.get("/api/logs")
async def get_logs():
    if not LOG_FILE.exists():
        return []
    try:
        # TONL-A5: Tail eficiente — leer solo los últimos ~8KB en lugar del archivo completo
        TAIL_BYTES = 8 * 1024  # 8KB son ~50 líneas JSON de log
        with open(LOG_FILE, "rb") as f:
            f.seek(0, 2)  # fin del archivo
            size = f.tell()
            f.seek(max(0, size - TAIL_BYTES))
            raw = f.read().decode("utf-8", errors="replace")
        # Descartar línea parcial al inicio (puede estar cortada)
        lines = raw.split("\n")
        if size > TAIL_BYTES:
            lines = lines[1:]  # La primera línea puede estar incompleta
        logs = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                # Limpiar emojis/iconos Unicode para mantener estética CRT terminal
                if "msg" in entry and isinstance(entry["msg"], str):
                    import re
                    # Remover emojis y símbolos Unicode no-ASCII
                    entry["msg"] = re.sub(
                        r'[\U0001F300-\U0001F9FF\U00002600-\U000027BF\U0000FE00-\U0000FEFF'
                        r'\U00002700-\U000027BF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF'
                        r'\U00002702-\U000027B0\U0000231A-\U0000231B\U000023E9-\U000023F3'
                        r'\U000023F8-\U000023FA\U000025AA-\U000025AB\U000025B6\U000025C0'
                        r'\U000025FB-\U000025FE\U00002934-\U00002935\U00002B05-\U00002B07'
                        r'\U00002B1B-\U00002B1C\U00002B50\U00002B55\U00003030\U0000303D'
                        r'\U00003297\U00003299\U0000200D\U000020E3\U0000FE0F]',
                        '', entry["msg"]
                    ).strip()
                    # Remover dobles espacios que quedan
                    entry["msg"] = re.sub(r'  +', ' ', entry["msg"])
                logs.append(entry)
            except:
                pass
        return logs[-50:]  # Máximo 50 entradas al cliente
    except:
        return []

def _check_service(url: str, timeout: int = 5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200, ""
    except:
        return False, ""

def _is_agent_alive():
    try:
        out = subprocess.check_output(["pgrep", "-f", "zohar_agent_v2"], text=True)
        return bool(out.strip())
    except:
        return False

def _get_cpu_temp() -> str:
    """Lee temperatura de CPU vía lm-sensors."""
    try:
        out = subprocess.check_output(['sensors'], text=True, timeout=3)
        m = re.search(r'(?:CPU|temp1|Tdie):\s+\+?([\d\.]+)', out)
        if m:
            return f"{m.group(1)}°C"
    except Exception:
        pass
    return "N/A"

def _get_mem_pct() -> float:
    """Porcentaje de RAM usada."""
    if _PSUTIL_OK:
        return round(psutil.virtual_memory().percent, 1)
    try:
        out = subprocess.check_output(['free', '-m'], text=True)
        lines = out.splitlines()
        parts = lines[1].split()
        total, used = int(parts[1]), int(parts[2])
        return round(used / total * 100, 1) if total else 0.0
    except Exception:
        return 0.0

def _get_disk_free() -> str:
    """Espacio libre en disco del proyecto."""
    try:
        total, used, free = shutil.disk_usage(str(BASE_DIR))
        return f"{free // (1024**3)} GB libres / {total // (1024**3)} GB total"
    except Exception:
        return "N/A"

def _get_queue_stats() -> dict:
    """Estadísticas de la cola del agente."""
    if not QUEUE_FILE.exists():
        return {"total": 0, "success": 0, "pending": 0, "failed": 0}
    try:
        q = json.loads(QUEUE_FILE.read_text())
        total = len(q)
        success = sum(1 for v in q.values() if v.get("status") == "success")
        pending = sum(1 for v in q.values() if v.get("status") == "pending")
        failed  = sum(1 for v in q.values() if v.get("status") == "failed")
        pct = round(success / total * 100, 1) if total else 0.0
        return {"total": total, "success": success, "pending": pending, "failed": failed, "progress_pct": pct}
    except Exception:
        return {"total": 0, "success": 0, "pending": 0, "failed": 0}

def _get_last_extraction_time() -> str:
    """Timestamp de la última línea de log del agente."""
    if not LOG_FILE.exists():
        return "N/A"
    try:
        with open(LOG_FILE, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            if size == 0:
                return "N/A"
            f.seek(max(0, size - 2048))
            raw = f.read().decode("utf-8", errors="replace")
        for line in reversed(raw.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                return entry.get("ts", entry.get("time", "N/A"))
            except Exception:
                pass
    except Exception:
        pass
    return "N/A"

def _get_active_model() -> str:
    """Modelo activo según el ModelRouter."""
    try:
        import sys
        sys.path.insert(0, str(BASE_DIR))
        from warehouse.model_router import ModelRouter
        return ModelRouter.get_active_model_name("extraction")
    except Exception:
        return "gemini-2.0-flash"


# ═══════════════════════════════════════════════════════════════════════════
# FASE 3: Control por botón — ciclo único de extracción
# ═══════════════════════════════════════════════════════════════════════════

AGENT_V2_PATH = BASE_DIR / "agent" / "zohar_agent_v2.py"
AGENT_OUTPUT_LOG = BASE_DIR / "agent" / "agent_output.log"

@app.post("/api/control/agent/start-once")
async def start_agent_once():
    """Ejecuta UN SOLO ciclo de extracción (no demonio).
    El agente NO corre automáticamente; solo responde a clicks del dashboard.
    """
    if _is_agent_alive():
        raise HTTPException(status_code=400, detail="Agente ya en ejecución")
    if not AGENT_V2_PATH.exists():
        raise HTTPException(status_code=500, detail="zohar_agent_v2.py no encontrado")
    try:
        venv_python = BASE_DIR / "venv" / "bin" / "python3"
        python_bin = str(venv_python) if venv_python.exists() else "python3"
        subprocess.Popen(
            [python_bin, str(AGENT_V2_PATH), "--single-run", "--year", "2026"],
            cwd=str(BASE_DIR),
            stdout=open(str(AGENT_OUTPUT_LOG), "w"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        return {
            "status": "ok",
            "mode": "single-run",
            "msg": "Ciclo único 2026 iniciado. Revisa /api/logs para el progreso.",
            "log": str(AGENT_OUTPUT_LOG),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/control/agent/status")
async def get_agent_run_status():
    """Estado actual del agente (para polling desde el dashboard)."""
    alive = _is_agent_alive()
    last_line = ""
    if AGENT_OUTPUT_LOG.exists():
        try:
            with open(str(AGENT_OUTPUT_LOG), "rb") as f:
                f.seek(0, 2)
                size = f.tell()
                f.seek(max(0, size - 512))
                raw = f.read().decode("utf-8", errors="replace")
            lines = [l.strip() for l in raw.splitlines() if l.strip()]
            last_line = lines[-1] if lines else ""
        except Exception:
            pass
    status = "RUNNING" if alive else ("IDLE" if not last_line else "COMPLETE")
    return {"running": alive, "status": status, "last_log_line": last_line}


# ═══════════════════════════════════════════════════════════════════════════
# FASE 4: Recursos en tiempo real
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/api/resources")
async def get_resources():
    """Métricas en tiempo real del sistema: CPU, RAM, disco, DBs, cola, modelo."""
    llama_ok, _ = _check_service("http://127.0.0.1:8001/v1/models", timeout=2)
    qwen_ok, _  = _check_service("http://127.0.0.1:8002/v1/models", timeout=2)
    return {
        "ts": datetime.datetime.now().isoformat(),
        "cpu_temp": _get_cpu_temp(),
        "mem_used_pct": _get_mem_pct(),
        "disk": _get_disk_free(),
        "agent_running": _is_agent_alive(),
        "llm_status": {
            "llama": "online" if llama_ok else "offline",
            "qwen":  "online" if qwen_ok  else "offline",
            "gemini": "primary",
        },
        "databases": {
            "sqlite":   {"path": str(DB_PATH),   "exists": DB_PATH.exists()},
            "duckdb":   {"path": str(DUCK_PATH),  "exists": DUCK_PATH.exists()},
            "supabase": {"status": "connected" if supabase_client else "disconnected"},
        },
        "queue": _get_queue_stats(),
        "last_extraction": _get_last_extraction_time(),
        "model_active": _get_active_model(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
