try:
    import re
    import pandas as pd
    import sqlite3
    from pathlib import Path
    import logging
except ImportError as e:
    print(f"❌ Error: Missing dependency '{e.name}'. Run: pip install pandas")
    exit(1)

# Configuación
WORK_DIR = Path("/home/gorops/proyectos antigravity/zohar-agent")
DB_PATH = Path("/home/gorops/zohar_intelligence.db") # Ruta standard en el agente

def sanitize_text(text: str) -> str:
    """
    Sanitiza texto siguiendo el Codex Pattern 4.1.1.6.
    Elimina URLs y caracteres especiales, dejando solo alfanuméricos y espacios.
    """
    if not text: return ""
    
    # 1. Remover URLs
    text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
    
    # 2. Remover caracteres especiales (dejar solo letras, números y espacios básicos)
    # Conservar tildes para español si es necesario, o limpiar a ASCII puro.
    # Aquí vamos por limpieza agresiva:
    text = re.sub(r'[^a-zA-Z0-9áéíóúÁÉÍÓÚñÑ\s]', ' ', text)
    
    # 3. Colapsar espacios
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def run_data_audit_cleaning():
    """
    Auditoría y Limpieza (Strategy 2).
    Aplica transformación a los insights y nombres de proyectos.
    """
    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger("zohar-audit")

    if not DB_PATH.exists():
        log.error(f"Database not found at {DB_PATH}")
        return

    try:
        conn = sqlite3.connect(str(DB_PATH))
        df = pd.read_sql_query("SELECT pid, proyecto, insight FROM projects", conn)
        
        log.info(f"🧐 Auditando {len(df)} registros para limpieza (Codex Pattern 4.1.1.6)...")
        
        df['proyecto_clean'] = df['proyecto'].apply(sanitize_text)
        df['insight_clean'] = df['insight'].apply(sanitize_text)
        
        # Detectar cambios significativos (posibles alucinaciones o ruido)
        df['noise_detected'] = df.apply(lambda r: len(str(r['insight'])) - len(str(r['insight_clean'])) > 50, axis=1)
        
        noise_count = df['noise_detected'].sum()
        if noise_count > 0:
            log.warning(f"⚠️ Se detectó ruido excesivo en {noise_count} registros. Procediendo a saneamiento.")
            
        # Update en DB (opcional, aquí mostramos el resultado)
        for _, row in df[df['noise_detected']].iterrows():
            log.debug(f"  [Clean] PID {row['pid']}: {row['insight_clean'][:80]}...")
            
        log.info("✅ Auditoría de limpieza completada.")
        print(df[['pid', 'noise_detected']].head(10))
        
        conn.close()
    except Exception as e:
        log.error(f"❌ Error en auditoría: {e}")

if __name__ == "__main__":
    run_data_audit_cleaning()
