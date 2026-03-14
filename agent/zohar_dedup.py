
import sqlite3
import logging
from pathlib import Path

DB_PATH = Path.home() / "zohar_intelligence.db"

def rebuild_links():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    log = logging.getLogger("zohar-dedup")
    
    if not DB_PATH.exists():
        log.error("Base de datos no encontrada.")
        return

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            projects = conn.execute("SELECT * FROM projects").fetchall()
            
            log.info(f"Escaneando {len(projects)} registros para vinculación semántica...")
            links_found = 0
            
            for p in projects:
                pid = p["pid"]
                name = p["proyecto"]
                prom = p["promovente"]
                
                if not name or not prom: continue
                
                # Buscar duplicados previos
                # Mismo criterio que en el agente: prefijos para tolerar variaciones
                query = """
                    SELECT pid, year FROM projects 
                    WHERE proyecto LIKE ? AND promovente LIKE ? AND pid != ?
                    ORDER BY year ASC LIMIT 1
                """
                res = conn.execute(query, (f"{name[:20]}%", f"{prom[:15]}%", pid)).fetchone()
                
                if res:
                    old_pid = res["pid"]
                    old_year = res["year"]
                    
                    # Si ya tiene un link, no lo sobreescribimos si es el mismo
                    if p["cross_year_link"] == old_pid: continue
                    
                    log.info(f"  🔗 Link detectado: {pid} -> {old_pid} ({old_year})")
                    conn.execute("UPDATE projects SET cross_year_link = ? WHERE pid = ?", (old_pid, pid))
                    links_found += 1
            
            conn.commit()
            log.info(f"✅ Re-vinculación completada. {links_found} nuevos enlaces creados.")
            
    except Exception as e:
        log.error(f"Fallo en rebuild: {e}")

if __name__ == "__main__":
    rebuild_links()
