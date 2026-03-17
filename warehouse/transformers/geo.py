"""
warehouse/transformers/geo.py
GeoTransformer cruza datos de municipio con el catálogo (muni_coords.json) 
para obtener latitud y longitud oficiales.
"""
import json
import logging
from pathlib import Path

log = logging.getLogger("warehouse.geo")

class GeoTransformer:
    def __init__(self):
        self.coords_dict = {}
        json_path = Path(__file__).resolve().parent.parent.parent / "dashboard" / "muni_coords.json"
        try:
            if json_path.exists():
                with open(json_path, 'r', encoding='utf-8') as f:
                    self.coords_dict = json.load(f)
                log.info(f"GeoTransformer: cargadas {len(self.coords_dict)} coordenadas.")
            else:
                log.warning(f"GeoTransformer: diccionario en {json_path} no existe.")
        except Exception as e:
            log.warning(f"GeoTransformer: error leyendo {json_path}: {e}")

    def transform(self, emisiones: list[dict]) -> list[dict]:
        transformed = 0
        for e in emisiones:
            estado = e.get("entidad", "").strip()
            muni = e.get("municipio", "").strip()
            key = f"{estado}||{muni}"
            if key in self.coords_dict:
                coords = self.coords_dict[key]
                e["lat"] = coords[0]
                e["lon"] = coords[1]
                transformed += 1
            else:
                e["lat"] = None
                e["lon"] = None
        log.info(f"GeoTransformer: {transformed}/{len(emisiones)} geocodificados.")
        return emisiones
