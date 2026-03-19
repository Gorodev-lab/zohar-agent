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
  fuente?: string;
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
            25, '#FFD700',  // MODERATE (Amber-ish)
            50, '#FFB000',  // UNHEALTHY (Esoteria Amber)
            100, '#C0392B'  // HAZARDOUS/RED
          ],
          'circle-opacity': 0.9,
          'circle-stroke-width': 1.5,
          'circle-stroke-color': '#000000'
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
    <div className="flex flex-1 overflow-hidden h-full font-mono">
      <div className="flex-1 relative bg-[#0A0A0A]">
        <div ref={mapContainer} className="absolute inset-0" />
        
        {/* Leyenda Esoteria */}
        <div className="absolute top-10 left-10 p-6 bg-[#0A0A0A]/90 backdrop-blur-md border border-[#FFB000]/20 z-10 space-y-4 max-w-[220px] shadow-2xl">
          <h4 className="text-[11px] font-black text-[#FFB000] uppercase tracking-[0.3em] border-b border-[#FFB000]/30 pb-3 mb-4 flex items-center gap-2">
            <span className="w-2 h-2 bg-[#FFB000] animate-pulse" />
            AIRE_INTEL // v1.0
          </h4>
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 bg-[#27AE60]" />
                <span className="text-[10px] text-[#AAAAAA] uppercase tracking-wider">Óptima</span>
              </div>
              <span className="text-[9px] text-[#444444] font-mono">&lt; 25 PM2.5</span>
            </div>
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 bg-[#FFD700]" />
                <span className="text-[10px] text-[#AAAAAA] uppercase tracking-wider">Nominal</span>
              </div>
              <span className="text-[9px] text-[#444444] font-mono">25-50 PM2.5</span>
            </div>
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 bg-[#FFB000]" />
                <span className="text-[10px] text-[#FFB000] uppercase tracking-wider font-bold">Crítica</span>
              </div>
              <span className="text-[9px] text-[#444444] font-mono">50-100 PM2.5</span>
            </div>
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 bg-[#C0392B]" />
                <span className="text-[10px] text-[#C0392B] uppercase tracking-wider font-bold">Peligro</span>
              </div>
              <span className="text-[9px] text-[#444444] font-mono">&gt; 100 PM2.5</span>
            </div>
          </div>
          <div className="pt-4 border-t border-[#FFB000]/10 flex flex-col gap-1">
            <p className="text-[9px] text-[#666666] leading-tight uppercase font-mono">
              Nodos_Activos: {sensors.length}
            </p>
            <p className="text-[9px] text-[#333333] leading-tight uppercase font-mono">
              Ref: {new Date().toISOString().split('T')[0]} // MX_DAT
            </p>
          </div>
        </div>
      </div>

      {/* Sidebar List (Esoteria Style) */}
      <aside className="w-[380px] border-l border-[#222222] flex flex-col bg-[#0A0A0A] overflow-hidden shrink-0">
        <header className="p-6 border-b border-[#222222] bg-[#111111]">
            <div className="flex items-center justify-between mb-2">
                <h3 className="text-[13px] font-black text-[#FFFFFF] uppercase tracking-[0.2em]">Telemetría_Nacional</h3>
                <span className="text-[9px] bg-[#FFB000] text-black px-1 font-black">STREAMING</span>
            </div>
            <p className="text-[10px] text-[#666666] font-mono uppercase tracking-widest">Sincronización Supabase_Realtime</p>
        </header>
        
        <div className="flex-1 overflow-y-auto scrollbar-tactical divide-y divide-[#1A1A1A] bg-[#0A0A0A]">
          {sensors.slice(0, 100).map(s => (
            <div key={s.id} className="p-4 hover:bg-[#111111] transition-all cursor-default group border-l-2 border-transparent hover:border-[#FFB000]">
              <div className="flex justify-between items-start mb-1">
                <span className="text-[12px] font-bold text-[#DDDDDD] uppercase truncate pr-4 group-hover:text-[#FFB000]">{s.municipio}</span>
                <div className="flex flex-col items-end">
                    <span className={`text-[12px] font-mono font-black ${(s.pm25 ?? 0) > 50 ? 'text-[#C0392B]' : (s.pm25 ?? 0) > 25 ? 'text-[#FFD700]' : 'text-[#27AE60]'}`}>
                      {(s.pm25 ?? 0).toFixed(2)}
                    </span>
                    <span className="text-[8px] text-[#444444] font-mono">µg/m³</span>
                </div>
              </div>
              <div className="flex justify-between items-center">
                <div className="flex items-center gap-2">
                    <span className="text-[9px] text-[#666666] uppercase tracking-tighter">{s.entidad}</span>
                    <span className="text-[9px] text-[#333333] tracking-tighter">// {s.fuente || 'GND_STATION'}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
        
        <footer className="p-4 bg-[#111111] border-t border-[#222222]">
            <div className="flex items-center justify-between text-[9px] font-mono text-[#444444] uppercase">
                <span>Buffer_Status: Nominal</span>
                <span>Latency: 42ms</span>
            </div>
        </footer>
      </aside>
    </div>
  );
}
