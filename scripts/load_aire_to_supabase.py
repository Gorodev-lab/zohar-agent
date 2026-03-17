#!/usr/bin/env python3
"""
Carga d3_aire01_49_1.csv → Supabase public.aire_emisiones
Uso: zohar_venv/bin/python scripts/load_aire_to_supabase.py
"""
import os, csv, sys, logging
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env.local")
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

try:
    from supabase import create_client
except ImportError:
    print("❌  pip install supabase"); sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("aire-load")

CSV_PATH    = Path(__file__).parent.parent / "d3_aire01_49_1.csv"
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://gmrnujwviunegvyuslrs.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_PUBLISHABLE_KEY")
TABLE       = "aire_emisiones"
BATCH_SIZE  = 200

def safe_float(v):
    try:
        return float(v) if v not in ("", "*", "N/D") else None
    except (ValueError, TypeError):
        return None

def load():
    if not SUPABASE_KEY:
        log.error("❌  SUPABASE_KEY no encontrada"); sys.exit(1)
    if not CSV_PATH.exists():
        log.error(f"❌  CSV no encontrado: {CSV_PATH}"); sys.exit(1)

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Limpiar tabla antes de recargar
    log.info("🧹 Limpiando tabla aire_emisiones...")
    sb.table(TABLE).delete().neq("id", 0).execute()

    rows_processed = 0
    batch = []

    with open(CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            record = {
                "entidad":   (row.get("Entidad_federativa") or row.get("Entidad") or "").strip(),
                "municipio": (row.get("Municipio") or "").strip(),
                "fuente":    (row.get("Tipo_de_Fuente") or "").strip(),
                "so2":  safe_float(row.get("SO_2")),
                "co":   safe_float(row.get("CO")),
                "nox":  safe_float(row.get("NOx")),
                "cov":  safe_float(row.get("COV")),
                "pm10": safe_float(row.get("PM_010")),
                "pm25": safe_float(row.get("PM_2_5")),
                "nh3":  safe_float(row.get("NH_3")),
            }
            if not record["municipio"]:
                continue
            batch.append(record)

            if len(batch) >= BATCH_SIZE:
                sb.table(TABLE).insert(batch).execute()
                rows_processed += len(batch)
                log.info(f"  ↑ {rows_processed} filas cargadas...")
                batch = []

    if batch:
        sb.table(TABLE).insert(batch).execute()
        rows_processed += len(batch)

    log.info(f"\n✅  CARGA COMPLETADA: {rows_processed} filas en '{TABLE}'")
    log.info(f"   Vista disponible: proyectos_con_riesgo_ambiental")

if __name__ == "__main__":
    load()
