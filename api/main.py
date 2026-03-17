import os
import sqlite3
import pandas as pd
import re
import urllib.request
import datetime
import json
import subprocess
import duckdb
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from supabase import create_client, Client
from dotenv import load_dotenv

# Cargar variables de entorno
ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(ENV_PATH)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase_client: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI(title="Zohar Intelligence API")

# Configuración de Rutas
HOME = Path(os.path.expanduser("~"))
BASE_DIR = Path(__file__).parent.parent
DB_PATH = HOME / "zohar_intelligence.db"
DUCK_PATH = HOME / "gaceta_work" / "zohar_warehouse.duckdb"
CSV_PATH = HOME / "zohar_historico_proyectos.csv"
STATE_FILE = HOME / "zohar_agent_state.json"
QUEUE_FILE = BASE_DIR / "agent" / "zohar_queue.json"
LOG_FILE = BASE_DIR / "agent" / "zohar_agent.jsonl"
DASHBOARD_DIR = BASE_DIR / "dashboard"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir Frontend
@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def get_index():
    index_path = DASHBOARD_DIR / "index.html"
    if index_path.exists():
        return index_path.read_text()
    return "Error: No se encontró el archivo index.html del Dashboard"

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
            df = pd.read_sql_query("SELECT * FROM projects ORDER BY year DESC, created_at DESC LIMIT 100", conn)
            # Normalizar nombres de columnas a mayúsculas para el Dashboard
            df.columns = [c.upper() for c in df.columns]
            df = df.rename(columns={"PID": "ID_PROYECTO", "YEAR": "ANIO"})
            # Usar to_json para manejar NaN -> null correctamente
            json_str = df.to_json(orient="records")
            return json.loads(json_str)
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

@app.get("/api/csv_data")
async def get_csv_data(type: str = "regulatory"):
    """
    Lee datos de los CSVs locales para el dashboard.
    types: 'regulatory' (ordenamientos), 'financial' (ingresos)
    """
    try:
        file_map = {
            "regulatory": BASE_DIR / "ordenamientos_ecologicos_expedidos.csv",
            "financial": BASE_DIR / "ingresos_2024.csv"
        }
        target_file = file_map.get(type)
        if not target_file or not target_file.exists():
            return []
            
        df = pd.read_csv(target_file)
        # Limpiar nombres de columnas
        df.columns = [c.upper().replace(" ", "_") for c in df.columns]
        # Limitamos a 200 filas para no saturar el DOM
        df = df.head(200).fillna("")
        return df.to_dict(orient="records")
    except Exception as e:
        print(f"Error reading CSV {type}: {e}")
        return []

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
        # Leer las últimas 50 líneas
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            # Parsear JSON lines
            logs = []
            for line in lines[-50:]:
                try:
                    logs.append(json.loads(line))
                except:
                    pass
            return logs
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
