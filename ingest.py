import csv
import requests
import json
import os

SUPABASE_URL = "https://gmrnujwviunegvyuslrs.supabase.co"
# Using service_role key to bypass RLS for ingestion
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imdtcm51and2aXVuZWd2eXVzbHJzIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MzQxNjA2NCwiZXhwIjoyMDg4OTkyMDY0fQ.STxrEt7eqZr52D_flo0BMvEkNl60UmxQSWs65nIIefg"

def parse_num(val):
    if not val or val.strip() == '': return None
    clean = val.replace(',', '').replace('$', '').replace('%', '').strip()
    try:
        return float(clean) if '.' in clean else int(clean)
    except:
        return None

def ingest_csv(filename, table_name, mapping=None, numeric_cols=[]):
    print(f"Ingesting {filename} into {table_name}...")
    with open(filename, 'r', encoding='latin-1') as f:
        reader = csv.DictReader(f)
        rows = []
        for i, row in enumerate(reader):
            item = {}
            for k, v in row.items():
                new_k = mapping.get(k, k.strip().lower().replace(' ', '_')) if mapping else k.strip().lower().replace(' ', '_')
                if new_k in numeric_cols:
                    item[new_k] = parse_num(v)
                else:
                    item[new_k] = v if v.strip() != '' else None
            rows.append(item)
    
    # Send in batches of 100
    for i in range(0, len(rows), 100):
        batch = rows[i:i+100]
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates"
        }
        res = requests.post(f"{SUPABASE_URL}/rest/v1/{table_name}", headers=headers, json=batch)
        if res.status_code not in [200, 201]:
            print(f"Error in batch {i}: {res.text}")
        else:
            print(f"Batch {i} uploaded.")

# Ingest Environmental Zoning
ingest_csv(
    'ordenamientos_ecologicos_expedidos.csv',
    'environmental_zoning',
    numeric_cols=['consecutivo', 'superficie_ha', 'fn_superficie_ha']
)

# Ingest Income 2024
income_headers_raw = [
    "Consecutivo", "Bitácora", "Clave Proyecto", "Promovente", "Nombre Proyecto",
    "Modalidad", "Estatus", "Fecha ingreso", "Fecha Resolución", "Resolución",
    "Quién Resolvió", "Oficio Resolución", "Entidad Federativa donde Ingresó",
    "Entidad Federativa Resolución", "Estado", "Municipio", "Días Laborables Transcurridos",
    "Plazo Máximo Días", "Situación Plazo", "Sector"
]
income_mapping = {
    "Consecutivo": "consecutivo", "Bitácora": "bitacora", "Clave Proyecto": "clave_proyecto",
    "Promovente": "promovente", "Nombre Proyecto": "nombre_proyecto", "Modalidad": "modalidad",
    "Estatus": "estatus", "Fecha ingreso": "fecha_ingreso", "Fecha Resolución": "fecha_resolucion",
    "Resolución": "resolucion", "Quién Resolvió": "quien_resolvio", "Oficio Resolución": "oficio_resolucion",
    "Entidad Federativa donde Ingresó": "entidad_federativa_donde_ingreso",
    "Entidad Federativa Resolución": "entidad_federativa_resolucion", "Estado": "estado",
    "Municipio": "municipio", "Días Laborables Transcurridos": "dias_laborables_transcurridos",
    "Plazo Máximo Días": "plazo_maximo_dias", "Situación Plazo": "situacion_plazo", "Sector": "sector"
}

ingest_csv(
    'ingresos_2024.csv',
    'ingresos_2024',
    mapping=income_mapping,
    numeric_cols=['consecutivo', 'dias_laborables_transcurridos', 'plazo_maximo_dias']
)
