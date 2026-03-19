'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface Project {
  id_proyecto: string;
  clave?: string;
  modalidad?: string;
  promovente: string;
  proyecto: string;
  estado: string;
  municipio: string;
  sector: string;
  fecha?: string;
  anio: number;
  estatus?: string;
  insight: string;
  reasoning: string;
  context: string;
  grounded: boolean;
  sources: any[];
  audit_status: string;
  auditor: string;
  confidence: number;
  coordinates: string;
  created_at?: string;
}

export default function ProjectsTable() {
  const [data, setData] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortConfig, setSortConfig] = useState<{ key: keyof Project, direction: 'asc' | 'desc' } | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
          const res = await fetch('/api/projects');
          const projects = await res.json();
          if (Array.isArray(projects)) {
            setData(projects);
          }
      } catch (err) {}
      setLoading(false);
    };

    fetchData();
  }, []);

  const sortedData = useMemo(() => {
    let items = [...data];
    if (sortConfig !== null) {
      items.sort((a, b) => {
        const aVal = a[sortConfig.key];
        const bVal = b[sortConfig.key];
        if (aVal === undefined || bVal === undefined) return 0;
        if (aVal < bVal) return sortConfig.direction === 'asc' ? -1 : 1;
        if (aVal > bVal) return sortConfig.direction === 'asc' ? 1 : -1;
        return 0;
      });
    }
    return items;
  }, [data, sortConfig]);

  const filteredData = useMemo(() => {
    const s = searchQuery.toLowerCase();
    if (!s) return sortedData;
    return sortedData.filter(row => (
      row.id_proyecto.toLowerCase().includes(s) ||
      row.proyecto.toLowerCase().includes(s) ||
      row.promovente.toLowerCase().includes(s) ||
      row.municipio?.toLowerCase().includes(s)
    ));
  }, [sortedData, searchQuery]);

  const selectedRow = useMemo(() => 
    data.find(r => r.id_proyecto === selectedId) || null
  , [data, selectedId]);

  const handleSort = (key: keyof Project) => {
    let direction: 'asc' | 'desc' = 'asc';
    if (sortConfig && sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };

  return (
    <div className="flex flex-1 overflow-hidden h-full bg-[#0A0A0A]">
      {/* LEFT: TACTICAL DATA GRID */}
      <div className="flex-1 flex flex-col min-w-0 border-r border-[#222222]">
        {/* Search & Header Stats */}
        <div className="h-12 border-b border-[#222222] flex items-center px-8 bg-[#111111] shrink-0 font-mono">
          <span className="text-[#FFB000] text-[10px] mr-4 font-black">CMD&gt;</span>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="FILTRAR_DATOS: clave, proyecto, promovente..."
            className="bg-transparent border-none text-[#FFFFFF] font-mono text-[10px] outline-none flex-1 placeholder:text-[#333333] uppercase tracking-widest"
          />
          <div className="flex items-center gap-6 border-l border-[#222222] pl-8 h-full">
              <div className="text-[10px] text-[#666666] font-black uppercase">VISTA: TABULAR_v2</div>
              <div className="text-[11px] text-[#FFB000] font-black select-none">
                {filteredData.length} REGS_CARGADOS
              </div>
          </div>
        </div>

        {/* Dense Table Body */}
        <div className="flex-1 overflow-auto scrollbar-tactical bg-[#050505]">
          <table className="w-full text-left font-mono border-collapse min-w-[1400px]">
            <thead className="sticky top-0 z-20 bg-[#111111]">
              <tr className="border-b border-[#222222] text-[10px] text-[#666666] font-black uppercase">
                <th onClick={() => handleSort('id_proyecto')} className="py-3 px-4 w-[150px] sticky left-0 bg-[#111111] z-30 cursor-pointer hover:text-[#FFB000]">
                  CLAVE {sortConfig?.key === 'id_proyecto' && (sortConfig.direction === 'asc' ? '▲' : '▼')}
                </th>
                <th onClick={() => handleSort('modalidad')} className="py-3 px-4 w-[180px] cursor-pointer hover:text-[#FFB000]">MODALIDAD</th>
                <th onClick={() => handleSort('promovente')} className="py-3 px-4 w-[220px] cursor-pointer hover:text-[#FFB000]">PROMOVENTE</th>
                <th onClick={() => handleSort('proyecto')} className="py-3 px-4 w-[300px] cursor-pointer hover:text-[#FFB000]">PROYECTO</th>
                <th onClick={() => handleSort('municipio')} className="py-3 px-4 w-[180px] cursor-pointer hover:text-[#FFB000]">UBICACION</th>
                <th onClick={() => handleSort('sector')} className="py-3 px-4 w-[150px] cursor-pointer hover:text-[#FFB000]">SECTOR</th>
                <th onClick={() => handleSort('anio')} className="py-3 px-4 w-[80px] cursor-pointer hover:text-[#FFB000]">AÑO</th>
                <th onClick={() => handleSort('confidence')} className="py-3 px-4 w-[100px] cursor-pointer hover:text-[#FFB000]">INTEL_CONF%</th>
                <th onClick={() => handleSort('estatus')} className="py-3 px-4 w-[120px] cursor-pointer hover:text-[#FFB000]">ESTATUS</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#111111]">
              {filteredData.map((row) => (
                <tr
                  key={row.id_proyecto}
                  onClick={() => setSelectedId(row.id_proyecto)}
                  className={cn(
                    "cursor-pointer transition-none text-[10px] border-l-2",
                    selectedId === row.id_proyecto ? "bg-[#FFB000] text-black border-black" : "hover:bg-[#111111] text-[#AAAAAA] border-transparent"
                  )}
                >
                  <td className={cn(
                      "py-3 px-4 font-bold sticky left-0 z-20",
                      selectedId === row.id_proyecto ? "bg-[#FFB000] text-black" : "bg-[#050505]"
                  )}>
                    {row.id_proyecto}
                  </td>
                  <td className="py-3 px-4 truncate">{row.modalidad || "PROYECTO_ESTÁNDAR"}</td>
                  <td className="py-3 px-4 truncate">{row.promovente}</td>
                  <td className="py-3 px-4 truncate uppercase font-bold">{row.proyecto}</td>
                  <td className="py-3 px-4 truncate">
                    {row.estado} / {row.municipio}
                  </td>
                  <td className="py-3 px-4 truncate text-[#666666]">{row.sector}</td>
                  <td className="py-3 px-4">
                    <span className={cn(
                        "px-1 py-0.5 font-black",
                        row.anio === 2026 && selectedId !== row.id_proyecto ? "text-[#FFB000] border border-[#FFB000]" : ""
                    )}>{row.anio}</span>
                  </td>
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-2">
                        <div className="flex-1 h-1 bg-[#222222]">
                            <div 
                                className={cn("h-full", selectedId === row.id_proyecto ? "bg-black" : "bg-[#FFB000]")} 
                                style={{ width: `${row.confidence}%` }} 
                            />
                        </div>
                        <span className="font-bold">{row.confidence}%</span>
                    </div>
                  </td>
                  <td className="py-3 px-4">
                    <span className={cn(
                        "font-black px-2 py-0.5 border text-[9px]",
                        selectedId === row.id_proyecto ? "border-black text-black" : "border-[#27AE60] text-[#27AE60]"
                    )}>
                        [{row.estatus || "ACTIVO_SCAN"}]
                    </span>
                  </td>
                </tr>
              ))}
              {loading && (
                  <tr>
                      <td colSpan={9} className="text-center py-40 animate-pulse text-[#FFB000] font-mono text-[11px] uppercase font-black">
                        EJECUTANDO_DATA_QUERY_ENGINE_z26_
                      </td>
                  </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* RIGHT: TACTICAL DETAIL PANEL (DETALLE MEJORADO) */}
      <aside className="w-[500px] flex flex-col bg-[#050505] shrink-0 overflow-hidden border-l border-[#222222]">
        <div className="h-12 border-b border-[#222222] flex items-center justify-between px-8 bg-[#111111] shrink-0 font-mono">
          <div className="flex items-center gap-3">
            <span className="w-3 h-3 bg-[#FFB000]" />
            <span className="text-[#FFB000] text-[13px] font-black uppercase tracking-[0.2em]">INTEL_DETALLE: PROYECTO</span>
          </div>
          {selectedRow && (
            <button 
              className="text-[#666666] hover:text-[#FFFFFF] text-[11px] font-black transition-none border border-[#333333] px-2 py-0.5" 
              onClick={() => setSelectedId(null)}
            >
              [X] CERRAR
            </button>
          )}
        </div>
        
        <div className="flex-1 overflow-y-auto scrollbar-tactical p-10 space-y-10 font-mono">
          {!selectedRow ? (
            <div className="h-full flex flex-col items-center justify-center text-center opacity-10">
                <div className="text-[#666666] text-[80px] font-black mb-4">ZHR</div>
                <p className="text-[#666666] text-[10px] uppercase tracking-[0.8em] font-black border border-[#222222] px-6 py-3">ESPERANDO_SELECCION</p>
            </div>
          ) : (
            <div className="space-y-12 animate-in fade-in transition-all">
                {/* SECCION I: IDENTITY */}
                <section className="space-y-6">
                    <div className="flex items-center justify-between border-b border-[#222222] pb-2">
                        <span className="text-[12px] text-[#FFB000] font-black tracking-widest">== IDENTITY_ID: {selectedRow.id_proyecto} ==</span>
                        <span className="text-[9px] text-[#444444] font-black font-mono">HASH_{selectedRow.id_proyecto.slice(-4)}</span>
                    </div>
                    <div className="space-y-4">
                        <div>
                            <label className="text-[9px] text-[#555555] font-black uppercase tracking-widest block mb-1">Nombre Completo del Proyecto</label>
                            <h2 className="text-[20px] text-[#FFFFFF] font-black leading-tight uppercase italic">{selectedRow.proyecto}</h2>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            <div className="p-3 bg-[#111111] border border-[#222222]">
                                <label className="text-[8px] text-[#444444] font-black uppercase block mb-1">Modalidad de Trámite</label>
                                <span className="text-[10px] text-[#AAAAAA] font-bold block">{selectedRow.modalidad || "ESTÁNDAR_ZHR"}</span>
                            </div>
                            <div className="p-3 bg-[#111111] border border-[#222222]">
                                <label className="text-[8px] text-[#444444] font-black uppercase block mb-1">Año Ciclo</label>
                                <span className="text-[16px] text-[#FFFFFF] font-black block">{selectedRow.anio}</span>
                            </div>
                        </div>
                    </div>
                </section>

                {/* SECCION II: ANALYTICS & CONFIDENCE */}
                <section className="space-y-6 bg-[#080808] p-6 border border-[#111111]">
                    <div className="text-[11px] text-[#FFB000] font-black tracking-widest border-b border-[#222222] pb-2">== AI_ANALYTICS_CONFIDENCE ==</div>
                    <div className="grid grid-cols-2 gap-8">
                        <div>
                            <label className="text-[9px] text-[#555555] font-black block mb-2">SCORE_DE_CONFIANZA</label>
                            <div className="relative h-20 w-20 flex items-center justify-center border-4 border-[#111111]">
                                <div 
                                    className="absolute inset-0 bg-[#FFB000]/10" 
                                    style={{ height: `${selectedRow.confidence}%`, top: 'auto' }}
                                />
                                <span className="text-[24px] text-[#FFB000] font-black relative z-10">{selectedRow.confidence}%</span>
                            </div>
                        </div>
                        <div className="space-y-4">
                            <div>
                                <label className="text-[9px] text-[#555555] font-black block mb-1">STATUS_VERIFICACION</label>
                                <div className="text-[12px] text-[#27AE60] font-black flex items-center gap-2">
                                    <span className="w-2 h-2 bg-[#27AE60] rounded-full" />
                                    {selectedRow.grounded ? "GROUNDED_AND_VERIFIED" : "PENDING_VALIDATION"}
                                </div>
                            </div>
                            <div>
                                <label className="text-[9px] text-[#555555] font-black block mb-1">NIVEL_DE_RIESGO</label>
                                <div className={cn(
                                    "text-[12px] font-black px-2 py-0.5 border inline-block",
                                    selectedRow.confidence > 90 ? "text-[#27AE60] border-[#27AE60]" : "text-[#E67E22] border-[#E67E22]"
                                )}>
                                    {selectedRow.confidence > 90 ? "RIESGO_BAJO" : "RIESGO_MODERADO"}
                                </div>
                            </div>
                        </div>
                    </div>
                </section>

                {/* SECCION III: DESCRIPTIVE DETAILS */}
                <section className="space-y-6">
                    <div className="text-[11px] text-[#FFB000] font-black tracking-widest border-b border-[#222222] pb-2">== CONTEXTO_DETALLADO ==</div>
                    <div className="space-y-6 text-[11px]">
                        <div>
                            <label className="text-[#444444] font-black uppercase block mb-2">Promovente Responsable</label>
                            <div className="text-[#AAAAAA] bg-[#0A0A0A] p-4 border-l-2 border-[#FFB000] uppercase font-bold">{selectedRow.promovente}</div>
                        </div>
                        <div className="grid grid-cols-2 gap-6">
                            <div>
                                <label className="text-[#444444] font-black block mb-1">Ubicación Administrativa</label>
                                <div className="text-[#FFFFFF] uppercase">{selectedRow.estado}</div>
                                <div className="text-[#666666] text-[10px] uppercase">{selectedRow.municipio}</div>
                            </div>
                            <div>
                                <label className="text-[#444444] font-black block mb-1">Sector Industrial</label>
                                <div className="text-[#FFFFFF] uppercase">{selectedRow.sector}</div>
                            </div>
                        </div>
                        <div>
                            <label className="text-[#444444] font-black block mb-1">Intel Insight (AI Summary)</label>
                            <p className="text-[#888888] leading-relaxed italic">{selectedRow.insight || "No hay un resumen analítico disponible para este registro en este ciclo."}</p>
                        </div>
                    </div>
                </section>

                {/* SECCION IV: SOURCES & LINKS */}
                <section className="space-y-6 pt-6 border-t border-[#111111]">
                    <div className="text-[11px] text-[#FFB000] font-black tracking-widest uppercase">== ARCHIVOS_Y_FUENTES ==</div>
                    <div className="grid grid-cols-2 gap-2">
                        {[
                            { label: 'GACETA_PDF', color: '#FFFFFF' },
                            { label: 'EXPEDIENTE_DIG', color: '#AAAAAA' },
                            { label: 'RESOLUCION_SCAN', color: '#AAAAAA' },
                            { label: 'MAPA_GEOGRAFICO', color: '#27AE60' }
                        ].map((link, i) => (
                            <button key={i} className="flex items-center gap-3 p-3 bg-[#111111] hover:bg-[#FFB000] hover:text-black transition-all group border border-transparent hover:border-black">
                                <span className="text-[9px] font-black" style={{ color: link.color }}>[{link.label}]</span>
                                <span className="text-[8px] opacity-0 group-hover:opacity-100 font-bold ml-auto">OPEN_FILE ↗</span>
                            </button>
                        ))}
                    </div>
                </section>
                
                <div className="h-12 border-t border-[#111111] pt-4 text-center">
                    <span className="text-[8px] text-[#333333] uppercase font-black tracking-[0.4em]">ZOHAR_INTEL_SYSTEM_RECORDS_SECURED</span>
                </div>
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}
