-- ╔══════════════════════════════════════════════════════════════╗
-- ║  ZOHAR — Vistas Analíticas Optimizadas                     ║
-- ║  infra/init/02_views.sql                                   ║
-- ║  Principios: window functions, CTE, partial indexes        ║
-- ╚══════════════════════════════════════════════════════════════╝

-- ─────────────────────────────────────────────────────────────
-- ÍNDICES ADICIONALES (complementan 01_schema.sql)
-- Cubrientes para evitar heap fetches en queries frecuentes
-- ─────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_proy_anio_confidence
    ON proyectos(anio, confidence_score DESC NULLS LAST)
    WHERE anio IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_proy_estado_riesgo
    ON proyectos(estado, riesgo_civil)
    WHERE riesgo_civil IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_aire_mun_lower
    ON aire_emisiones(LOWER(TRIM(municipio)));

-- ─────────────────────────────────────────────────────────────
-- VISTA 1: intel_2026 — Dashboard principal
-- Window: RANK() por confidence dentro de cada sector
-- Usa idx_proy_anio_confidence (no full scan)
-- ─────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW intel_2026 AS
WITH base AS (
    SELECT
        id_proyecto, anio, promovente, proyecto,
        estado, municipio, sector, insight,
        coordenadas, grounded, audit_status,
        confidence_score, riesgo_civil, sancion_profepa,
        alertas_noticias, fuentes_web, updated_at
    FROM proyectos
    WHERE anio = 2026          -- usa idx_proy_anio_confidence
)
SELECT
    *,
    -- Ranking global por score
    RANK() OVER (ORDER BY confidence_score DESC NULLS LAST)
        AS rank_global,
    -- Ranking dentro del sector
    RANK() OVER (PARTITION BY sector ORDER BY confidence_score DESC NULLS LAST)
        AS rank_sector,
    -- Cuartil de riesgo (1=bajo … 4=alto)
    NTILE(4) OVER (ORDER BY confidence_score DESC NULLS LAST)
        AS cuartil_riesgo
FROM base;

-- ─────────────────────────────────────────────────────────────
-- VISTA 2: proyectos_con_riesgo_ambiental
-- JOIN proyectos × aire_emisiones usando índice LOWER()
-- Window: ROW_NUMBER() para deduplicar si hay varios municipios
-- ─────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW proyectos_con_riesgo_ambiental AS
WITH emisiones_agg AS (
    -- Pre-agrega emisiones por municipio (evita JOIN cartesiano)
    SELECT
        LOWER(TRIM(municipio))       AS mun_key,
        ROUND(SUM(pm25)::numeric, 2) AS total_pm25,
        ROUND(SUM(nox)::numeric,  2) AS total_nox,
        ROUND(SUM(co)::numeric,   2) AS total_co,
        ROUND(MAX(pm25)::numeric, 2) AS max_pm25
    FROM aire_emisiones
    GROUP BY LOWER(TRIM(municipio))
),
proyectos_2026 AS (
    -- Accede por índice parcial anio=2026
    SELECT *
    FROM proyectos
    WHERE anio = 2026
)
SELECT
    p.id_proyecto,
    p.anio,
    p.promovente,
    p.proyecto,
    p.estado,
    p.municipio,
    p.sector,
    p.riesgo_civil,
    p.sancion_profepa,
    p.confidence_score,
    p.coordenadas,
    e.total_pm25,
    e.total_nox,
    e.total_co,
    e.max_pm25,
    -- Percentil de PM2.5 dentro del estado
    PERCENT_RANK() OVER (
        PARTITION BY p.estado
        ORDER BY COALESCE(e.total_pm25, 0)
    ) AS pct_pm25_en_estado,
    -- Flag de alerta: pm25 en cuartil superior del estado
    CASE
        WHEN NTILE(4) OVER (
            PARTITION BY p.estado
            ORDER BY COALESCE(e.total_pm25, 0) DESC
        ) = 1 THEN true
        ELSE false
    END AS alerta_pm25
FROM proyectos_2026 p
LEFT JOIN emisiones_agg e
    ON LOWER(TRIM(p.municipio)) = e.mun_key  -- usa idx_aire_mun_lower
ORDER BY p.confidence_score DESC NULLS LAST;

-- ─────────────────────────────────────────────────────────────
-- VISTA 3: top_emisores_estado — Mapa de calor por estado
-- Window: RANK() para ordenar estados por contaminante
-- ─────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW top_emisores_estado AS
WITH por_estado AS (
    SELECT
        entidad,
        ROUND(SUM(pm25)::numeric, 1) AS total_pm25,
        ROUND(SUM(nox)::numeric,  1) AS total_nox,
        ROUND(SUM(co)::numeric,   1) AS total_co,
        ROUND(SUM(nh3)::numeric,  1) AS total_nh3,
        COUNT(DISTINCT municipio)     AS n_municipios
    FROM aire_emisiones
    GROUP BY entidad           -- usa idx_aire_ent
)
SELECT
    *,
    RANK() OVER (ORDER BY total_pm25 DESC) AS rank_pm25,
    RANK() OVER (ORDER BY total_nox  DESC) AS rank_nox,
    RANK() OVER (ORDER BY total_co   DESC) AS rank_co
FROM por_estado
ORDER BY total_pm25 DESC;

-- ─────────────────────────────────────────────────────────────
-- VISTA 4: tendencia_anual — Evolución YoY con LAG()
-- Window: LAG() para calcular delta año anterior
-- ─────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW tendencia_anual AS
WITH por_anio AS (
    SELECT
        anio,
        COUNT(*)                                      AS total_proyectos,
        COUNT(*) FILTER (WHERE grounded = true)       AS grounded_count,
        ROUND(AVG(confidence_score)::numeric, 1)      AS avg_score,
        COUNT(*) FILTER (WHERE riesgo_civil = 'ALTO') AS riesgo_alto_count,
        COUNT(*) FILTER (WHERE coordenadas IS NOT NULL) AS con_coords
    FROM proyectos
    WHERE anio IS NOT NULL
    GROUP BY anio
)
SELECT
    *,
    -- Delta vs año anterior
    total_proyectos - LAG(total_proyectos) OVER (ORDER BY anio)
        AS delta_proyectos,
    -- % cambio YoY
    ROUND(
        (total_proyectos::numeric /
         NULLIF(LAG(total_proyectos) OVER (ORDER BY anio), 0) - 1) * 100,
        1
    ) AS pct_cambio_yoy,
    -- Proyectos acumulados (running total)
    SUM(total_proyectos) OVER (ORDER BY anio ROWS UNBOUNDED PRECEDING)
        AS acumulado
FROM por_anio
ORDER BY anio;
