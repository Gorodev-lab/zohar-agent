"""
ZOHAR API - FastAPI Backend
Puerto: 8081
Sirve el dashboard y los endpoints de la API de monitoreo.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import subprocess
import re
import os
import json
import csv
import pandas as pd

app = FastAPI(title="Zohar Lean API", version="5.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Determinar el directorio base dinámicamente
API_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(API_DIR)
HOME = os.path.expanduser("~")

CSV_FILE = os.path.join(HOME, "zohar_historico_proyectos.csv")
STATE_FILE = os.path.join(HOME, "zohar_agent_state.json")
DASHBOARD_DIR = os.path.join(BASE_DIR, "dashboard")

# Servir dashboard
app.mount("/static", StaticFiles(directory=DASHBOARD_DIR), name="static")

@app.get("/")
def read_index():
    return FileResponse(os.path.join(DASHBOARD_DIR, "index.html"))

@app.get("/api/status")
def get_status():
    temp = "N/A"
    try:
        out = subprocess.check_output(['sensors'], text=True)
        m = re.search(r'(?:CPU|temp1|Tdie):\s+\+?([\d\.]+)', out)
        if m: temp = f"{m.group(1)}°C"
    except: pass
    
    # Check if agent is running
    is_active = os.path.exists("/tmp/zohar_agent_v2.pid")
    
    return {
        "cpu_temp": temp, 
        "llama_status": "🟢 Ready" if is_active else "🔴 Stopped", 
        "system": "Zohar Lean",
        "agent_running": is_active
    }

@app.get("/api/agent_state")
def get_agent_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {"pdf": "IDLE", "action": "STANDBY", "target": "NONE"}

@app.get("/api/projects")
def get_projects():
    if not os.path.exists(CSV_FILE): return []
    projects = []
    try:
        import csv
        with open(CSV_FILE, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None) # Saltar cabecera
            rows = list(reader)
            
            for p in rows[-51:]:  # Últimos 50
                if len(p) >= 7:
                    projects.append({
                        "ID_PROYECTO": p[1],
                        "ESTADO": p[2],
                        "MUNICIPIO": p[3],
                        "PROYECTO": p[4],
                        "PROMOVENTE": p[5],
                        "RIESGO": p[6],
                        "DESCRIPCION": p[7] if len(p) > 7 else ""
                    })
        return projects
    except Exception as e:
        print(f"Error reading projects: {e}")
        return []

@app.get("/api/analytics")
def get_analytics():
    if not os.path.exists(CSV_FILE) or os.path.getsize(CSV_FILE) == 0:
        return {"total": 0, "risk_counts": {}, "top_states": [], "top_promoters": []}
    
    try:
        cols = ["year", "id", "estado", "municipio", "proyecto", "promovente", "riesgo"]
        df = pd.read_csv(CSV_FILE, names=cols, header=0, on_bad_lines='skip')
        
        # Clean data
        df['riesgo'] = df['riesgo'].fillna('bajo').str.lower().str.strip()
        df['estado'] = df['estado'].fillna('DESCONOCIDO').str.upper().str.strip()
        
        # Filter out noise from states and promoters
        noise_filter = ['DE', 'LOS', 'EL', 'LA', 'SAN', 'SANTA', 'DEL', 'EL ID', 'ID_PROYECTO', 'MUNICIPIO', 'ESTADO', 'ID']
        valid_states = df[~df['estado'].isin(noise_filter)]
        
        analytics = {
            "total": int(len(df)),
            "top_states": valid_states['estado'].value_counts().head(5).reset_index().values.tolist(),
            "top_promoters": df[~df['promovente'].str.contains('DESCONOCIDO|ENCONTRADO|EXTRACCIÓN|ID_PROYECTO|EL ID', na=True, case=False)]['promovente'].value_counts().head(5).reset_index().values.tolist()
        }
        return analytics
    except Exception as e:
        print(f"Analytics Error: {e}")
        return {"total": 0, "risk_counts": {}, "top_states": [], "top_promoters": []}

@app.post("/api/control")
async def control_agent(request: Request):
    data = await request.json()
    action = data.get("action")
    
    # Path to ctl script
    ctl_script = os.path.join(BASE_DIR, "agent", "zohar_ctl.sh")
    
    try:
        if action == "restart":
            subprocess.run([ctl_script, "stop"], check=False)
            subprocess.Popen([ctl_script, "start-daemon"])
            return {"status": "restarting"}
        elif action == "stop":
            subprocess.run([ctl_script, "stop"], check=False)
            return {"status": "stopped"}
        elif action == "retry":
            subprocess.run([ctl_script, "retry-failed"], check=False)
            subprocess.run([ctl_script, "stop"], check=False)
            subprocess.Popen([ctl_script, "start-daemon"])
            return {"status": "retrying"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
    return {"status": "unknown_action"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
