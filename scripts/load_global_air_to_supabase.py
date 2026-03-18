#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║  LOAD: Kaggle Global Air Quality → Supabase             ║
║  Integra datos globales como benchmark internacional     ║
╚══════════════════════════════════════════════════════════╝
"""
import os, sys, csv, logging
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
    load_dotenv(Path(__file__).parent.parent / ".env.local")
except ImportError:
    pass

try:
    from supabase import create_client
except ImportError:
    print("❌  pip install supabase"); sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("global-air-load")

CSV_PATH = Path.home() / ".cache/kagglehub/datasets/waqi786/global-air-quality-dataset/versions/1/global_air_quality_data_10000.csv"
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://gmrnujwviunegvyuslrs.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_PUBLISHABLE_KEY")
TABLE = "global_air_quality"
BATCH_SIZE = 250

def safe_float(v):
    try:
        return float(v) if v not in ("", "*", "N/D", "NA") else None
    except (ValueError, TypeError):
        return None

def safe_date(v):
    try:
        return datetime.strptime(v, "%Y-%m-%d").date().isoformat() if v else None
    except Exception:
        return None

def load():
    if not SUPABASE_KEY:
        log.error("❌  SUPABASE_KEY no encontrada"); sys.exit(1)
    if not CSV_PATH.exists():
        log.error(f"❌  CSV no encontrado: {CSV_PATH}")
        log.info("   Ejecuta primero: python -c \"import kagglehub; kagglehub.dataset_download('waqi786/global-air-quality-dataset')\"")
        sys.exit(1)

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Verificar si ya hay datos
    try:
        count_res = sb.table(TABLE).select("id", count="exact").limit(1).execute()
        existing = count_res.count if hasattr(count_res, 'count') and count_res.count else 0
        if existing > 0:
            log.info(f"⚠️  La tabla ya tiene {existing} registros. Limpiando para recarga...")
            sb.table(TABLE).delete().neq("id", 0).execute()
    except Exception as e:
        log.warning(f"  Verificación previa falló: {e}")

    rows_loaded = 0
    batch = []

    with open(CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            record = {
                "city":        (row.get("City") or "").strip(),
                "country":     (row.get("Country") or "").strip(),
                "date":        safe_date(row.get("Date")),
                "pm25":        safe_float(row.get("PM2.5")),
                "pm10":        safe_float(row.get("PM10")),
                "no2":         safe_float(row.get("NO2")),
                "so2":         safe_float(row.get("SO2")),
                "co":          safe_float(row.get("CO")),
                "o3":          safe_float(row.get("O3")),
                "temperature": safe_float(row.get("Temperature")),
                "humidity":    safe_float(row.get("Humidity")),
                "wind_speed":  safe_float(row.get("Wind Speed")),
            }
            if not record["city"]:
                continue
            batch.append(record)

            if len(batch) >= BATCH_SIZE:
                sb.table(TABLE).insert(batch).execute()
                rows_loaded += len(batch)
                log.info(f"  ↑ {rows_loaded} registros cargados...")
                batch = []

    if batch:
        sb.table(TABLE).insert(batch).execute()
        rows_loaded += len(batch)

    log.info(f"\n{'='*50}")
    log.info(f"✅  CARGA COMPLETADA: {rows_loaded} registros en '{TABLE}'")
    log.info(f"📊  Vista disponible: benchmark_mexico_vs_world")

if __name__ == "__main__":
    load()
