"""
warehouse/extractors/semarnat.py
Extrae proyectos desde SQLite local (fuente primaria del agente).
"""
import sqlite3, logging
from pathlib import Path

log = logging.getLogger("warehouse.extractor.semarnat")
DB_PATH = Path.home() / "zohar_intelligence.db"


class SemarnatExtractor:
    def __init__(self, year: int | None = None, full: bool = False):
        self.year = year
        self.full = full

    async def extract(self) -> list[dict]:
        if not DB_PATH.exists():
            log.error(f"DB no encontrada: {DB_PATH}")
            return []

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        query = "SELECT * FROM projects"
        params = []

        if self.year:
            query += " WHERE year = ?"
            params.append(self.year)

        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]
