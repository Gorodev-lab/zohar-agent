#!/usr/bin/env python3
"""
Zohar Agent - Geocode Municipalities
Geocodifica la lista de municipios en México utilizando la API de Google Maps.
"""

import csv
import json
import urllib.request
import urllib.parse
from pathlib import Path
import time
import os

API_KEY = "AIzaSyCTgF49SGXXwtEmt9QEkwPRC6GEG-71SQw"

def main():
    print("Iniciando geocodificación de municipios...")
    
    # Asegúrate de que este en el directorio principal o ajusta la ruta
    csv_path = Path(__file__).resolve().parent.parent / 'd3_aire01_49_1.csv'
    if not csv_path.exists():
        # Fallback 
        csv_path = Path('d3_aire01_49_1.csv')
        if not csv_path.exists():
            print("No se encontró el archivo CSV de datos de aire.")
            return

    munis = set()
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            estado = row.get('Entidad_federativa', '').strip()
            if not estado:
                estado = row.get('Entidad', '').strip()
            muni = row.get('Municipio', '').strip()
            if estado and muni:
                munis.add((estado, muni))
    
    print(f"Total de municipios únicos encontrados en CSV: {len(munis)}")
    
    coords_dict = {}
    
    out_dir = Path(__file__).resolve().parent.parent / 'dashboard'
    out_file = out_dir / 'muni_coords.json'
    
    if not out_dir.exists():
         out_dir = Path('dashboard')
         out_file = out_dir / 'muni_coords.json'
         out_dir.mkdir(exist_ok=True)

    if out_file.exists():
        with open(out_file, 'r', encoding='utf-8') as f:
            coords_dict = json.load(f)
            
    # Geocodificar los que falten
    new_count = 0
    
    # Limitando a un subset en primera corrida para no quemar cuota si el user no quiere (-3k requests)
    # Por ahora solo imprime a modo de herramienta y obtiene 5 como demo o continua si el usuario lo corre.
    # Recomendado: usa un limit en producción
    
    for estado, muni in munis:
        key = f"{estado}||{muni}"
        if key in coords_dict:
            continue
            
        print(f"Geocodificando: {muni}, {estado}")
        query = f"{muni}, {estado}, Mexico"
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={urllib.parse.quote(query)}&key={API_KEY}"
        
        try:
            req = urllib.request.urlopen(url)
            res = json.loads(req.read())
            if res.get('status') == 'OK':
                loc = res['results'][0]['geometry']['location']
                coords_dict[key] = [loc['lat'], loc['lng']]
                new_count += 1
            else:
                print(f"Error para {query}: {res.get('status')}")
            time.sleep(0.05) # Rate limit respect 50/s
        except Exception as e:
            print(f"Error de red: {e}")
            break
            
        # Save every 50 to avoid losing progress
        if new_count > 0 and new_count % 50 == 0:
            with open(out_file, 'w', encoding='utf-8') as f:
                json.dump(coords_dict, f, ensure_ascii=False)
                
    if new_count > 0:
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(coords_dict, f, ensure_ascii=False)
        print(f"Se agregaron {new_count} nuevas coordenadas. Guardado en {out_file}")
    else:
        print(f"Todas las coordenadas ya estaban resueltas. Total: {len(coords_dict)}")

if __name__ == '__main__':
    # Para ejecutarlo, descomenta 'main()'
    main()
