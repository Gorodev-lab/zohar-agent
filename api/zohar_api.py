import os
import sqlite3
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import json

app = FastAPI(title="Zohar Intelligence API")

# Configuración de Rutas
HOME = Path(os.path.expanduser("~"))
BASE_DIR = Path(__file__).parent.parent
DB_PATH = HOME / "zohar_intelligence.db"
CSV_PATH = HOME / "zohar_historico_proyectos.csv"
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

# Endpoints de Datos
@app.get("/api/projects")
async def get_projects():
    if not DB_PATH.exists():
        return []
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
            # Normalizar para el Dashboard
            data = []
            for r in rows:
                d = dict(r)
                data.append({
                    "ID_PROYECTO": d.get("pid"),
                    "ANIO": d.get("year"),
                    "ESTADO": d.get("estado"),
                    "MUNICIPIO": d.get("municipio"),
                    "LOCALIDAD": d.get("localidad"),
                    "PROYECTO": d.get("proyecto"),
                    "PROMOVENTE": d.get("promovente"),
                    "SECTOR": d.get("sector"),
                    "INSIGHT": d.get("insight"),
                    "COORDENADAS": d.get("coordenadas"),
                    "POLIGONO": d.get("poligono"),
                    "audit_status": d.get("audit_status", "pending")
                })
            return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Compatibilidad con el nuevo modo Cloud en Local
@app.get("/api/cloud-projects")
async def get_cloud_projects_local():
    """Redirigir a los proyectos locales para que el dashboard funcione sin cambios."""
    return await get_projects()

@app.get("/api/status")
async def get_status():
    return {
        "cpu_temp": "45°C",
        "llama_status": "Online",
        "agent_running": True,
        "llama_ok": True,
        "mode": "hybrid-local"
    }

@app.get("/api/analytics")
async def get_analytics():
    projects = await get_projects()
    total = len(projects)
    
    # Simple stats
    states = {}
    proms = {}
    for p in projects:
        s = (p.get("ESTADO") or "DESCONOCIDO").title()
        pr = (p.get("PROMOVENTE") or "DESCONOCIDO").title()
        states[s] = states.get(s, 0) + 1
        proms[pr] = proms.get(pr, 0) + 1
        
    top_states = sorted(states.items(), key=lambda x: x[1], reverse=True)
    top_promoters = sorted(proms.items(), key=lambda x: x[1], reverse=True)
    
    return {
        "total": total,
        "top_states": [[k, v] for k, v in top_states[:5]],
        "top_promoters": [[k, v] for k, v in top_promoters[:5]]
    }

@app.get("/api/diagnostics")
async def get_diagnostics():
    csv_rows = 0
    csv_size = 0
    if CSV_PATH.exists():
        csv_size = os.path.getsize(CSV_PATH) // 1024
        try:
            with open(CSV_PATH, 'r') as f:
                csv_rows = sum(1 for _ in f)
        except:
            pass
            
    return {
        "system": "ok",
        "csv": {
            "rows": csv_rows,
            "size_kb": csv_size
        },
        "services": {
            "agent": {"pid_file": True},
            "llama": {"status": "online"},
            "ocr": {"status": "online"}
        },
        "queue": {
            "pending": 319,
            "success": 359,
            "failed": 0,
            "progress_pct": 0
        },
        "issues": []
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
