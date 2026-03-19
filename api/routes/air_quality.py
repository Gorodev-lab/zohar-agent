from fastapi import APIRouter, HTTPException
import httpx
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import os

router = APIRouter(prefix="/api/v1/sensors", tags=["air_quality"])

# Cache simple en memoria para evitar saturar OpenAQ y respetar el cooldown del dashboard
# En un sistema distribuido usaríamos Redis, pero aquí un bypass de memoria es suficiente.
_sensors_cache: Dict[str, Any] = {
    "data": None,
    "last_updated": None
}
CACHE_TTL_SECONDS = 300  # 5 minutos

# --- Modelos GeoJSON (Pydantic) ---

class AirQualityProperties(BaseModel):
    id: int
    stationName: str
    city: str
    pm25: float = 0.0
    no2: Optional[float] = None
    o3: Optional[float] = None
    aqi_level: str
    last_updated: str
    source: str = "OpenAQ_v3"

class Geometry(BaseModel):
    type: str = "Point"
    coordinates: List[float]  # [lng, lat]

class SensorFeature(BaseModel):
    type: str = "Feature"
    geometry: Geometry
    properties: AirQualityProperties

class AirQualityFeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    features: List[SensorFeature]

# --- Utilidades ---

def calculate_aqi_level(pm25: float) -> str:
    """Calcula el nivel cualitativo de AQI basado en PM2.5 (mu/m3)"""
    if pm25 <= 12.0: return "GOOD"
    if pm25 <= 35.4: return "MODERATE"
    if pm25 <= 55.4: return "UNHEALTHY_SENSITIVE"
    if pm25 <= 150.4: return "UNHEALTHY"
    return "HAZARDOUS"

# --- Endpoints ---

@router.get("/geojson", response_model=AirQualityFeatureCollection)
async def get_sensors_geojson():
    """
    Obtiene la telemetría de OpenAQ v3 para BCS y la transforma a GeoJSON.
    """
    global _sensors_cache
    
    # 1. Verificar Cache
    now = datetime.now()
    if (_sensors_cache["data"] and _sensors_cache["last_updated"] and 
        (now - _sensors_cache["last_updated"]).total_seconds() < CACHE_TTL_SECONDS):
        return _sensors_cache["data"]

    # 2. Configuración de OpenAQ v3
    # BBOX BCS: ~22.8, -115.0 a 28.0, -109.4
    # Reemplazamos por un filtro de bbox aproximado o parámetros directos si es posible
    # API v3 usa 'bbox' parameter: 'min_lon,min_lat,max_lon,max_lat'
    # BCS BBox: -115.0, 22.8, -109.4, 28.0
    URL = "https://api.openaq.org/v3/locations"
    params = {
        "bbox": "-115.0,22.8,-109.4,28.0",
        "limit": 100
    }
    
    headers = {}
    api_key = os.getenv("OPENAQ_API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(URL, params=params, headers=headers)
            
            if response.status_code != 200:
                raise Exception(f"OpenAQ_Status: {response.status_code}")
            
            data = response.json()
            
            # 3. Transformación a GeoJSON
            features = []
            for loc in data.get("results", []):
                coords = loc.get("coordinates")
                if not coords or not coords.get("longitude") or not coords.get("latitude"):
                    continue
                
                # Extraer PM2.5 si existe
                pm25_val = 0.0
                sensors = loc.get("sensors", [])
                latest_pm25 = next((s for s in sensors if s.get("parameter", {}).get("name") == "pm25"), None)
                
                if latest_pm25 and latest_pm25.get("latest"):
                    pm25_val = latest_pm25["latest"].get("value", 0.0)
                
                # Armar propiedades
                props = AirQualityProperties(
                    id=loc.get("id", 0),
                    stationName=loc.get("name", "ESTACIÓN_DESCONOCIDA"),
                    city=loc.get("locality") or "Baja California Sur",
                    pm25=pm25_val,
                    aqi_level=calculate_aqi_level(pm25_val),
                    last_updated=loc.get("datetimeFirst") or now.isoformat()
                )
                
                feature = SensorFeature(
                    geometry=Geometry(coordinates=[coords["longitude"], coords["latitude"]]),
                    properties=props
                )
                features.append(feature)
            
            geojson_result = AirQualityFeatureCollection(features=features)
            
            # 4. Actualizar Cache
            _sensors_cache["data"] = geojson_result
            _sensors_cache["last_updated"] = now
            
            return geojson_result

    except Exception as e:
        print(f"ERROR_OPENAQ: {str(e)}")
        # Inmersión terminal en el error
        raise HTTPException(
            status_code=503, 
            detail={
                "msg": "ERROR_DE_ENLACE_TELEMETRICO", 
                "system": "ZOHAR_INTEL_BCS",
                "code": "LINK_TIMEOUT_OR_API_FAIL"
            }
        )
