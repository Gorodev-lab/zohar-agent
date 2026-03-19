import json
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def fix_coords():
    with open('dashboard_legacy/muni_coords.json', 'r', encoding='utf-8') as f:
        muni_coords = json.load(f)
    
    print(f"Loaded {len(muni_coords)} municipality coordinates.")

    # Fetch groups instead of everything to avoid big memory usage
    response = supabase.table('aire_emisiones').select('entidad, municipio').execute()
    records = response.data
    
    unique_munis = set()
    for r in records:
        unique_munis.add((r['entidad'], r['municipio']))
    
    print(f"Found {len(unique_munis)} unique municipalities.")

    count = 0
    for entidad, municipio in unique_munis:
        key_comb = f"{entidad}||{municipio}"
        if key_comb in muni_coords:
            lat, lon = muni_coords[key_comb]
            try:
                # Use query building with filters
                supabase.table('aire_emisiones')\
                    .update({'lat': float(lat), 'lon': float(lon)})\
                    .eq('entidad', entidad)\
                    .eq('municipio', municipio)\
                    .is_('lat', 'null')\
                    .execute()
                count += 1
                if count % 10 == 0:
                    print(f"Updated {count} municipalities...")
            except Exception as e:
                print(f"Error updating {key_comb}: {e}")
        else:
            # Fallback for keys
            found = False
            for k, (lt, ln) in muni_coords.items():
                if municipio in k and entidad in k:
                    try:
                        supabase.table('aire_emisiones')\
                            .update({'lat': float(lt), 'lon': float(ln)})\
                            .eq('entidad', entidad)\
                            .eq('municipio', municipio)\
                            .is_('lat', 'null')\
                            .execute()
                        found = True
                        break
                    except:
                        pass
            if not found:
                print(f"No coords for: {key_comb}")

    print("Finished coordinate sync.")

if __name__ == "__main__":
    fix_coords()
