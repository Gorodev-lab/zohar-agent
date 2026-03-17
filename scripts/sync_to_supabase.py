#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║  ZOHAR → SUPABASE SYNC                                          ║
║  Sincroniza zohar_intelligence.db (SQLite) → monitor_gaceta_eco ║
║  Uso: python3 scripts/sync_to_supabase.py [--full] [--year 2026]║
╚══════════════════════════════════════════════════════════════════╝
"""

import os, sys, json, sqlite3, logging
from pathlib import Path
from datetime import datetime, timezone

try:
    from dotenv import load_dotenv
    load_dotenv()
    load_dotenv(Path(__file__).parent.parent / ".env.local")
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

try:
    from supabase import create_client
except ImportError:
    print("❌  Instala supabase: pip install supabase")
    sys.exit(1)

# ─── Config ───────────────────────────────────────────────────────────────────
DB_PATH      = Path.home() / "zohar_intelligence.db"
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://gmrnujwviunegvyuslrs.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_PUBLISHABLE_KEY")
TABLE        = "proyectos"
BATCH_SIZE   = 50

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("zohar-sync")

# ─── Helpers ──────────────────────────────────────────────────────────────────
def parse_sources(raw: str | None) -> list:
    """Convierte el campo sources (string JSON) a lista para jsonb de Supabase."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []

def parse_json_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []

def row_to_supabase(row: dict) -> dict:
    """Mapea una fila de SQLite al schema de Supabase."""
    return {
        "id_proyecto":       row.get("pid"),
        "anio":              row.get("year"),
        "promovente":        row.get("promovente"),
        "proyecto":          row.get("proyecto"),
        "estado":            row.get("estado"),
        "municipio":         row.get("municipio"),
        "sector":            row.get("sector"),
        "insight":           row.get("insight"),
        "coordenadas":       row.get("coordenadas"),
        "grounded":          bool(row.get("grounded", 0)),
        "audit_status":      row.get("audit_status", "pending"),
        "confidence_score":  row.get("confidence_score"),
        "sources":           parse_sources(row.get("sources")),
        "fuentes_web":       parse_sources(row.get("sources")),   # alias
        "riesgo_civil":      row.get("riesgo_civil"),
        "sancion_profepa":   row.get("sancion_profepa"),
        "alertas_noticias":  parse_json_list(row.get("alertas_noticias")),
        "updated_at":        datetime.now(timezone.utc).isoformat(),
    }

# ─── Main Sync ────────────────────────────────────────────────────────────────
def sync(full: bool = False, year_filter: int | None = None):
    if not SUPABASE_KEY:
        log.error("❌  SUPABASE_KEY no encontrada en el entorno.")
        sys.exit(1)

    if not DB_PATH.exists():
        log.error(f"❌  DB no encontrada: {DB_PATH}")
        sys.exit(1)

    log.info(f"🔌 Conectando a Supabase: {SUPABASE_URL}")
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Obtener PIDs ya sincronizados (para modo incremental)
    existing_pids = set()
    if not full:
        try:
            res = sb.table(TABLE).select("id_proyecto").execute()
            existing_pids = {r["id_proyecto"] for r in res.data}
            log.info(f"📊 Registros ya en Supabase: {len(existing_pids)}")
        except Exception as e:
            log.warning(f"⚠️  No se pudo obtener PIDs existentes: {e}")

    # Leer desde SQLite
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    query = "SELECT * FROM projects"
    params = []

    conditions = []
    if year_filter:
        conditions.append("year = ?")
        params.append(year_filter)
    if not full and existing_pids:
        placeholders = ",".join("?" * len(existing_pids))
        conditions.append(f"pid NOT IN ({placeholders})")
        params.extend(existing_pids)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY created_at DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()

    total = len(rows)
    log.info(f"📦 Filas a sincronizar: {total}")

    if total == 0:
        log.info("✅  Todo ya está sincronizado.")
        return

    # Sincronizar en batches (upsert por id_proyecto)
    success = 0
    errors  = 0
    for i in range(0, total, BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        records = [row_to_supabase(dict(r)) for r in batch]

        # Filtrar None en campos obligatorios
        records = [r for r in records if r.get("id_proyecto")]

        try:
            sb.table(TABLE).upsert(
                records,
                on_conflict="id_proyecto"
            ).execute()
            success += len(records)
            log.info(f"  ↑ Batch {i//BATCH_SIZE + 1}: {len(records)} registros → OK  ({success}/{total})")
        except Exception as e:
            errors += len(records)
            log.error(f"  ❌ Batch {i//BATCH_SIZE + 1} falló: {e}")

    log.info(f"\n{'='*50}")
    log.info(f"✅  SYNC COMPLETADO: {success} OK  |  {errors} errores")
    log.info(f"🌐  Ver en: https://supabase.com/dashboard/project/gmrnujwviunegvyuslrs/editor")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Zohar → Supabase Sync")
    parser.add_argument("--full",  action="store_true", help="Sincronizar TODOS (incluye existentes, usa upsert)")
    parser.add_argument("--year",  type=int,            help="Filtrar por año (ej: 2026)")
    args = parser.parse_args()

    sync(full=args.full, year_filter=args.year)
