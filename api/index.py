"""
╔══════════════════════════════════════════════════════════════════╗
║  ZOHAR API — Vercel Serverless (Cloud Mode)                      ║
║  Lee desde Supabase en lugar de SQLite/DuckDB local              ║
║  Compatible con Vercel Python Runtime                            ║
╚══════════════════════════════════════════════════════════════════╝

ARQUITECTURA:
  Local (Ryzen 5):  Agent → extrae → SQLite → sync_to_supabase.py → Supabase
  Cloud (Vercel):   Dashboard → API (este archivo) → Supabase
"""

import os
import json
import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# ─── Detectar entorno ────────────────────────────────────────
IS_VERCEL = os.environ.get("VERCEL") == "1"
IS_LOCAL  = not IS_VERCEL

# ─── Supabase Client ─────────────────────────────────────────
try:
    from supabase import create_client, Client
except ImportError:
    create_client = None

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
    load_dotenv(Path(__file__).parent.parent / ".env.local")
except ImportError:
    pass

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://gmrnujwviunegvyuslrs.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_PUBLISHABLE_KEY")

sb: Client = None
if create_client and SUPABASE_URL and SUPABASE_KEY:
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─── App ──────────────────────────────────────────────────────
app = FastAPI(title="Zohar Intelligence API — Cloud")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Helpers ──────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
DASHBOARD_DIR = BASE_DIR / "dashboard"


def _require_sb():
    """Valida que Supabase esté conectado."""
    if sb is None:
        raise HTTPException(status_code=503, detail="Supabase no configurado")


# ═══════════════════════════════════════════════════════════════
# RUTAS - Compatibles con Vercel Serverless
# ═══════════════════════════════════════════════════════════════

# ─── Frontend ─────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def get_index():
    index_path = DASHBOARD_DIR / "index.html"
    if index_path.exists():
        return index_path.read_text()
    return "<h1>Zohar Dashboard no encontrado</h1>"

@app.get("/aire", response_class=HTMLResponse)
async def get_aire():
    aire_path = DASHBOARD_DIR / "aire.html"
    if aire_path.exists():
        return aire_path.read_text()
    return "<h1>Mapa de Aire no encontrado</h1>"


# ─── Status ───────────────────────────────────────────────────
@app.get("/api/status")
async def get_status():
    _require_sb()
    agent_data = {"pdf": "INACTIVO", "action": "CLOUD_MODE", "target": "VERCEL"}
    try:
        res = sb.table("agente_status").select("*").eq("id", 1).execute()
        if res.data:
            s = res.data[0]
            agent_data = {
                "pdf": s.get("pdf", ""),
                "action": s.get("action", ""),
                "target": s.get("target", ""),
                "time": (s.get("last_seen", "") or "")[-8:]
            }
    except Exception:
        pass

    return {
        "cpu_temp": "CLOUD",
        "llama_status": "Cloud Mode (Supabase)",
        "agent_running": bool(agent_data.get("action") not in ["INACTIVO", "CLOUD_MODE"]),
        "llama_ok": True,
        "mode": "vercel-cloud",
        "agent_state": agent_data
    }


@app.get("/api/agent_state")
async def get_agent_state():
    _require_sb()
    try:
        res = sb.table("agente_status").select("*").eq("id", 1).execute()
        if res.data:
            s = res.data[0]
            return {
                "pdf": s.get("pdf", "INACTIVO"),
                "action": s.get("action", "ESPERA"),
                "target": s.get("target", "NINGUNO"),
                "time": (s.get("last_seen", "") or "")[-8:]
            }
    except Exception:
        pass
    return {"pdf": "INACTIVO", "action": "ESPERA", "target": "NINGUNO"}


# ─── Proyectos (Enfoque 2026) ────────────────────────────────
@app.get("/api/projects")
async def get_projects():
    _require_sb()
    try:
        res = sb.table("proyectos") \
            .select("*") \
            .eq("anio", 2026) \
            .order("created_at", desc=True) \
            .limit(200) \
            .execute()

        # Normalizar para el Dashboard (mayúsculas)
        projects = []
        for row in res.data:
            projects.append({
                "ID_PROYECTO": row.get("id_proyecto"),
                "ANIO": row.get("anio"),
                "PROMOVENTE": row.get("promovente"),
                "PROYECTO": row.get("proyecto"),
                "ESTADO": row.get("estado"),
                "MUNICIPIO": row.get("municipio"),
                "SECTOR": row.get("sector"),
                "INSIGHT": row.get("insight"),
                "GROUNDED": row.get("grounded"),
                "AUDIT_STATUS": row.get("audit_status"),
                "CONFIDENCE_SCORE": row.get("confidence_score"),
                "COORDENADAS": row.get("coordenadas"),
                "CREATED_AT": row.get("created_at"),
            })
        return projects
    except Exception as e:
        print(f"Error fetching projects: {e}")
        return []


@app.get("/proyectos/{pid}")
async def get_project_detail(pid: str):
    _require_sb()
    try:
        res = sb.table("proyectos").select("*").eq("id_proyecto", pid).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Proyecto no hallado")
        return res.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Link Normalizer ──────────────────────────────────────────
_GIS_BASE = "https://gisviewer.semarnat.gob.mx"

def _normalize_links_cloud(links_raw, clave: str) -> dict:
    """Normaliza links: relativos→absolutos, http→https, genéicos→específicos."""
    if not links_raw or not isinstance(links_raw, dict):
        return {}
    out = {}
    for key, url in links_raw.items():
        if not isinstance(url, str) or not url.strip():
            continue
        url = url.strip()
        if url.startswith('/'):
            url = _GIS_BASE + url
        if 'mapas.semarnat.gob.mx' in url and '?' not in url:
            url = f"{_GIS_BASE}/Aplicaciones/Tramites/ConsultaN.html?idS={clave}"
        if url.startswith('http://'):
            url = 'https://' + url[7:]
        if url.startswith('Gacetas/') or url.startswith('gacetas/'):
            url = f"{_GIS_BASE}/{url}"
        out[key] = url
    return out


# ─── Análisis Histórico/Estratégico 2026 ─────────────────────
@app.get("/api/historic_consultations")
async def get_historic_consultations():
    _require_sb()
    combined_data = []

    # Datos de proyectos 2026 desde Supabase (live extractions)
    try:
        res = sb.table("proyectos") \
            .select("id_proyecto,promovente,proyecto,estado,municipio,sector,anio,created_at,sources,grounded") \
            .eq("anio", 2026) \
            .order("created_at", desc=True) \
            .execute()

        for row in res.data:
            combined_data.append({
                "Clave": row.get("id_proyecto", ""),
                "Modalidad": "MIA-P" if row.get("grounded") else "MIA",
                "Promovente": row.get("promovente", ""),
                "Proyecto": row.get("proyecto", ""),
                "Ubicacion": f"{row.get('estado', '')}, {row.get('municipio', '')}",
                "Sector": row.get("sector", ""),
                "Fecha": row.get("created_at", ""),
                "Año": str(row.get("anio", 2026)),
                "Estatus": "VERIFIED_2026" if row.get("grounded") else "EXTRACTED_2026",
                "links": row.get("sources", [])
            })
    except Exception as e:
        print(f"Error loading from Supabase: {e}")

    # Merge: static JSON con TODOS los años (no solo 2026)
    json_path = BASE_DIR / "agent" / "semarnat_historic_consultations.json"
    if json_path.exists():
        try:
            existing_claves = {str(item["Clave"]).strip().upper() for item in combined_data}
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for item in data:
                clave = item.get("clave", "")
                if clave.strip().upper() in existing_claves:
                    continue  # Ya está desde Supabase
                anio = str(item.get("anio", ""))
                combined_data.append({
                    "Clave": clave,
                    "Modalidad": item.get("modalidad", ""),
                    "Promovente": item.get("promovente", ""),
                    "Proyecto": item.get("proyecto", ""),
                    "Ubicacion": item.get("ubicacion", ""),
                    "Sector": item.get("sector", ""),
                    "Fecha": item.get("fechas", ""),
                    "Año": anio,
                    "Estatus": "CONCLUIDO_2026" if anio == "2026" else "HISTORICO",
                    "links": _normalize_links_cloud(item.get("links", {}), clave)
                })
        except Exception:
            pass

    return combined_data


# ─── Datos CSV / Aire ─────────────────────────────────────────
@app.get("/api/csv_data")
async def get_csv_data(type: str = "regulatory"):
    if type == "air_quality":
        _require_sb()
        try:
            # Leer de Supabase en lugar de DuckDB local
            res = sb.table("aire_emisiones") \
                .select("*") \
                .limit(5000) \
                .execute()

            records = []
            for row in res.data:
                records.append({
                    "Entidad_federativa": row.get("entidad", ""),
                    "Municipio": row.get("municipio", ""),
                    "Tipo_de_Fuente": row.get("fuente", ""),
                    "SO_2": row.get("so2"),
                    "CO": row.get("co"),
                    "NOx": row.get("nox"),
                    "COV": row.get("cov"),
                    "PM_010": row.get("pm10"),
                    "PM_2_5": row.get("pm25"),
                    "NH_3": row.get("nh3"),
                    "lat": row.get("lat"),
                    "lon": row.get("lon"),
                })
            return records
        except Exception as e:
            print(f"Error reading air data from Supabase: {e}")

        # Fallback: snapshot JSON
        snapshot = DASHBOARD_DIR / "aire_snapshot.json"
        if snapshot.exists():
            with open(snapshot, 'r') as f:
                return json.load(f)
        return []

    else:
        # Para regulatory y otros CSVs, leer del filesystem si existe
        import csv as csvmod
        file_map = {
            "regulatory": BASE_DIR / "ordenamientos_ecologicos_expedidos.csv",
        }
        target = file_map.get(type)
        if not target or not target.exists():
            return []
        try:
            with open(target, 'r', encoding='utf-8') as f:
                reader = csvmod.DictReader(f)
                rows = []
                for i, row in enumerate(reader):
                    if i >= 200:
                        break
                    rows.append({k.strip(): (v or "").strip() for k, v in row.items()})
                return rows
        except Exception:
            return []


# ─── Reporte Ambiental ────────────────────────────────────────
@app.get("/proyectos/{pid}/report")
async def get_project_report(pid: str):
    _require_sb()
    try:
        # Obtener ubicación
        proj_res = sb.table("proyectos").select("municipio,anio").eq("id_proyecto", pid).execute()
        if not proj_res.data:
            raise HTTPException(status_code=404, detail="Proyecto no hallado")

        municipio = proj_res.data[0].get("municipio", "")
        year = proj_res.data[0].get("anio")

        # Consultar emisiones de esa zona
        aire_res = sb.table("aire_emisiones") \
            .select("so2,nox,pm25") \
            .ilike("municipio", f"%{municipio}%") \
            .execute()

        if not aire_res.data:
            return {"pid": pid, "execution_path": "SKIPPED_NO_DATA"}

        # Calcular promedios y máximos
        vals = aire_res.data
        avg_so2 = sum(r.get("so2", 0) or 0 for r in vals) / len(vals)
        avg_nox = sum(r.get("nox", 0) or 0 for r in vals) / len(vals)
        avg_pm25 = sum(r.get("pm25", 0) or 0 for r in vals) / len(vals)

        data = {
            "avg": {"so2": round(avg_so2, 2), "nox": round(avg_nox, 2), "pm25": round(avg_pm25, 2)},
            "max": {
                "so2": round(max((r.get("so2") or 0) for r in vals), 2),
                "nox": round(max((r.get("nox") or 0) for r in vals), 2),
                "pm25": round(max((r.get("pm25") or 0) for r in vals), 2),
            }
        }

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
        if violations and any(v["excess_pct"] > 20 for v in violations):
            path = "CRITICAL_SIGNATURE_REQUIRED"
        elif risk_score > 50:
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Stats / Diagnostics (Cloud) ─────────────────────────────
@app.get("/api/diagnostics")
async def get_diagnostics():
    _require_sb()
    stats = {}
    try:
        res = sb.table("proyectos") \
            .select("anio,grounded,audit_status") \
            .eq("anio", 2026) \
            .execute()

        total = len(res.data)
        grounded = sum(1 for r in res.data if r.get("grounded"))
        pending = sum(1 for r in res.data if r.get("audit_status") == "pending")

        stats["queue"] = {
            "total": total,
            "success": grounded,
            "pending": pending,
            "failed": total - grounded - pending,
            "progress_pct": round((grounded / total) * 100, 1) if total > 0 else 0,
        }
        stats["agent"] = {"running": False, "mode": "cloud"}
    except Exception:
        pass

    return {
        "ts": datetime.datetime.now().isoformat(),
        "services": stats,
        "mode": "vercel-cloud-v2"
    }


@app.get("/api/logs")
async def get_logs():
    """En modo cloud, los logs no están disponibles localmente."""
    return [{"ts": datetime.datetime.now().isoformat(), "level": "INFO", "msg": "Cloud mode: logs se consultan desde el dashboard local"}]


# ─── NOTA:  En entorno local, se usa api/main.py directamente
# (uvicorn api.main:app). Este archivo (index.py) es SOLO para Vercel.
# No importar main.py aquí — las rutas de Vercel apuntan a este archivo.

