"""
warehouse/loaders/duckdb_loader.py
Materializa datos en DuckDB local para análisis de alto rendimiento.
"""
import logging
from pathlib import Path

log = logging.getLogger("warehouse.duckdb_loader")
DUCK_PATH = Path.home() / "zohar_warehouse.duckdb"


class DuckDBLoader:
    def materialize(self, records: list[dict]) -> int:
        if not records:
            return 0
        try:
            import duckdb
            import json
        except ImportError:
            log.error("duckdb no instalado")
            return 0

        con = duckdb.connect(str(DUCK_PATH))
        con.execute("""
            CREATE TABLE IF NOT EXISTS proyectos (
                pid TEXT PRIMARY KEY,
                year INTEGER,
                promovente TEXT, proyecto TEXT,
                estado TEXT, municipio TEXT, sector TEXT,
                insight TEXT, coordenadas TEXT,
                grounded BOOLEAN, audit_status TEXT,
                confidence_score INTEGER,
                riesgo_civil TEXT, sancion_profepa TEXT,
                fuentes_web TEXT, alertas_noticias TEXT,
                created_at TEXT
            )
        """)

        rows = []
        for r in records:
            rows.append((
                r.get("pid"), r.get("year"), r.get("promovente"),
                r.get("proyecto"), r.get("estado"), r.get("municipio"),
                r.get("sector"), r.get("insight"), r.get("coordenadas"),
                bool(r.get("grounded")), r.get("audit_status", "pending"),
                r.get("confidence_score"), r.get("riesgo_civil"),
                r.get("sancion_profepa"),
                json.dumps(r.get("fuentes_web", [])),
                json.dumps(r.get("alertas_noticias", [])),
                r.get("created_at", ""),
            ))

        con.executemany("""
            INSERT OR REPLACE INTO proyectos VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, rows)
        count = con.execute("SELECT COUNT(*) FROM proyectos").fetchone()[0]
        con.close()
        log.info(f"DuckDB: {count} registros totales en warehouse")
        return len(rows)

    def materialize_aire(self, records: list[dict]) -> int:
        if not records:
            return 0
        try:
            import duckdb
        except ImportError:
            log.error("duckdb no instalado")
            return 0

        con = duckdb.connect(str(DUCK_PATH))
        con.execute("""
            CREATE TABLE IF NOT EXISTS aire_emisiones (
                entidad TEXT, municipio TEXT, fuente TEXT,
                so2 DOUBLE, co DOUBLE, nox DOUBLE, cov DOUBLE,
                pm10 DOUBLE, pm25 DOUBLE, nh3 DOUBLE,
                lat DOUBLE, lon DOUBLE
            )
        """)
        con.execute("DELETE FROM aire_emisiones")

        rows = []
        for r in records:
            rows.append((
                r.get("entidad"), r.get("municipio"), r.get("fuente"),
                float(r.get("so2")) if r.get("so2") is not None else None,
                float(r.get("co")) if r.get("co") is not None else None,
                float(r.get("nox")) if r.get("nox") is not None else None,
                float(r.get("cov")) if r.get("cov") is not None else None,
                float(r.get("pm10")) if r.get("pm10") is not None else None,
                float(r.get("pm25")) if r.get("pm25") is not None else None,
                float(r.get("nh3")) if r.get("nh3") is not None else None,
                float(r.get("lat")) if r.get("lat") is not None else None,
                float(r.get("lon")) if r.get("lon") is not None else None
            ))

        con.executemany("""
            INSERT INTO aire_emisiones VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, rows)
        count = con.execute("SELECT COUNT(*) FROM aire_emisiones").fetchone()[0]
        con.close()
        log.info(f"DuckDB: {count} registros de aire en warehouse")
        return len(rows)
