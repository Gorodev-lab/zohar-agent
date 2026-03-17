"""
warehouse/loaders/pg_loader.py
Carga async a PostgreSQL (Supabase) usando asyncpg pool.
"""
import os, logging
from typing import Any
from datetime import datetime, timezone

log = logging.getLogger("warehouse.pg_loader")

# Prioridad: DATABASE_URL > construir desde SUPABASE_URL
DATABASE_URL = (
    os.environ.get("DATABASE_URL") or
    os.environ.get("SUPABASE_DB_URL")   # pooler :6543
)


class PGLoader:
    TABLE = "proyectos"

    async def upsert(self, records: list[dict]) -> int:
        """Upsert en batch a proyectos vía asyncpg pool."""
        if not records:
            return 0

        try:
            import asyncpg
        except ImportError:
            log.error("asyncpg no instalado: pip install asyncpg")
            return 0

        if not DATABASE_URL:
            log.warning("DATABASE_URL no configurada — saltando carga PG")
            return 0

        pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
        count = 0

        try:
            async with pool.acquire() as conn:
                for r in records:
                    try:
                        await conn.execute("""
                            INSERT INTO proyectos (
                                id_proyecto, anio, promovente, proyecto,
                                estado, municipio, sector, insight,
                                coordenadas, grounded, audit_status,
                                confidence_score, riesgo_civil, sancion_profepa,
                                fuentes_web, alertas_noticias,
                                reasoning, context_snippet, updated_at
                            ) VALUES (
                                $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,
                                $11,$12,$13,$14,$15,$16,$17,$18,$19
                            )
                            ON CONFLICT (id_proyecto) DO UPDATE SET
                                promovente       = EXCLUDED.promovente,
                                proyecto         = EXCLUDED.proyecto,
                                insight          = EXCLUDED.insight,
                                coordenadas      = EXCLUDED.coordenadas,
                                grounded         = EXCLUDED.grounded,
                                confidence_score = EXCLUDED.confidence_score,
                                riesgo_civil     = EXCLUDED.riesgo_civil,
                                sancion_profepa  = EXCLUDED.sancion_profepa,
                                fuentes_web      = EXCLUDED.fuentes_web,
                                alertas_noticias = EXCLUDED.alertas_noticias,
                                reasoning        = EXCLUDED.reasoning,
                                context_snippet  = EXCLUDED.context_snippet,
                                updated_at       = EXCLUDED.updated_at
                        """,
                            r.get("pid"),
                            r.get("year"),
                            r.get("promovente"),
                            r.get("proyecto"),
                            r.get("estado"),
                            r.get("municipio"),
                            r.get("sector"),
                            r.get("insight"),
                            r.get("coordenadas"),
                            bool(r.get("grounded", False)),
                            r.get("audit_status", "pending"),
                            r.get("confidence_score"),
                            r.get("riesgo_civil"),
                            r.get("sancion_profepa"),
                            r.get("fuentes_web", []),
                            r.get("alertas_noticias", []),
                            r.get("reasoning"),
                            r.get("context_snippet"),
                            datetime.now(timezone.utc),
                        )
                        count += 1
                    except Exception as e:
                        log.error(f"  ❌ Error en {r.get('pid')}: {e}")
        finally:
            await pool.close()

        return count

    async def upsert_aire(self, records: list[dict]) -> int:
        """Upsert emissions data directly to air_emissions table."""
        if not records:
            return 0

        try:
            import asyncpg
        except ImportError:
            log.error("asyncpg no instalado")
            return 0

        if not DATABASE_URL:
            log.warning("DATABASE_URL no configurada — saltando carga PG aire_emisiones")
            return 0

        pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
        count = 0

        try:
            async with pool.acquire() as conn:
                log.info("🧹 Limpiando tabla aire_emisiones...")
                await conn.execute("DELETE FROM aire_emisiones")

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

                query = """
                    INSERT INTO aire_emisiones (
                        entidad, municipio, fuente, so2, co, nox, cov, pm10, pm25, nh3, lat, lon
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                """
                await conn.executemany(query, rows)
                count = len(rows)
        except Exception as e:
            log.error(f"❌ Error en upsert_aire: {e}")
        finally:
            await pool.close()

        return count
