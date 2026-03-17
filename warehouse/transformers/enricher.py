"""
warehouse/transformers/enricher.py
Enriquece proyectos con emisiones de calidad del aire del municipio.
"""
import logging
from collections import defaultdict

log = logging.getLogger("warehouse.enricher")


class Enricher:
    def __init__(self, emisiones: list[dict]):
        # Índice por municipio normalizado (lowercase sin espacios extra)
        self.emis_idx: dict[str, dict] = defaultdict(lambda: {
            "pm25": 0.0, "pm10": 0.0, "nox": 0.0, "co": 0.0,
            "so2": 0.0, "cov": 0.0, "nh3": 0.0
        })
        for e in emisiones:
            key = e.get("municipio", "").lower().strip()
            if not key:
                continue
            for col in ["pm25", "pm10", "nox", "co", "so2", "cov", "nh3"]:
                val = e.get(col) or 0.0
                self.emis_idx[key][col] += float(val)

    def enrich(self, projects: list[dict]) -> list[dict]:
        enriched = 0
        for p in projects:
            key = p.get("municipio", "").lower().strip()
            if key in self.emis_idx:
                emis = self.emis_idx[key]
                p["aire_pm25"] = round(emis["pm25"], 3)
                p["aire_pm10"] = round(emis["pm10"], 3)
                p["aire_nox"]  = round(emis["nox"],  3)
                p["aire_co"]   = round(emis["co"],   3)
                enriched += 1
        log.info(f"Enricher: {enriched}/{len(projects)} proyectos enriquecidos con datos de aire")
        return projects
