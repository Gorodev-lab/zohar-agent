#!/usr/bin/env python3
"""audit/run_audit.py — CLI del auditor"""
import argparse, logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")

from audit.auditor import DataAuditor

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Zohar Data Quality Auditor")
    parser.add_argument("--year", type=int, help="Filtrar por año")
    args = parser.parse_args()

    results = DataAuditor(year=args.year).run()

    # Print resumen a terminal
    c = results["completeness"]
    g = results["grounding"]
    print(f"\n{'='*50}")
    print(f"  COMPLETITUD : {c['score']}%   |   {c['total_rows']} registros")
    print(f"  GROUNDING   : {g['grounded_pct']}% verificados")
    print(f"  COORDENADAS : {g['coords_pct']}% con GPS")
    print(f"{'='*50}")
