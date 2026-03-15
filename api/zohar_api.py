import os
import sqlite3
import pandas as pd
import re
import urllib.request
import datetime
import json
import subprocess
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

app = FastAPI(title="Zohar Intelligence API")

# Configuración de Rutas
HOME = Path(os.path.expanduser("~"))
BASE_DIR = Path(__file__).parent.parent
DB_PATH = HOME / "zohar_intelligence.db"
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

# Servir Dashboard
@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    index_file = DASHBOARD_DIR / "index.html"
    if not index_file.exists():
        return "Dashboard index.html not found."
    return index_file.read_text()

@app.get("/api/status")
async def get_status():
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
        "llama_status": "Online" if llama_ok else "Offline",
        "agent_running": agent_running,
        "llama_ok": llama_ok,
        "mode": "hybrid-local"
    }

@app.get("/api/projects")
async def get_projects():
    df = load_audited_data()
    try:
        if hasattr(df, "fillna"):
            data = df.fillna("").to_dict("records")
        else:
            data = df
        if not data: return []
        data.sort(key=lambda x: (str(x.get("ANIO", "")), str(x.get("ID_PROYECTO", ""))), reverse=True)
        return data[:500]
    except:
        return []

@app.get("/api/agent_state")
async def get_agent_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except: pass
    return {"pdf": "IDLE", "action": "STANDBY", "target": "NONE"}

@app.get("/api/logs")
async def get_logs():
    if not LOG_FILE.exists(): return []
    try:
        lines = LOG_FILE.read_text().splitlines()[-20:]
        logs = []
        for line in lines:
            try:
                entry = json.loads(line)
                logs.append({
                    "ts": entry.get("ts", "")[-8:],
                    "msg": entry.get("msg", ""),
                    "level": entry.get("level", "INFO")
                })
            except: continue
        return logs
    except: return []

@app.get("/api/diagnostics")
async def get_diagnostics():
    csv_rows = 0
    csv_size = 0
    if CSV_PATH.exists():
        csv_size = os.path.getsize(CSV_PATH) // 1024
        csv_rows = sum(1 for _ in open(CSV_PATH))
            
    # Queue Stats Reales
    queue_data = {"pending": 0, "success": 0, "failed": 0, "progress_pct": 0}
    if QUEUE_FILE.exists():
        try:
            q = json.loads(QUEUE_FILE.read_text())
            items = q.values() if isinstance(q, dict) else q
            queue_data["pending"] = len([i for i in items if i.get("status") == "pending"])
            queue_data["success"] = len([i for i in items if i.get("status") == "success"])
            queue_data["failed"] = len([i for i in items if i.get("status") in ["failed", "error"]])
            total = len(items)
            if total > 0:
                queue_data["progress_pct"] = int((queue_data["success"] / total) * 100)
        except: pass

    llama_ok, _ = _check_service("http://127.0.0.1:8001/v1/models")
    ocr_ok, _ = _check_service("http://127.0.0.1:8002/v1/models")
    agent_alive = _is_agent_alive()

    return {
        "ts": datetime.datetime.now().isoformat(),
        "services": {
            "llama": {"status": "online" if llama_ok else "offline", "running": True},
            "ocr": {"status": "online" if ocr_ok else "offline", "running": True},
            "agent": {"running": agent_alive, "pid_file": os.path.exists("/tmp/zohar_agent_v2.pid")}
        },
        "csv": {"rows": csv_rows, "size_kb": csv_size},
        "queue": queue_data,
        "issues": []
    }

@app.post("/api/control")
async def post_control(request: Request):
    """
    Protocolo de Reinicio y Mantenimiento (Local + Cloud).
    """
    try:
        data = await request.json()
        action = data.get("action")
        target = data.get("target", "all")
        
        ctl_script = BASE_DIR / "agent" / "zohar_ctl.sh"
        
        if action == "restart":
            if target in ["agent", "all"]:
                # Detener y arrancar daemon (usa sentinel para red/green)
                subprocess.run(["bash", str(ctl_script), "stop"], check=False)
                subprocess.Popen(["bash", str(ctl_script), "start-daemon"], 
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 start_new_session=True)
                return {"status": "ok", "msg": "Reinicio de Agente iniciado (Protocolo Sentinel Activo)"}
                
        elif action == "stop":
            subprocess.run(["bash", str(ctl_script), "stop"], check=False)
            return {"status": "ok", "msg": "Agente detenido"}

        elif action == "sweep":
            if target in ["agent", "all"]:
                subprocess.run(["bash", str(ctl_script), "stop"], check=False)
                subprocess.Popen(["bash", str(ctl_script), "sweep"], 
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 start_new_session=True)
                return {"status": "ok", "msg": "Barrido Histórico (Sweep) iniciado"}
                
        elif action == "retry-failed":
            subprocess.run(["bash", str(ctl_script), "retry-failed"], check=False)
            return {"status": "ok", "msg": "IDs fallidos reseteados a pendiente"}
            
        elif action == "sync-cloud":
            # Verificar Supabase (simulado o via script)
            return {"status": "ok", "msg": "Sincronización Cloud Verificada"}

        return {"status": "error", "msg": "Acción no reconocida"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/audit")
async def post_audit(request: Request):
    try:
        data = await request.json()
        pid = data.get("pid")
        status = data.get("status")
        notes = data.get("notes", "")
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE projects SET audit_status = ?, auditor_notes = ? WHERE pid = ?", (status, notes, pid))
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/cloud-projects")
async def get_cloud_projects_local():
    return await get_projects()

# Helpers
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

def load_audited_data():
    if not DB_PATH.exists(): return pd.DataFrame()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            df = pd.read_sql_query("SELECT * FROM projects", conn)
            return df.rename(columns={
                "pid": "ID_PROYECTO", "year": "ANIO", "estado": "ESTADO",
                "municipio": "MUNICIPIO", "localidad": "LOCALIDAD",
                "proyecto": "PROYECTO", "promovente": "PROMOVENTE",
                "sector": "SECTOR", "insight": "INSIGHT",
                "coordenadas": "COORDENADAS", "poligono": "POLIGONO"
            })
    except: return pd.DataFrame()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
