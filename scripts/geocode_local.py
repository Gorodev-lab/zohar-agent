#!/usr/bin/env python3
"""
Zohar Agent - Local Geocoder (Geonames)
Genera muni_coords.json utilizando la base de datos libre Geonames
sin necesidad de Google Maps Geocoding API, logrando precisión inmediata.
"""

import os
import csv
import json
import zipfile
import urllib.request
from pathlib import Path

# Configuraciones
MX_ZIP_URL = "https://download.geonames.org/export/dump/MX.zip"
TMP_DIR = Path("/tmp/geonames_mx")
MX_TXT = TMP_DIR / "MX.txt"

def unidecode(text):
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn').upper()

def main():
    print("Iniciando geocodificación local usando Geonames...")
    
    csv_path = Path(__file__).resolve().parent.parent / 'd3_aire01_49_1.csv'
    if not csv_path.exists():
        csv_path = Path('d3_aire01_49_1.csv')
        if not csv_path.exists():
            print("No se encontró el archivo CSV de datos de aire.")
            return

    # 1. Leer los municipios únicos
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
    
    print(f"Total de municipios en CSV: {len(munis)}")

    # 2. Descargar y extraer MX.txt
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    if not MX_TXT.exists():
        print("Descargando base de datos Geonames (MX.zip)...")
        zip_path = TMP_DIR / "MX.zip"
        urllib.request.urlretrieve(MX_ZIP_URL, zip_path)
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(TMP_DIR)
        print("Descarga y extracción completada.")

    # 3. Leer Geonames en memoria
    print("Cargando diccionario geográfico...")
    # Formato Geonames: geonameid, name, asciiname, alternatenames, latitude, longitude, feature class, feature code, country code, cc2, admin1 code...
    
    # Creamos dos indices para match exacto y match parcial
    geonames_exact = {}
    
    # Mapeo de códigos de estados Geonames (admin1) a nombres en nuestro CSV
    admin1_map = {
        '01': 'AGUASCALIENTES', '02': 'BAJA CALIFORNIA', '03': 'BAJA CALIFORNIA SUR', '04': 'CAMPECHE',
        '05': 'COAHUILA', '06': 'COLIMA', '07': 'CHIAPAS', '08': 'CHIHUAHUA', '09': 'CIUDAD DE MEXICO',
        '10': 'DURANGO', '11': 'GUANAJUATO', '12': 'GUERRERO', '13': 'HIDALGO', '14': 'JALISCO',
        '15': 'MEXICO', '16': 'MICHOACAN', '17': 'MORELOS', '18': 'NAYARIT', '19': 'NUEVO LEON',
        '20': 'OAXACA', '21': 'PUEBLA', '22': 'QUERETARO', '23': 'QUINTANA ROO', '24': 'SAN LUIS POTOSI',
        '25': 'SINALOA', '26': 'SONORA', '27': 'TABASCO', '28': 'TAMAULIPAS', '29': 'TLAXCALA',
        '30': 'VERACRUZ', '31': 'YUCATAN', '32': 'ZACATECAS'
    }

    with open(MX_TXT, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='\t')
        for row in reader:
            if len(row) < 11:
                continue
            name = unidecode(row[1])
            lat = float(row[4])
            lng = float(row[5])
            fcode = row[7] # PPL, ADM2(Muni), etc
            admin1_code = row[10]
            
            # Priorizamos ADM2 (Municipios) o PPLA/PPLC (Cabeceras)
            score = 0
            if fcode == 'ADM2': score = 10  # Es un municipio formal
            elif fcode.startswith('PPL'): score = 5  # Es una ciudad
            else: score = 1
            
            estado_geo = admin1_map.get(admin1_code, "")
            key = f"{estado_geo}||{name}"
            
            if key not in geonames_exact or geonames_exact[key]['score'] < score:
                geonames_exact[key] = {'lat': lat, 'lng': lng, 'score': score}

    # 4. Machar nuestros municipios
    resolved = {}
    unresolved = []
    
    for estado, muni in munis:
        estado_clean = unidecode(estado)
        muni_clean = unidecode(muni)
        
        # Ajustes comunes de nombres entre catálogos
        if estado_clean == 'VERACRUZ DE IGNACIO DE LA LLAVE': estado_clean = 'VERACRUZ'
        if estado_clean == 'COAHUILA DE ZARAGOZA': estado_clean = 'COAHUILA'
        if estado_clean == 'MICHOACAN DE OCAMPO': estado_clean = 'MICHOACAN'
        if estado_clean == 'ESTADO DE MEXICO': estado_clean = 'MEXICO'

        key = f"{estado.strip()}||{muni.strip()}"
        match_key = f"{estado_clean}||{muni_clean}"
        
        if match_key in geonames_exact:
            resolved[key] = [geonames_exact[match_key]['lat'], geonames_exact[match_key]['lng']]
        else:
            # Fallback a match más flexible (sin "San", "De", etc.)
            base_muni = muni_clean.replace("SAN ", "").replace("SANTA ", "").replace(" VILLA", "")
            base_key = f"{estado_clean}||{base_muni}"
            if base_key in geonames_exact:
                resolved[key] = [geonames_exact[base_key]['lat'], geonames_exact[base_key]['lng']]
            else:
                # Tratar de buscar solo el nombre del muni si es suficientemente unico
                best_match = None
                for k, v in geonames_exact.items():
                    if k.endswith(f"||{muni_clean}"):
                        best_match = v
                        break
                
                if best_match:
                    resolved[key] = [best_match['lat'], best_match['lng']]
                else:
                    unresolved.append((estado, muni))

    # 5. Escribir resultado
    out_dir = Path(__file__).resolve().parent.parent / 'dashboard'
    out_file = out_dir / 'muni_coords.json'
    
    if not out_dir.exists():
         out_dir = Path('dashboard')
         out_file = out_dir / 'muni_coords.json'
         out_dir.mkdir(exist_ok=True)

    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(resolved, f, ensure_ascii=False)
        
    print(f"\nResumen:")
    print(f"- Resueltos en local: {len(resolved)}")
    print(f"- No encontrados: {len(unresolved)}")
    print(f"Archivo guardado y listo en: {out_file}")

if __name__ == '__main__':
    main()
