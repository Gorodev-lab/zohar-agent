import os
import sqlite3
import pandas as pd
import requests
import json

# Configuración
HOME = os.path.expanduser("~")
DB_PATH = os.path.join(HOME, "zohar_intelligence.db")
CSV_PATH = os.path.join(HOME, "zohar_historico_proyectos.csv")

def get_env():
    env = {}
    with open(".env", "r") as f:
        for line in f:
            if "=" in line:
                k, v = line.strip().split("=", 1)
                env[k] = v
    return env

ENV = get_env()
SB_URL = ENV.get("SUPABASE_URL")
SB_KEY = ENV.get("SUPABASE_KEY")

def sync():
    all_data = []
    
    # 1. Leer SQLite
    if os.path.exists(DB_PATH):
        print(f"Leyendo SQLite: {DB_PATH}")
        with sqlite3.connect(DB_PATH) as conn:
            df = pd.read_sql_query("SELECT * FROM projects", conn)
            # Normalizar columnas para Supabase
            df = df.rename(columns={
                'pid': 'id_proyecto',
                'year': 'anio',
                'estado': 'estado',
                'municipio': 'municipio',
                'proyecto': 'proyecto',
                'promovente': 'promovente',
                'sector': 'sector',
                'insight': 'insight',
                'sources': 'fuentes_web'
            })
            # Convertir fuentes_web de string a lista si es necesario
            if 'fuentes_web' in df.columns:
                df['fuentes_web'] = df['fuentes_web'].apply(lambda x: [x] if isinstance(x, str) and x.startswith('http') else [])
            
            all_data.append(df)

    if not all_data:
        print("No hay datos para sincronizar.")
        return

    df_final = pd.concat(all_data).drop_duplicates(subset=['id_proyecto'])
    # Solo columnas que existen en Supabase
    cols = ['id_proyecto', 'anio', 'estado', 'municipio', 'localidad', 'proyecto', 'promovente', 'sector', 'insight', 'fuentes_web']
    records = df_final[df_final.columns.intersection(cols)].fillna("").to_dict(orient="records")
    
    # Asegurar que fuentes_web sea JSONB compatible (lista)
    for r in records:
        if isinstance(r.get('fuentes_web'), str):
            r['fuentes_web'] = [r['fuentes_web']]

    print(f"Sincronizando {len(records)} registros a Supabase...")
    
    headers = {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates" # Upsert
    }

    # Subir en bloques de 50 para evitar limites de payload
    for i in range(0, len(records), 50):
        chunk = records[i:i+50]
        r = requests.post(f"{SB_URL}/rest/v1/proyectos", headers=headers, json=chunk)
        if r.status_code not in [200, 201]:
            print(f"Error en bloque {i}: {r.text}")
        else:
            print(f"Bloque {i} sincronizado ✅")

if __name__ == "__main__":
    sync()
