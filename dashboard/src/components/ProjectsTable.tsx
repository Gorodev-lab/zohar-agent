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
  description?: string;
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
                  <td className="py-2 px-4 truncate text-[#BBBBBB]">{row.modalidad || "ESTÁNDAR"}</td>
                  <td className="py-2 px-4 truncate text-[#BBBBBB]">{row.promovente}</td>
                  <td className="py-2 px-4 truncate uppercase font-bold text-[#FFFFFF]">{row.proyecto}</td>
                  <td className="py-2 px-4 truncate text-[#BBBBBB]">
                    {row.municipio}, {row.estado}
                  </td>
                  <td className="py-2 px-4 truncate text-[#666666]">{row.sector}</td>
                  <td className="py-2 px-4">
                    <span className={cn(
                        "px-1 py-0.5 font-black",
                        row.anio === 2026 ? "bg-[#FFB000] text-black" : "text-[#666666] border border-[#333333]"
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
                  <td className="py-2 px-4">
                    {row.anio === 2026 ? (
                      <span className="font-black px-2 py-0.5 bg-[#27AE60] text-black text-[9px] border border-[#27AE60]">
                        [ OK ]
                      </span>
                    ) : (
                      <span className="font-black px-2 py-0.5 text-[#666666] text-[9px] border border-[#333333]">
                        HISTORICO
                      </span>
                    )}
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

      {/* RIGHT: TACTICAL DETAIL PANEL (MATCHING 8081 AGENT CONSOLE) */}
      <aside className={cn(
        "bg-[#050505] shrink-0 overflow-hidden border-l border-[#222222] font-mono transition-all duration-300 flex flex-col",
        selectedId ? "w-[450px]" : "w-0 border-none"
      )}>
        <div className="h-10 border-b border-[#222222] flex items-center justify-between px-6 bg-[#111111] shrink-0">
          <span className="text-[#FFB000] text-[12px] font-black tracking-widest uppercase italic">== DETALLE ==</span>
          <button 
            className="text-[#666666] hover:text-[#FFFFFF] text-[11px] font-black px-2 py-0.5 border border-transparent hover:border-[#333333]" 
            onClick={() => setSelectedId(null)}
          >
            [X]
          </button>
        </div>
        
        <div className="flex-1 overflow-y-auto scrollbar-tactical p-6 space-y-6">
          {selectedRow && (
            <div className="space-y-6 text-[11px] leading-tight animate-in fade-in duration-300">
                <div>
                    <h2 className="text-[#FFFFFF] font-black text-[14px] uppercase border-b border-[#222222] pb-1 mb-4 italic leading-tight">
                      {selectedRow.promovente}
                    </h2>
                </div>

                <div className="space-y-4">
                    <div>
                        <label className="text-[#00E5FF] font-black uppercase tracking-widest block mb-0.5">PROYECTO</label>
                        <div className="text-[#FFB000] font-black uppercase text-[12px] italic leading-tight">{selectedRow.proyecto}</div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="text-[#00E5FF] font-black uppercase tracking-widest block mb-0.5">ESTADO</label>
                            <div className="text-[#FFB000] font-black uppercase">{selectedRow.estado}</div>
                        </div>
                        <div>
                            <label className="text-[#00E5FF] font-black uppercase tracking-widest block mb-0.5">MUNICIPIO</label>
                            <div className="text-[#FFB000] font-black uppercase">{selectedRow.municipio}</div>
                        </div>
                    </div>

                    <div>
                        <label className="text-[#00E5FF] font-black uppercase tracking-widest block mb-0.5">SECTOR</label>
                        <div className="text-[#FFB000] font-black uppercase">{selectedRow.sector}</div>
                    </div>

                    <div>
                        <label className="text-[#00E5FF] font-black uppercase tracking-widest block mb-0.5">ESTATUS</label>
                        <div className={cn(
                          "font-black inline-block px-2 py-0.5 text-[10px]",
                          selectedRow.anio === 2026 ? "bg-[#27AE60] text-black" : "text-[#666666] border border-[#333333]"
                        )}>
                          {selectedRow.anio === 2026 ? "[ OK ]" : "HISTORICO"}
                        </div>
                    </div>

                    <div className="space-y-4 border-t border-[#111111] pt-4">
                        <div>
                            <label className="text-[#00E5FF] font-black uppercase tracking-widest block mb-0.5">INSIGHT (IA)</label>
                            <div className="text-[#AAAAAA] leading-normal font-bold italic border-l-2 border-[#FFB000] pl-4 py-1">
                                {selectedRow.insight || "Detectando profundidad de impacto..."}
                            </div>
                        </div>

                        <div>
                            <label className="text-[#00E5FF] font-black uppercase tracking-widest block mb-0.5">DESCRIPCIÓN DEL PROYECTO</label>
                            <div className="text-[#888888] leading-relaxed italic bg-[#0A0A0A] p-3 border border-[#111111]">
                                {selectedRow.description || selectedRow.context?.slice(0, 400) + "..." || "No disponible."}
                            </div>
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4 border-t border-[#111111] pt-4">
                        <div>
                            <label className="text-[#00E5FF] font-black uppercase tracking-widest block mb-0.5">GROUNDED</label>
                            <div className="text-[#27AE60] font-black">{selectedRow.grounded ? "TRUE" : "FALSE"}</div>
                        </div>
                        <div>
                            <label className="text-[#00E5FF] font-black uppercase tracking-widest block mb-0.5">CONFIANZA_IA</label>
                            <div className="text-[#FFB000] font-black">{selectedRow.confidence}%</div>
                        </div>
                    </div>

                    <div className="border-t border-[#111111] pt-4">
                        <label className="text-[#00E5FF] font-black uppercase tracking-widest block mb-1">ENLACES TÁCTICOS</label>
                        <div className="grid grid-cols-1 gap-1">
                          {['MIA', 'Visor Geográfico', 'GACETA', 'Expediente del Trámite'].map(link => (
                            <button key={link} className="w-full text-left px-3 py-2 bg-[#111111] hover:bg-[#FFB000] hover:text-black transition-all text-[#00E5FF] text-[10px] font-black flex items-center gap-3">
                              <span className="opacity-40">→</span> {link.toUpperCase()}
                            </button>
                          ))}
                        </div>
                    </div>
                </div>

                <div className="pt-8 text-center">
                    <span className="text-[9px] text-[#222222] uppercase font-black tracking-[0.3em] font-mono">ZOHAR_RECORD_ESTRAT_v2.2_SECURED</span>
                </div>
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}
