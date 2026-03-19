'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { supabase } from '@/lib/supabase';

interface Project {
  id_proyecto: string;
  anio: number;
  promovente: string;
  proyecto: string;
  estado: string;
  municipio: string;
  sector: string;
  created_at: string;
  insight?: string;
  grounded?: boolean;
}

export default function ProjectsTable() {
  const [data, setData] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      const { data: projects, error } = await supabase
        .from('proyectos')
        .select('*')
        .order('created_at', { ascending: false })
        .limit(200);

      if (projects) {
        setData(projects);
      }
      setLoading(false);
    };

    fetchData();

    const channel = supabase
      .channel('projects_realtime')
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'proyectos' },
        (payload) => {
          console.log('New project received:', payload);
          setData(prev => [payload.new as Project, ...prev].slice(0, 250));
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  const filteredData = useMemo(() => {
    const s = searchQuery.toLowerCase();
    if (!s) return data;
    return data.filter(row => (
      row.id_proyecto.toLowerCase().includes(s) ||
      row.proyecto.toLowerCase().includes(s) ||
      row.promovente.toLowerCase().includes(s) ||
      row.municipio?.toLowerCase().includes(s)
    ));
  }, [data, searchQuery]);

  const selectedRow = useMemo(() => 
    data.find(r => r.id_proyecto === selectedId) || null
  , [data, selectedId]);

  return (
    <div className="flex flex-1 overflow-hidden h-full">
      {/* LEFT: TABLE CONTENT */}
      <div className="flex-1 flex flex-col min-w-0 bg-[#0A0A0A]">
        {/* Search Header */}
        <div className="h-14 border-b border-[#222222] flex items-center px-8 bg-[#111111]">
          <span className="text-[#FFB000] font-mono mr-4">&gt;</span>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Filtrar por ID, Municipio, Promovente..."
            className="bg-transparent border-none text-[#FFFFFF] font-mono text-[14px] outline-none flex-1 placeholder:text-[#444444]"
          />
          <div className="text-[12px] text-[#666666]">
            MOSTRANDO <span className="text-[#FFFFFF]">{filteredData.length}</span> / {data.length}
          </div>
        </div>

        {/* Table Body */}
        <div className="flex-1 overflow-auto scrollbar-tactical">
          <table className="w-full text-left">
            <thead className="sticky top-0 z-10">
              <tr>
                <th className="w-[140px]">ID_EXPEDIENTE</th>
                <th className="w-[80px]">AÑO</th>
                <th className="w-[200px]">PROMOVENTE</th>
                <th>NOMBRE_PROYECTO</th>
                <th className="w-[120px]">UBICACIÓN</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#222222]">
              {filteredData.map((row) => (
                <tr
                  key={row.id_proyecto}
                  onClick={() => {
                      console.log("Selecting project:", row.id_proyecto);
                      setSelectedId(row.id_proyecto);
                  }}
                  className={cn(
                    "cursor-pointer group transition-colors",
                    selectedId === row.id_proyecto ? "bg-[#111111] selected" : "hover:bg-[#111111]"
                  )}
                >
                  <td className="font-mono text-[#FFB000]">{row.id_proyecto}</td>
                  <td>
                    <span className={cn(
                        "px-2 py-0.5 text-[11px] font-bold",
                        row.anio === 2026 ? "bg-[#FFB000] text-black" : "bg-[#222222] text-[#AAAAAA]"
                    )}>
                        {row.anio}
                    </span>
                  </td>
                  <td className="truncate max-w-[200px]">{row.promovente}</td>
                  <td className="whitespace-normal leading-tight py-4">
                    <div className="line-clamp-2 text-[#FFFFFF] group-hover:text-[#FFB000] transition-colors font-medium">
                        {row.proyecto}
                    </div>
                  </td>
                  <td>
                    <div className="text-[12px] uppercase">{row.municipio}</div>
                    <div className="text-[10px] text-[#666666]">{row.estado}</div>
                  </td>
                </tr>
              ))}
              {loading && (
                  <tr>
                      <td colSpan={5} className="text-center py-20 animate-pulse text-[#666666]">
                          Sincronizando con base de datos central...
                      </td>
                  </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* RIGHT: DETAIL PANEL (Esoteria Card Style) */}
      <aside className="w-[400px] border-l border-[#222222] flex flex-col bg-[#111111] shrink-0 overflow-hidden">
        <div className="h-14 border-b border-[#222222] flex items-center justify-between px-6 bg-[#111111] shrink-0">
          <span className="text-[12px] font-bold text-[#FFFFFF] uppercase tracking-widest">Detalles_Módulo_Intel</span>
          {selectedRow && (
            <button 
              className="text-[#666666] hover:text-[#FFB000] transition-colors text-[14px]" 
              onClick={() => setSelectedId(null)}
            >
              [Cerrar]
            </button>
          )}
        </div>
        
        <div className="flex-1 overflow-y-auto scrollbar-tactical p-8 space-y-8">
          {!selectedRow ? (
            <div className="h-full flex flex-col items-center justify-center text-center">
                <div className="text-[#222222] text-[48px] font-bold mb-4 select-none">ZOHAR</div>
                <p className="text-[#444444] text-[13px] uppercase tracking-[0.2em]">Seleccione un expediente para visualizar telemetría</p>
            </div>
          ) : (
            <>
              <section>
                <label className="text-[10px] text-[#666666] uppercase block mb-2 tracking-tighter">Nombre del Proyecto</label>
                <h3 className="text-[18px] font-bold text-[#FFFFFF] leading-tight mb-4">{selectedRow.proyecto}</h3>
                <div className="flex gap-2">
                    <span className="px-2 py-1 bg-[#FFB000] text-black text-[11px] font-bold tracking-widest">MISSION_ACTIVE</span>
                    <span className="px-2 py-1 border border-[#222222] text-[#AAAAAA] text-[11px] uppercase">{selectedRow.sector}</span>
                </div>
              </section>

              <div className="h-px bg-[#222222]" />

              <div className="grid grid-cols-2 gap-6">
                <div>
                  <label className="text-[10px] text-[#666666] uppercase block mb-1">Carga_ID</label>
                  <div className="text-[14px] font-mono text-[#FFB000]">{selectedRow.id_proyecto}</div>
                </div>
                <div>
                  <label className="text-[10px] text-[#666666] uppercase block mb-1">Prioridad_Año</label>
                  <div className="text-[14px] text-[#FFFFFF]">{selectedRow.anio}</div>
                </div>
                <div className="col-span-2">
                  <label className="text-[10px] text-[#666666] uppercase block mb-1">Promovente_Legal</label>
                  <div className="text-[14px] text-[#FFFFFF]">{selectedRow.promovente}</div>
                </div>
                <div>
                  <label className="text-[10px] text-[#666666] uppercase block mb-1">Estado_MX</label>
                  <div className="text-[14px] text-[#FFFFFF]">{selectedRow.estado}</div>
                </div>
                <div>
                  <label className="text-[10px] text-[#666666] uppercase block mb-1">Municipio_Región</label>
                  <div className="text-[14px] text-[#FFFFFF]">{selectedRow.municipio}</div>
                </div>
              </div>

              <div className="h-px bg-[#222222]" />

              <section>
                <label className="text-[10px] text-[#666666] uppercase block mb-2 font-bold tracking-widest">Información Estratégica (Insight)</label>
                <div className="text-[14px] text-[#AAAAAA] leading-relaxed">
                  {selectedRow.insight || "No hay información adicional disponible para este proyecto en el monitor de inteligencia."}
                </div>
              </section>

              <div className="pt-8">
                <button 
                  className="w-full py-4 bg-[#FFB000] text-black font-bold uppercase tracking-[0.2em] text-[12px] hover:bg-[#D99600] transition-colors"
                >
                  Documentación_Extendida
                </button>
              </div>
            </>
          )}
        </div>
      </aside>
    </div>
  );
}

function cn(...inputs: any[]) {
  return inputs.filter(Boolean).join(' ');
}
