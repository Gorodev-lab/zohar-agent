#!/usr/bin/env python3
"""
reprocess_failed.py
════════════════════════════════════════════════════════════
Lee de Supabase los proyectos sin promovente y los regresa
a la queue local del agente con status=pending para que
el pipeline con validación en cascada los reintente.

Uso:
  cd ~/proyectos\ antigravity/zohar-agent
  source zohar_venv/bin/activate
  python scripts/reprocess_failed.py [--dry-run]
"""
import sys, os, json, argparse
from pathlib import Path
from dotenv import load_dotenv

# ── Setup paths ───────────────────────────────────────────
ROOT  = Path(__file__).resolve().parent.parent
AGENT = ROOT / "agent"
sys.path.insert(0, str(AGENT))
load_dotenv(ROOT / ".env")

import zohar_agent_v2 as Z

# ── Supabase ──────────────────────────────────────────────
from supabase import create_client
SUPA_URL = os.getenv("SUPABASE_URL", "")
SUPA_KEY = os.getenv("SUPABASE_KEY", "")

def fetch_failed_ids() -> list[dict]:
    """Trae de Supabase los proyectos sin promovente."""
    sb = create_client(SUPA_URL, SUPA_KEY)
    resp = (
        sb.table("proyectos")
          .select("id_proyecto, anio, estado")
          .is_("promovente", "null")
          .order("anio", desc=True)
          .execute()
    )
    return resp.data or []


def find_txt_for_pid(pid: str, year: int) -> str | None:
    """Busca el archivo .txt del proyecto en el directorio de trabajo."""
    base_dirs = [
        Path("/home/gorops/gaceta_work") / str(year),
        Path("/home/gorops/gaceta_work") / str(year-1), 
        Path("/home/gorops/gaceta_work") / str(year+1),
    ]
    for d in base_dirs:
        if not d.exists():
            continue
        # Buscar txt que contenga el PID
        for txt_file in d.glob("*.txt"):
            try:
                if pid in txt_file.read_text(errors="replace"):
                    return str(txt_file)
            except Exception:
                continue
    return None


def _find_key_for_pid(queue: Z.PersistentQueue, pid: str) -> str | None:
    """La regex vieja a veces dividía el PID en la key de la queue. Buscamos por match."""
    if pid in queue._d:
        return pid
    # Buscar si algún value .pid coincide exactamente (mejor que la key)
    for k, v in queue._d.items():
        if getattr(v, "pid", "") == pid or getattr(v, "pid", "") == pid.replace(" ", ""):
            return k
    # Buscar como substring de la key
    for k in queue._d:
        if pid in k or k in pid:
            return k
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="No modifica la queue, solo imprime lo que haría")
    args = parser.parse_args()

    # Cargar queue local
    queue_path = ROOT / "zohar_queue.json"
    if not queue_path.exists():
        # Intentar rutas alternativas
        for alt in [ROOT / "data" / "queue.json", ROOT / "queue.json"]:
            if alt.exists():
                queue_path = alt
                break

    queue = Z.PersistentQueue(queue_path)
    stats_before = queue.stats()

    print(f"\n{'='*60}")
    print(f"  ZOHAR REPROCESS — Queue: {queue_path}")
    print(f"  Estado inicial: {stats_before}")
    print(f"  Modo: {'DRY-RUN' if args.dry_run else 'REAL'}")
    print(f"{'='*60}\n")

    # Obtener IDs fallidos de Supabase
    print("Consultando Supabase...")
    failed = fetch_failed_ids()
    print(f"  {len(failed)} proyectos sin promovente en Supabase\n")

    reset_count = 0
    added_count = 0
    not_found   = 0

    for row in failed:
        pid  = row["id_proyecto"]
        year = row["anio"]

        if pid in queue._d:
            # Ya está en queue — resetear a pending
            item = queue._d[pid]
            if not args.dry_run:
                item.status     = "pending"
                item.attempts   = 0
                item.last_error = "requeued_by_reprocess"
                queue._save()
            reset_count += 1
            print(f"  [RESET]  {pid} ({year}) — era: {item.status}")
        else:
            # Buscar el txt para agregarlo como nuevo
            txt = find_txt_for_pid(pid, year)
            if txt:
                if not args.dry_run:
                    # Para pdf usamos placeholder — el agente lo encontrará
                    queue.add(pid, f"{pid}.pdf", year, txt)
                added_count += 1
                print(f"  [ADD]    {pid} ({year}) — txt: {Path(txt).name}")
            else:
                not_found += 1
                print(f"  [SKIP]   {pid} ({year}) — sin archivo TXT local")

    print(f"\n{'='*60}")
    print(f"  RESUMEN:")
    print(f"    Reseteados a pending : {reset_count}")
    print(f"    Agregados nuevos     : {added_count}")
    print(f"    Sin archivo local    : {not_found}")
    if not args.dry_run:
        print(f"    Stats finales        : {queue.stats()}")
    print(f"{'='*60}\n")

    if not args.dry_run and (reset_count + added_count) > 0:
        print("  Queue actualizada. Inicia el agente para reprocesar:")
        print("  python agent/zohar_agent_v2.py\n")


if __name__ == "__main__":
    main()
