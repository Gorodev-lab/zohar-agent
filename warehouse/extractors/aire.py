"""
warehouse/extractors/aire.py
Extrae datos de calidad del aire desde CSV local.
"""
import csv, logging
from pathlib import Path

log = logging.getLogger("warehouse.extractor.aire")
CSV_PATH = Path(__file__).parent.parent.parent / "d3_aire01_49_1.csv"


class AireExtractor:
    def extract(self) -> list[dict]:
        if not CSV_PATH.exists():
            log.warning(f"CSV de aire no encontrado: {CSV_PATH}")
            return []

        def sf(v):
            try: return float(v) if v not in ("", "*", "N/D") else None
            except: return None

        rows = []
        with open(CSV_PATH, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rows.append({
                    "entidad":   (r.get("Entidad_federativa") or r.get("Entidad") or "").strip(),
                    "municipio": r.get("Municipio", "").strip(),
                    "fuente":    r.get("Tipo_de_Fuente", "").strip(),
                    "so2":  sf(r.get("SO_2")),
                    "co":   sf(r.get("CO")),
                    "nox":  sf(r.get("NOx")),
                    "cov":  sf(r.get("COV")),
                    "pm10": sf(r.get("PM_010")),
                    "pm25": sf(r.get("PM_2_5")),
                    "nh3":  sf(r.get("NH_3")),
                })
        log.info(f"Aire: {len(rows)} registros extraídos")
        return rows
