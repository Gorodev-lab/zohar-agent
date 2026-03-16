try:
    import duckdb
    import os
    from pathlib import Path
    import logging
except ImportError as e:
    print(f"❌ Error: Missing dependency '{e.name}'. Run: pip install duckdb")
    exit(1)

# Configuración
WORK_DIR = Path("/home/gorops/proyectos antigravity/zohar-agent")
WAREHOUSE_PATH = WORK_DIR / "zohar_warehouse.duckdb"

def run_analytical_transformation():
    """
    Ejecuta una transformación analítica de alto nivel (Strategy 1 + Codex patterns).
    Calcula el crecimiento Año-tras-Año (YoY) por Estado.
    """
    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger("zohar-warehouse")

    if not WAREHOUSE_PATH.exists():
        log.info(f"Warehouse not found at {WAREHOUSE_PATH}. Creating empty DB for structure...")
        # (Opcional) si no existe, podríamos intentar crearlo desde SQLite, 
        # pero asumimos que sync_to_warehouse ya corrió.
        return

    try:
        con = duckdb.connect(str(WAREHOUSE_PATH))
        
        log.info("🚀 Iniciando Transformación Analítica (Codex Pattern 4.1.1.4)...")
        
        # Query Analítica Avanzada (YoY Growth Rate)
        # Adaptada del prompt 4 de 'Data Transformation' del Codex
        yoy_query = """
        WITH YearlyStats AS (
            -- Agregamos por año y estado
            SELECT 
                year, 
                estado, 
                COUNT(*) as project_count
            FROM warehouse_projects
            WHERE estado IS NOT NULL AND estado != ''
            GROUP BY year, estado
        ),
        LaggedStats AS (
            -- Usamos Window Functions (LAG) para obtener el valor del año anterior
            SELECT 
                year,
                estado,
                project_count,
                LAG(project_count) OVER (PARTITION BY estado ORDER BY year) as prev_year_count
            FROM YearlyStats
        )
        -- Calculamos el YoY Growth Rate (%)
        SELECT 
            year,
            estado,
            project_count,
            prev_year_count,
            CASE 
                WHEN prev_year_count IS NULL OR prev_year_count = 0 THEN NULL
                ELSE round(((project_count - prev_year_count) / CAST(prev_year_count AS FLOAT)) * 100, 2)
            END as yoy_growth_pct
        FROM LaggedStats
        ORDER BY estado, year DESC;
        """
        
        # Crear Carpeta de Insights
        insights_dir = WORK_DIR / "analytics"
        insights_dir.mkdir(parents=True, exist_ok=True)
        
        # Ejecutar y mostrar resumen
        log.info("📊 Resumen de Crecimiento (Top 10):")
        res = con.execute(yoy_query).fetchdf()
        
        if res.empty:
            log.warning("No data found in warehouse_projects to analyze.")
        else:
            print(res.head(10))
            report_path = insights_dir / "yoy_state_growth.csv"
            res.to_csv(report_path, index=False)
            log.info(f"✅ Reporte generado en: {report_path}")
        
        con.close()
    except Exception as e:
        log.error(f"❌ Error en transformación: {e}")

if __name__ == "__main__":
    run_analytical_transformation()
