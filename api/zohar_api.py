"""
ZOHAR API - FastAPI Backend
Puerto: 8081
Sirve el dashboard y los endpoints de la API de monitoreo.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import subprocess
import re
import os
import json

app = FastAPI(title="Zohar Lean API", version="5.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

HOME = os.path.expanduser("~")
CSV_FILE = os.path.join(HOME, "zohar_historico_proyectos.csv")
STATE_FILE = os.path.join(HOME, "zohar_agent_state.json")

# Servir dashboard
app.mount("/static", StaticFiles(directory=os.path.join(HOME, "dashboard")), name="static")

@app.get("/")
def read_index():
    return FileResponse(os.path.join(HOME, "dashboard/index.html"))

@app.get("/api/status")
def get_status():
    temp = "N/A"
    try:
        out = subprocess.check_output(['sensors'], text=True)
        m = re.search(r'(?:CPU|temp1):\s+\+?([\d\.]+)', out)
        if m: temp = f"{m.group(1)}°C"
    except: pass
    return {"cpu_temp": temp, "llama_status": "🟢 Ready", "system": "Zohar Lean"}

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
        with open(CSV_FILE, mode='r') as f:
            lines = f.readlines()
            for line in lines[1:]:
                p = line.strip().split(',')
                if len(p) >= 6:
                    projects.append({
                        "ID_PROYECTO": p[1],
                        "ESTADO": p[2],
                        "MUNICIPIO": p[3],
                        "PROYECTO": p[4],
                        "PROMOVENTE": p[5],
                        "RIESGO": p[6] if len(p) > 6 else "bajo"
                    })
        return projects[-50:]
    except: return []

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
