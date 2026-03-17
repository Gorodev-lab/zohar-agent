#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════╗
║  ZOHAR — AUTOMATED DATA WAREHOUSE PIPELINE          ║
║  warehouse/pipeline.py                              ║
║  Uso: python -m warehouse.pipeline [--year 2026]    ║
╚══════════════════════════════════════════════════════╝
"""
import os, sys, asyncio, logging, argparse
from pathlib import Path
from datetime import datetime

# ── Cargar .env ────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    for env_file in [".env.local", ".env"]:
        load_dotenv(Path(__file__).parent.parent / env_file)
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("warehouse.pipeline")


class ZoharWarehousePipeline:
    """
    Orquestador principal ETL.
    Extract → Transform → Load (PostgreSQL + DuckDB)
    """

    def __init__(self, year: int | None = None, full: bool = False):
        self.year  = year
        self.full  = full
        self.stats = {
            "started_at": datetime.now().isoformat(),
            "extracted": 0,
            "transformed": 0,
            "loaded_pg": 0,
            "loaded_duckdb": 0,
            "errors": []
        }

    async def run(self):
        log.info("🏭 Iniciando Zohar Warehouse Pipeline")
        log.info(f"   Año: {self.year or 'todos'}  |  Modo: {'FULL' if self.full else 'incremental'}")

        # ── 1. EXTRACT ──────────────────────────────────────────────────────
        from warehouse.extractors.semarnat import SemarnatExtractor
        from warehouse.extractors.aire     import AireExtractor

        log.info("📥 [EXTRACT] Cargando datos...")
        proyectos = await SemarnatExtractor(year=self.year, full=self.full).extract()
        self.stats["extracted"] = len(proyectos)
        log.info(f"   → {len(proyectos)} proyectos extraídos")

        emisiones = AireExtractor().extract()
        log.info(f"   → {len(emisiones)} registros de emisiones")

        # ── 2. TRANSFORM ────────────────────────────────────────────────────
        from warehouse.transformers.normalizer import Normalizer
        from warehouse.transformers.enricher   import Enricher
        from warehouse.transformers.geo        import GeoTransformer

        log.info("🔄 [TRANSFORM] Normalizando y enriqueciendo...")
        normalized = Normalizer().normalize(proyectos)
        enriched   = Enricher(emisiones).enrich(normalized)
        self.stats["transformed"] = len(enriched)
        log.info(f"   → {len(enriched)} registros transformados")

        log.info("🌍 [TRANSFORM] Geocodificando emisiones cruzando con catálogo...")
        emisiones = GeoTransformer().transform(emisiones)

        # ── 3. LOAD ─────────────────────────────────────────────────────────
        from warehouse.loaders.pg_loader     import PGLoader
        from warehouse.loaders.duckdb_loader import DuckDBLoader

        log.info("📤 [LOAD] Cargando en PostgreSQL...")
        pg_loader = PGLoader()
        pg_count = await pg_loader.upsert(enriched)
        pg_aire = await pg_loader.upsert_aire(emisiones)
        self.stats["loaded_pg"] = pg_count
        self.stats["loaded_pg_aire"] = pg_aire
        log.info(f"   → {pg_count} proyectos en Supabase")
        log.info(f"   → {pg_aire} emisiones de aire en Supabase")

        log.info("📤 [LOAD] Materializando en DuckDB...")
        duck_loader = DuckDBLoader()
        duck_count = duck_loader.materialize(enriched)
        duck_aire = duck_loader.materialize_aire(emisiones)
        self.stats["loaded_duckdb"] = duck_count
        self.stats["loaded_duckdb_aire"] = duck_aire
        log.info(f"   → {duck_count} proyectos en DuckDB local")
        log.info(f"   → {duck_aire} emisiones de aire en DuckDB local")

        # ── RESUMEN ─────────────────────────────────────────────────────────
        self.stats["finished_at"] = datetime.now().isoformat()
        log.info("\n" + "="*50)
        log.info("✅ PIPELINE COMPLETADO")
        for k, v in self.stats.items():
            log.info(f"   {k}: {v}")
        log.info("="*50)

        return self.stats


def main():
    parser = argparse.ArgumentParser(description="Zohar Warehouse Pipeline")
    parser.add_argument("--year",  type=int, help="Filtrar por año (ej: 2026)")
    parser.add_argument("--full",  action="store_true", help="Re-procesar todos los registros")
    args = parser.parse_args()

    pipeline = ZoharWarehousePipeline(year=args.year, full=args.full)
    asyncio.run(pipeline.run())


if __name__ == "__main__":
    main()
