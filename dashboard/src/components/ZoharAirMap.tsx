'use client';

import React, { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { supabase } from '@/lib/supabase';

interface AirSensor {
  id: number;
  municipio: string;
  entidad: string;
  pm25: number;
  lat: number;
  lon: number;
  created_at: string;
}

export default function ZoharAirMap() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [sensors, setSensors] = useState<AirSensor[]>([]);

  useEffect(() => {
    const fetchSensors = async () => {
      const { data } = await supabase
        .from('aire_emisiones')
        .select('*')
        .not('lat', 'is', null)
        .limit(1000);
      
      if (data) setSensors(data as AirSensor[]);
    };

    fetchSensors();
  }, []);

  useEffect(() => {
    if (!mapContainer.current) return;
    if (map.current) return;

    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
      center: [-102.5528, 23.6345], // Céntrado en México
      zoom: 4
    });

    map.current.on('load', () => {
      if (!map.current) return;

      // Estilo de Esoteria para el mapa: Oscuro total
      map.current.addSource('sensors', {
        type: 'geojson',
        data: {
          type: 'FeatureCollection',
          features: []
        }
      });

      // Capa de puntos (Esoteria Amber)
      map.current.addLayer({
        id: 'sensor-points',
        type: 'circle',
        source: 'sensors',
        paint: {
          'circle-radius': [
            'interpolate', ['linear'], ['coalesce', ['get', 'pm25'], 0],
            0, 3,
            50, 10,
            150, 20
          ],
          'circle-color': [
            'interpolate', ['linear'], ['coalesce', ['get', 'pm25'], 0],
            0, '#27AE60',   // GOOD
            35, '#F39C12',  // MODERATE
            55, '#C0392B',  // UNHEALTHY
            150, '#FFB000'  // HAZARDOUS/AMBER ESOTERIA
          ],
          'circle-opacity': 0.8,
          'circle-stroke-width': 1,
          'circle-stroke-color': '#FFFFFF'
        }
      });
    });

    return () => {
      map.current?.remove();
      map.current = null;
    };
  }, []);

  // Update data when sensors fetch
  useEffect(() => {
    if (!map.current || !sensors.length) return;

    const source = map.current.getSource('sensors') as maplibregl.GeoJSONSource;
    if (source) {
      source.setData({
        type: 'FeatureCollection',
        features: sensors.map(s => ({
          type: 'Feature',
          geometry: {
            type: 'Point',
            coordinates: [s.lon, s.lat]
          },
          properties: {
            id: s.id,
            municipio: s.municipio,
            pm25: s.pm25 || 0
          }
        }))
      });
    }
  }, [sensors]);

  return (
    <div className="flex flex-1 overflow-hidden h-full">
      <div className="flex-1 relative bg-[#0A0A0A]">
        <div ref={mapContainer} className="absolute inset-0" />
        
        {/* Leyenda Esoteria */}
        <div className="absolute bottom-10 left-10 p-6 bg-[#111111] border border-[#222222] z-10 space-y-4 max-w-[200px]">
          <h4 className="text-[12px] font-bold text-[#FFFFFF] uppercase tracking-widest border-b border-[#222222] pb-2 mb-4">
            Intel_Calidad_Aire
          </h4>
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <span className="w-3 h-3 bg-[#27AE60]" />
              <span className="text-[11px] text-[#AAAAAA] uppercase">Buena</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="w-3 h-3 bg-[#F39C12]" />
              <span className="text-[11px] text-[#AAAAAA] uppercase">Moderada</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="w-3 h-3 bg-[#C0392B]" />
              <span className="text-[11px] text-[#AAAAAA] uppercase">Riesgo</span>
            </div>
          </div>
          <div className="pt-4 border-t border-[#222222]">
            <p className="text-[10px] text-[#666666] leading-tight uppercase font-mono">
              Base_Municipios: {sensors.length} puntos_sincronizados
            </p>
          </div>
        </div>
      </div>

      {/* Sidebar List (Esoteria Style) */}
      <aside className="w-[350px] border-l border-[#222222] flex flex-col bg-[#111111] overflow-hidden shrink-0">
        <header className="p-6 border-b border-[#222222] bg-[#111111]">
            <h3 className="text-[14px] font-bold text-[#FFFFFF] uppercase tracking-[0.2em] mb-1">Telemetría_Nacional</h3>
            <p className="text-[10px] text-[#666666] font-mono uppercase">Streaming de datos v3.0</p>
        </header>
        
        <div className="flex-1 overflow-y-auto scrollbar-tactical divide-y divide-[#222222]">
          {sensors.slice(0, 50).map(s => (
            <div key={s.id} className="p-4 hover:bg-[#1A1A1A] transition-colors cursor-default group">
              <div className="flex justify-between items-start mb-1">
                <span className="text-[13px] font-bold text-[#FFFFFF] uppercase truncate pr-4">{s.municipio}</span>
                <span className={`text-[13px] font-mono font-bold ${(s.pm25 ?? 0) > 50 ? 'text-[#C0392B]' : 'text-[#27AE60]'}`}>
                  {(s.pm25 ?? 0).toFixed(1)}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-[10px] text-[#666666] uppercase">{s.entidad}</span>
                <span className="text-[10px] text-[#444444] font-mono">
                  {s.created_at ? new Date(s.created_at).toLocaleTimeString() : 'N/A'}
                </span>
              </div>
            </div>
          ))}
        </div>
      </aside>
    </div>
  );
}
