import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client

def test_connection():
    load_dotenv()
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    
    if not url or not key:
        print("❌ Error: SUPABASE_URL o SUPABASE_KEY no definidos en el entorno / .env")
        return False
        
    try:
        print(f"🔗 Conectando a {url}...")
        supabase: Client = create_client(url, key)
        
        # Probar lectura básica
        print("🔍 Probando acceso a tablas...")
        # Intentamos listar tablas o algo simple. Nota: depende de RLS
        res = supabase.table("proyectos").select("*", count="exact").limit(1).execute()
        
        print(f"✅ Conexión exitosa. Proyectos encontrados: {res.count if hasattr(res, 'count') else 'N/A'}")
        return True
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return False

if __name__ == "__main__":
    if test_connection():
        print("\n🚀 El ecosistema Zohar está listo para la nube.")
    else:
        print("\n⚠️  Asegúrate de haber creado la tabla 'proyectos' en Supabase.")
        sys.exit(1)
