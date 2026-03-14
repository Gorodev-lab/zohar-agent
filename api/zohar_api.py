"""
ZOHAR API - FastAPI Backend v6.0
Integridad de Datos Esoteria - Grounding, Auditing & Governance
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import subprocess
import urllib.request
import re
import os
import json
import csv
import pandas as pd
import datetime
import sqlite3
import unicodedata

app = FastAPI(title="Zohar Integrity API", version="6.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────────────────
API_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(API_DIR)
HOME = os.path.expanduser("~")

DB_PATH = os.path.join(HOME, "zohar_intelligence.db")
CSV_PATH = os.path.join(HOME, "zohar_historico_proyectos.csv")
STATE_FILE = os.path.join(HOME, "zohar_agent_state.json")
DASHBOARD_DIR = os.path.join(BASE_DIR, "dashboard")

# BLACKLIST CRÍTICA (Detectores de Hallucinación)
FORBIDDEN_PATTERNS = [
    r"desconocido", r"null", r"none", r"n/a", r"placeholder", r"undefined",
    r"sistema de gestión", r"proyecto de inversión", r"información del proyecto",
    r"estudio de impacto", r"estudio de sustentabilidad", r"extracción automática",
    r"gaceta ecológica", r"semarnat gazette", r"gaceta semarnat"
    r"bitácora del trámite", r"consulta de trámites", r"gaceta ecológica",
    r"id_proyecto", r"el id", r"nombre del proyecto", r"nombre del promovente",
    r"extrae el", r"error de extracción", r"sin información", r"generic name",
    r"^.{0,8}$"
]

# Servir dashboard
app.mount("/static", StaticFiles(directory=DASHBOARD_DIR), name="static")

@app.get("/")
def read_index():
    return FileResponse(os.path.join(DASHBOARD_DIR, "index.html"))

# ─────────────────────────────────────────────────────────
# CORE: AUDITORÍA DE DATOS
# ─────────────────────────────────────────────────────────
def is_valid_record(proyecto, promovente, fuentes):
    """Verifica si un registro es confiable."""
    p = str(proyecto).lower()
    m = str(promovente).lower()
    f = str(fuentes).lower()
    
    # Bajamos la exigencia a 10 chars para el nombre si no hay fuentes.
    # Si el nombre es muy corto (< 10) y no hay fuentes, lo consideramos sospechoso.
    if not ("http" in f) and len(p) < 10: 
        return False
        
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, p) or re.search(pattern, m): return False
    
    if len(p) < 5 or len(m) < 3: return False
    return True

def load_audited_data():
    all_projects = []
    base_cols = ["ANIO", "ID_PROYECTO", "ESTADO", "MUNICIPIO", "LOCALIDAD", 
                 "PROYECTO", "PROMOVENTE", "SECTOR", "INSIGHT", 
                 "COORDENADAS", "POLIGONO", "FUENTES"]
    audit_cols = ["audit_status", "auditor_notes", "confidence_score", "REASONING", "SNIPPET", "LINK_PID"]
    all_cols = base_cols + audit_cols

    # 1. SQLite (Gold Standard)
    if os.path.exists(DB_PATH):
        try:
            with sqlite3.connect(DB_PATH) as conn:
                df_db = pd.read_sql_query("SELECT * FROM projects", conn)
                if not df_db.empty:
                    df_db = df_db.rename(columns={
                        'year': 'ANIO', 'pid': 'ID_PROYECTO', 'estado': 'ESTADO',
                        'municipio': 'MUNICIPIO', 'proyecto': 'PROYECTO',
                        'promovente': 'PROMOVENTE', 'sector': 'SECTOR',
                        'insight': 'INSIGHT', 'sources': 'FUENTES'
                    })
                    # Asegurar que existan las columnas de auditoría
                    for c in audit_cols:
                        if c not in df_db.columns: df_db[c] = None
                    if 'LOCALIDAD' not in df_db.columns: df_db['LOCALIDAD'] = "N/A"
                    if 'COORDENADAS' not in df_db.columns: df_db['COORDENADAS'] = ""
                    if 'POLIGONO' not in df_db.columns: df_db['POLIGONO'] = ""
                    
                    if 'reasoning' in df_db.columns and 'REASONING' not in df_db.columns:
                        df_db = df_db.rename(columns={'reasoning': 'REASONING'})
                    if 'context_snippet' in df_db.columns and 'SNIPPET' not in df_db.columns:
                        df_db = df_db.rename(columns={'context_snippet': 'SNIPPET'})
                    if 'cross_year_link' in df_db.columns and 'LINK_PID' not in df_db.columns:
                        df_db = df_db.rename(columns={'cross_year_link': 'LINK_PID'})
                    
                    # Asegurar columnas faltantes y eliminar duplicadas
                    df_db = df_db.loc[:, ~df_db.columns.duplicated()]
                    for c in all_cols:
                        if c not in df_db.columns: df_db[c] = None

                    all_projects.append(df_db[all_cols])
        except Exception as e: print(f"DB Error: {e}")

    # 2. CSV (Silver Data - legacy, no tiene score usualmente)
    if os.path.exists(CSV_PATH):
        try:
            # El CSV solo tiene las base_cols
            df_csv = pd.read_csv(CSV_PATH, names=base_cols, header=None, on_bad_lines='skip')
            for c in audit_cols: df_csv[c] = None
            df_csv['audit_status'] = 'legacy'
            all_projects.append(df_csv[all_cols])
        except Exception as e: print(f"CSV Error: {e}")

    if not all_projects:
        return pd.DataFrame(columns=all_cols)
    
    df = pd.concat(all_projects).drop_duplicates(subset=['ID_PROYECTO'], keep='first')
    
    # Heurística: Densidad de Proponentes (Señal de Alerta Estratégica)
    # Si un promovente tiene > 3 proyectos en el mismo estado, marcamos señal
    df['density_count'] = df.groupby(['PROMOVENTE', 'ESTADO'])['ID_PROYECTO'].transform('count')
    df['SIGNAL'] = df['density_count'].apply(lambda c: "HIGH_DENSITY" if c > 3 else "NORMAL")

    # Métrica de Reputación (Fase 3)
    # Calculamos reputación simple basada en auditorías previas en el DF actual
    rep_map = {}
    for prom in df['PROMOVENTE'].unique():
        sub = df[df['PROMOVENTE'] == prom]
        approved = len(sub[sub['audit_status'] == 'audited'])
        total = len(sub)
        if total > 2 and approved/total > 0.8: rep_map[prom] = "TRUSTED"
        elif (sub['audit_status'] == 'rejected').any(): rep_map[prom] = "RISKY"
    
    df['REPUTATION'] = df['PROMOVENTE'].map(lambda x: rep_map.get(x, "NEW"))

    # Aplicar Auditoría Final
    df['is_valid'] = df.apply(lambda r: is_valid_record(r['PROYECTO'], r['PROMOVENTE'], r['FUENTES']), axis=1)
    df_clean = df[df['is_valid'] == True].copy()
    
    return df_clean[all_cols + ['SIGNAL', 'REPUTATION']]

@app.get("/api/projects")
def get_projects():
    try:
        df = load_audited_data()
        projects = df.fillna("").to_dict(orient="records")
        projects.sort(key=lambda x: (str(x.get('ANIO', '')), str(x.get('ID_PROYECTO', ''))), reverse=True)
        return projects
    except Exception as e:
        print(f"API Error: {e}")
        return []

@app.get("/api/analytics")
def get_analytics():
    try:
        df = load_audited_data()
        if df.empty:
            return {"total": 0, "top_states": [], "top_promoters": []}

        df['ESTADO'] = df['ESTADO'].fillna('DESCONOCIDO').str.upper().str.strip()
        df['PROMOVENTE'] = df['PROMOVENTE'].fillna('DESCONOCIDO').str.upper().str.strip()
        
        noise = ['DE', 'LOS', 'EL', 'LA', 'SAN', 'DEL', ' ', '']
        valid_states = df[~df['ESTADO'].isin(noise)]
        
        return {
            "total": int(len(df)),
            "top_states": [[str(s).title(), int(c)] for s, c in valid_states['ESTADO'].value_counts().head(5).items()],
            "top_promoters": [[str(p).title(), int(c)] for p, c in df['PROMOVENTE'].value_counts().head(5).items()]
        }
    except Exception as e:
        print(f"Analytics Error: {e}")
        return {"total": 0, "top_states": [], "top_promoters": []}

# ─────────────────────────────────────────────────────────
# NEW: GOVERNANCE ENDPOINT (AUDIT)
# ─────────────────────────────────────────────────────────
@app.post("/api/audit")
async def audit_project(request: Request):
    data = await request.json()
    pid = data.get("pid")
    status = data.get("status") # 'audited', 'rejected', 'pending'
    notes = data.get("notes", "")

    if not pid or not status:
        return {"status": "error", "message": "Missing pid or status"}

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                UPDATE projects 
                SET audit_status = ?, auditor_notes = ?
                WHERE pid = ?
            """, (status, notes, pid))
            return {"status": "ok", "pid": pid, "new_status": status}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ─────────────────────────────────────────────────────────
# RESTO DE ENDPOINTS
# ─────────────────────────────────────────────────────────
@app.get("/api/status")
def get_status():
    llama_ok, _ = _check_service("http://127.0.0.1:8001/v1/models")
    return {
        "cpu_temp": "N/A", 
        "llama_status": "Ready" if llama_ok else "Offline", 
        "agent_running": os.path.exists("/tmp/zohar_agent_v2.pid"),
        "llama_ok": llama_ok
    }

def _check_service(url, timeout=5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r: return True, ""
    except: return False, ""

@app.get("/api/agent_state")
def get_agent_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f: return json.load(f)
        except: pass
    return {"pdf": "IDLE", "action": "STANDBY"}

@app.get("/api/logs")
def get_logs():
    log_file = os.path.join(BASE_DIR, "agent", "zohar_agent.jsonl")
    if not os.path.exists(log_file): return []
    try:
        with open(log_file, "r") as f:
            lines = f.readlines()[-20:]
            logs = []
            for line in lines:
                try:
                    e = json.loads(line)
                    logs.append({"ts": e.get("ts","")[-8:], "msg": e.get("msg",""), "level": e.get("level","INFO")})
                except: continue
            return logs
    except: return []

@app.post("/api/control")
async def control_agent(request: Request):
    data = await request.json()
    action = data.get("action")
    ctl = os.path.join(BASE_DIR, "agent", "zohar_ctl.sh")
    if action == "restart":
        subprocess.run([ctl, "stop"], check=False)
        subprocess.Popen([ctl, "start-daemon"])
    elif action == "stop": subprocess.run([ctl, "stop"], check=False)
    return {"status": "ok"}

@app.get("/api/diagnostics")
def get_diagnostics():
    # 1. Health Checks
    llama_ok, _ = _check_service("http://127.0.0.1:8001/v1/models")
    ocr_ok, _   = _check_service("http://127.0.0.1:8002/v1/models")
    agent_running = os.path.exists("/tmp/zohar_agent_v2.pid")
    
    # 2. Process check (Real-time fallback)
    def _get_procs(pattern):
        try:
            res = subprocess.check_output(["ps", "aux"], text=True)
            return [line for line in res.splitlines() if pattern in line and "grep" not in line]
        except: return []

    # 3. Queue & Data
    csv_rows = 0
    csv_size = 0
    if os.path.exists(CSV_PATH):
        csv_rows = sum(1 for _ in open(CSV_PATH))
        csv_size = os.path.getsize(CSV_PATH) // 1024

    queue_data = {"pending": 0, "success": 0, "failed": 0, "progress_pct": 0, "by_year": {}}
    if os.path.exists(os.path.join(BASE_DIR, "agent", "zohar_queue.json")):
        try:
            with open(os.path.join(BASE_DIR, "agent", "zohar_queue.json"), 'r') as f:
                q = json.load(f)
                # Soportar tanto dict como list
                items = q.values() if isinstance(q, dict) else q
                queue_data["pending"] = len([i for i in items if i.get("status") == "pending"])
                queue_data["success"] = len([i for i in items if i.get("status") == "success"])
                queue_data["failed"]  = len([i for i in items if i.get("status") in ["failed", "error"]])
                total = len(items)
                if total > 0:
                    queue_data["progress_pct"] = int((queue_data["success"] / total) * 100)
                # Group by year
                for item in items:
                    yr = str(item.get("year", "2025"))
                    queue_data["by_year"][yr] = queue_data["by_year"].get(yr, 0) + 1
        except Exception as e:
            print(f"Queue Diagnostics Error: {e}")

    # 4. Anomaly Detection
    issues = []
    if not llama_ok: issues.append({"severity": "critical", "component": "LLM", "msg": "Mistral-7B Offline", "hint": "Check port 8001", "cmd": "tail -f llama_8001.log"})
    if not ocr_ok:   issues.append({"severity": "warning", "component": "OCR", "msg": "Qwen-VL Busy/Offline", "hint": "Check port 8002"})
    if not agent_running: issues.append({"severity": "critical", "component": "AGENT", "msg": "Extractor stopped", "cmd": "bash zohar_ctl.sh start"})

    return {
        "ts": datetime.datetime.now().isoformat(),
        "services": {
            "llama": {"status": "online" if llama_ok else "offline", "running": True, "procs": _get_procs("8001")},
            "ocr":   {"status": "online" if ocr_ok else "offline", "running": True, "procs": _get_procs("8002")},
            "agent": {"running": agent_running, "pid_file": agent_running, "procs": _get_procs("zohar_agent_v2")}
        },
        "csv": {"rows": csv_rows, "size_kb": csv_size},
        "queue": queue_data,
        "issues": issues
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
