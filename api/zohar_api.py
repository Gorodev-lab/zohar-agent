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
import urllib.request
import re
import os
import json
import csv
import pandas as pd
import datetime

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

def _check_service(url: str, timeout: int = 6) -> tuple[bool, str]:
    """Verifica disponibilidad HTTP. Retorna (ok, info). Timeout mayor para modelos ocupados."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            body = r.read().decode("utf-8", errors="replace")[:200]
            return True, body
    except Exception as e:
        return False, str(e)[:100]

def _proc_running(pattern: str) -> bool:
    """True si hay un proceso vivo que coincide con el pattern."""
    try:
        out = subprocess.check_output(["pgrep", "-f", pattern], text=True, timeout=2).strip()
        return bool(out)
    except Exception:
        return False

import unicodedata
def _strip_ctrl(text: str) -> str:
    """Elimina emojis y caracteres non-ASCII para estética terminal."""
    return ''.join(c for c in text if ord(c) < 128 or unicodedata.category(c) not in ('So','Cs','Cf'))

@app.get("/api/status")
def get_status():
    temp = "N/A"
    try:
        out = subprocess.check_output(['sensors'], text=True)
        m = re.search(r'(?:CPU|temp1|Tdie):\s+\+?([\d\.]+)', out)
        if m: temp = f"{m.group(1)}°C"
    except: pass
    
    # Check if agent PID is active
    is_active = os.path.exists("/tmp/zohar_agent_v2.pid")
    if is_active:
        try:
            pid = open("/tmp/zohar_agent_v2.pid").read().strip()
            # Verify PID is actually alive
            os.kill(int(pid), 0)
        except (OSError, ValueError):
            is_active = False

    # Check llama-server via /v1/models (llama-cpp-python no tiene /health)
    llama_ok, _ = _check_service("http://127.0.0.1:8001/v1/models")
    
    return {
        "cpu_temp": temp, 
        "llama_status": "System Ready" if llama_ok else "LLM Offline", 
        "system": "Zohar Intelligence Core",
        "agent_running": is_active,
        "llama_ok": llama_ok,
    }

@app.get("/api/agent_state")
def get_agent_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {"pdf": "IDLE", "action": "STANDBY", "target": "NONE"}

@app.get("/api/logs")
def get_logs():
    log_file = os.path.join(BASE_DIR, "agent", "zohar_agent.jsonl")
    if not os.path.exists(log_file): return []
    try:
        with open(log_file, "r") as f:
            # Leer últimas 15 líneas
            lines = f.readlines()[-15:]
            logs = []
            for line in lines:
                try:
                    entry = json.loads(line)
                    logs.append({
                        "ts":    entry.get("ts", "")[-8:],
                        "msg":   _strip_ctrl(entry.get("msg", "")),
                        "level": entry.get("level", "INFO")
                    })
                except: continue
            return logs
    except: return []

@app.get("/api/projects")
def get_projects():
    if not os.path.exists(CSV_FILE): return []
    try:
        # Usamos pandas para consistencia con analytics, pero sin header
        cols_v22 = ["ANIO", "ID_PROYECTO", "ESTADO", "MUNICIPIO", "LOCALIDAD", "PROYECTO", "PROMOVENTE", "SECTOR", "INSIGHT", "COORDENADAS", "POLIGONO", "FUENTES"]
        df = pd.read_csv(CSV_FILE, names=cols_v22, header=None, on_bad_lines='skip', index_col=False)
        
        # Detectar si está aterrizado (grounded)
        df['grounded'] = df['FUENTES'].fillna('').apply(lambda x: len(str(x)) > 5)
        
        # FILTRO CRÍTICO: Solo mostrar datos con fuentes verificadas (Grounded)
        df = df[df['grounded'] == True]
        
        # REMOVER ALUCINACIONES: Patrones conocidos de error del modelo
        placeholder_regex = 'DESCONOCIDO|ENCONTRADO|EXTRACCIÓN|ID_PROYECTO|EL ID|PROYECTO EN EVALUACIÓN|ERROR|PLACEHOLDER|NULL|NONE'
        df = df[~df['PROMOVENTE'].fillna('').astype(str).str.contains(placeholder_regex, na=False, case=False)]
        df = df[~df['PROYECTO'].fillna('').astype(str).str.contains(placeholder_regex, na=False, case=False)]
        
        # Convertir a lista de dicts limpiando NaNs
        projects = df.fillna("").to_dict("records")
        
        # Ordenar por Año (Descendente) y luego por ID
        projects.sort(key=lambda x: (str(x.get('ANIO', '')), str(x.get('ID_PROYECTO', ''))), reverse=True)
        return projects[:500]
    except Exception as e:
        print(f"Error reading projects: {e}")
        return []

@app.get("/api/analytics")
def get_analytics():
    if not os.path.exists(CSV_FILE) or os.path.getsize(CSV_FILE) == 0:
        return {"total": 0, "risk_counts": {}, "top_states": [], "top_promoters": []}
    
    try:
        # Usar la misma estructura de columnas que get_projects para consistencia
        cols = ["year", "id", "estado", "municipio", "localidad", "proyecto", "promovente", "sector", "insight", "coordenadas", "poligono", "fuentes"]
        # header=None porque el CSV no tiene cabecera propia
        df = pd.read_csv(CSV_FILE, names=cols, header=None, on_bad_lines='skip', index_col=False)
        
        # Filtro de Grounded (solo datos con fuentes)
        df['grounded'] = df['fuentes'].fillna('').apply(lambda x: len(str(x)) > 5)
        df = df[df['grounded'] == True]
        
        # Clean data
        df['sector'] = df['sector'].fillna('OTROS').str.upper().str.strip()
        df['estado'] = df['estado'].fillna('DESCONOCIDO').str.upper().str.strip()
        df['promovente'] = df['promovente'].fillna('DESCONOCIDO').str.upper().str.strip()
        
        # Filtro de ruido y alucinaciones más agresivo para analytics
        noise_filter = ['DE', 'LOS', 'EL', 'LA', 'SAN', 'SANTA', 'DEL', 'EL ID', 'ID_PROYECTO', 'MUNICIPIO', 'ESTADO', 'ID', ' ', '', 'ANIO', 'YEAR']
        placeholder_regex = 'DESCONOCIDO|ENCONTRADO|EXTRACCIÓN|ID_PROYECTO|EL ID|PROYECTO EN EVALUACIÓN|ERROR|PLACEHOLDER|NULL|NONE'
        
        # Filtrar estados válidos
        df_states = df[~df['estado'].isin(noise_filter) & df['estado'].notna() & (df['estado'] != '')]
        df_states = df_states[~df_states['estado'].str.contains(placeholder_regex, na=False, case=False)]
        
        # Filtrar promoventes válidos (ignorar placeholders)
        df_proms = df[~df['promovente'].str.contains(placeholder_regex, na=True, case=False) & (df['promovente'] != '')]
        df_proms = df_proms[~df_proms['promovente'].isin(noise_filter)]

        analytics = {
            "total": int(len(df)),
            "top_states": [[str(s).title(), int(c)] for s, c in df_states['estado'].value_counts().head(5).items()],
            "top_promoters": [[str(p).title(), int(c)] for p, c in df_proms['promovente'].value_counts().head(5).items()]
        }
        return analytics
    except Exception as e:
        print(f"Analytics Error: {e}")
        return {"total": 0, "top_states": [], "top_promoters": []}

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

@app.get("/api/diagnostics")
def get_diagnostics():
    """Panel de troubleshooting en tiempo real."""
    now = datetime.datetime.now().isoformat(timespec="seconds")

    llama_ok, _ = _check_service("http://127.0.0.1:8001/v1/models")
    ocr_ok,   _ = _check_service("http://127.0.0.1:8002/v1/models")

    def proc_info(pattern):
        try:
            out = subprocess.check_output(["pgrep", "-fa", pattern], text=True, timeout=3).strip()
            lines = [l for l in out.splitlines() if "pgrep" not in l]
            return {"running": bool(lines), "procs": lines[:2]}
        except Exception:
            return {"running": False, "procs": []}

    agent_proc = proc_info("zohar_agent_v2")
    llama_proc = proc_info("llama_cpp.server")
    ocr_proc   = proc_info("qwen2-vl")

    # Diferenciar "busy" de "offline" usando el proceso como señal secundaria
    llama_alive = llama_proc["running"]
    ocr_alive   = ocr_proc["running"]
    llama_status = "online" if llama_ok else ("busy" if llama_alive else "offline")
    ocr_status   = "online" if ocr_ok   else ("busy" if ocr_alive  else "offline")

    # Queue stats
    queue_stats = {"total": 0, "success": 0, "pending": 0, "failed": 0, "by_year": {}, "progress_pct": 0}
    queue_file = os.path.join(BASE_DIR, "agent", "zohar_queue.json")
    if os.path.exists(queue_file):
        try:
            with open(queue_file) as f:
                q = json.load(f)
            by_status = {}
            by_year = {}
            for v in q.values():
                s = v.get("status", "pending")
                by_status[s] = by_status.get(s, 0) + 1
                yr = str(v.get("year", "?"))
                by_year[yr] = by_year.get(yr, 0) + 1
            total = len(q)
            succ  = by_status.get("success", 0)
            queue_stats = {
                "total":        total,
                "success":      succ,
                "pending":      by_status.get("pending", 0),
                "failed":       by_status.get("failed", 0),
                "by_year":      dict(sorted(by_year.items(), reverse=True)[:8]),
                "progress_pct": round(succ / max(total, 1) * 100, 2)
            }
        except Exception as e:
            queue_stats["error"] = str(e)

    # CSV
    csv_info = {"exists": False, "rows": 0, "size_kb": 0}
    if os.path.exists(CSV_FILE):
        try:
            size_kb = round(os.path.getsize(CSV_FILE) / 1024, 1)
            rows    = sum(1 for _ in open(CSV_FILE)) - 1
            csv_info = {"exists": True, "rows": rows, "size_kb": size_kb}
        except Exception as e:
            csv_info["error"] = str(e)

    # Issues — solo critico si el PROCESO no existe (offline real)
    # Si proceso vive pero /v1/models no responde = busy (normal durante extraccion)
    issues = []
    if not llama_alive:
        issues.append({
            "severity": "critical", "component": "llama-server",
            "msg": "LLM process termination - critical infrastructure failure",
            "hint": "Restore via systemd or manual daemon initiation",
            "cmd":  "ps aux | grep llama_cpp"
        })
    elif not llama_ok:
        issues.append({
            "severity": "info", "component": "llama-server",
            "msg": "LLM Latency - Active Inference in Progress",
            "hint": "Resource lock during token generation. Nominal operational state.",
            "cmd":  ""
        })
    if not ocr_alive:
        issues.append({
            "severity": "warning", "component": "ocr-server",
            "msg": "Qwen2-VL process termination - Visual fallback non-operational",
            "hint": "systemctl status zohar-ocr",
            "cmd":  "ps aux | grep qwen2"
        })
    if queue_stats.get("failed", 0) > 50:
        issues.append({
            "severity": "warning", "component": "queue",
            "msg": f"Anomalous detection: {queue_stats['failed']} entities in failed state",
            "hint": "Execute [RETRY-FAILED] or: ./agent/zohar_ctl.sh retry-failed",
            "cmd":  "./agent/zohar_ctl.sh retry-failed"
        })
    
    # Check for Supabase Schema Issues in logs
    recent_logs = get_logs()
    for l in recent_logs:
        if "Could not find the 'coordenadas' column" in l["msg"]:
            issues.append({
                "severity": "critical", "component": "supabase",
                "msg": "Faltan columnas 'coordenadas' y 'poligono' en Supabase",
                "hint": "Ejecute el SQL de migración en el dashboard de Supabase",
                "cmd": "ALTER TABLE proyectos ADD COLUMN coordenadas TEXT, ADD COLUMN poligono TEXT;"
            })
            break
    if not issues:
        issues.append({"severity": "ok", "component": "all", "msg": "All intelligence services operational", "hint": "", "cmd": ""})

    return {
        "ts": now,
        "services": {
            "llama":  {
                "ok": llama_ok, "status": llama_status,
                "running": llama_alive, "procs": llama_proc["procs"]
            },
            "ocr":    {
                "ok": ocr_ok, "status": ocr_status,
                "running": ocr_alive, "procs": ocr_proc["procs"]
            },
            "agent":  {
                "running": agent_proc["running"],
                "pid_file": os.path.exists("/tmp/zohar_agent_v2.pid"),
                "procs": agent_proc["procs"]
            },
            "supabase": {
                "ok": not any("Cloud Sync Error" in l.get("msg", "") for l in get_logs()[-5:]),
                "error": next((l.get("msg", "") for l in get_logs() if "Cloud Sync Error" in l.get("msg", "")), None)
            }
        },
        "queue":  queue_stats,
        "csv":    csv_info,
        "issues": issues,
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
