-- ╔══════════════════════════════════════════════════════╗
-- ║  ZOHAR — Schema Inicial PostgreSQL                 ║
-- ║  infra/init/01_schema.sql                          ║
-- ║  Cargado automáticamente por Docker al iniciar     ║
-- ╚══════════════════════════════════════════════════════╝

-- Proyectos SEMARNAT
CREATE TABLE IF NOT EXISTS proyectos (
    id_proyecto      TEXT PRIMARY KEY,
    anio             INTEGER,
    promovente       TEXT,
    proyecto         TEXT,
    estado           TEXT,
    municipio        TEXT,
    sector           TEXT,
    insight          TEXT,
    reasoning        TEXT,
    context_snippet  TEXT,
    coordenadas      TEXT,
    poligono         TEXT,
    grounded         BOOLEAN   DEFAULT false,
    audit_status     TEXT      DEFAULT 'pending',
    confidence_score INTEGER,
    cross_year_link  TEXT,
    fuentes_web      JSONB     DEFAULT '[]'::jsonb,
    sources          JSONB     DEFAULT '[]'::jsonb,
    riesgo_civil     TEXT,
    sancion_profepa  TEXT,
    alertas_noticias JSONB     DEFAULT '[]'::jsonb,
    created_at       TIMESTAMPTZ DEFAULT now(),
    updated_at       TIMESTAMPTZ DEFAULT now()
);

-- Emisiones de calidad del aire (INECC)
CREATE TABLE IF NOT EXISTS aire_emisiones (
    id        BIGSERIAL PRIMARY KEY,
    entidad   TEXT NOT NULL,
    municipio TEXT NOT NULL,
    fuente    TEXT NOT NULL,
    so2       FLOAT,
    co        FLOAT,
    nox       FLOAT,
    cov       FLOAT,
    pm10      FLOAT,
    pm25      FLOAT,
    nh3       FLOAT
);

-- Status del agente (singleton)
CREATE TABLE IF NOT EXISTS agente_status (
    id        INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    pdf       TEXT,
    action    TEXT,
    target    TEXT,
    last_seen TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO agente_status (id) VALUES (1) ON CONFLICT DO NOTHING;

-- Índices de performance
CREATE INDEX IF NOT EXISTS idx_proy_anio         ON proyectos(anio);
CREATE INDEX IF NOT EXISTS idx_proy_grounded     ON proyectos(grounded) WHERE grounded = true;
CREATE INDEX IF NOT EXISTS idx_proy_confidence   ON proyectos(confidence_score DESC);
CREATE INDEX IF NOT EXISTS idx_proy_riesgo       ON proyectos(riesgo_civil);
CREATE INDEX IF NOT EXISTS idx_proy_fts          ON proyectos
    USING GIN (to_tsvector('spanish',
        coalesce(promovente,'') || ' ' ||
        coalesce(proyecto,'')   || ' ' ||
        coalesce(insight,'')
    ));
CREATE INDEX IF NOT EXISTS idx_fuentes           ON proyectos USING GIN (fuentes_web);
CREATE INDEX IF NOT EXISTS idx_alertas           ON proyectos USING GIN (alertas_noticias);
CREATE INDEX IF NOT EXISTS idx_aire_mun          ON aire_emisiones(municipio);
CREATE INDEX IF NOT EXISTS idx_aire_ent          ON aire_emisiones(entidad);
