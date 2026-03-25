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
    // Filtro estricto: Únicamente proyectos del 2026
    const only2026 = sortedData.filter(r => r.anio === 2026);
    
    if (!s) return only2026;
    return only2026.filter(row => (
      row.id_proyecto.toLowerCase().includes(s) ||
      row.proyecto.toLowerCase().includes(s) ||
      row.promovente.toLowerCase().includes(s) ||
      row.municipio?.toLowerCase().includes(s) ||
      row.estado?.toLowerCase().includes(s)
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
              <tr className="border-b border-[#222222] text-[9px] text-[#666666] font-black uppercase tracking-tighter">
                <th onClick={() => handleSort('id_proyecto')} className="py-3 px-4 w-[160px] sticky left-0 bg-[#1a1a1a] z-30 cursor-pointer hover:text-[#FFB000] border-r border-[#111111]">
                  CLAVE {sortConfig?.key === 'id_proyecto' && (sortConfig.direction === 'asc' ? '▲' : '▼')}
                </th>
                <th onClick={() => handleSort('modalidad')} className="py-3 px-4 w-[140px] cursor-pointer hover:text-[#FFB000] border-r border-[#111111]">MODALIDAD</th>
                <th onClick={() => handleSort('promovente')} className="py-3 px-4 w-[240px] cursor-pointer hover:text-[#FFB000] border-r border-[#111111]">PROMOVENTE {sortConfig?.key === 'promovente' && (sortConfig.direction === 'asc' ? '▲' : '▼')}</th>
                <th onClick={() => handleSort('proyecto')} className="py-3 px-4 min-w-[350px] cursor-pointer hover:text-[#FFB000] border-r border-[#111111]">PROYECTO {sortConfig?.key === 'proyecto' && (sortConfig.direction === 'asc' ? '▲' : '▼')}</th>
                <th onClick={() => handleSort('estado')} className="py-3 px-4 w-[160px] cursor-pointer hover:text-[#00E5FF] transition-colors border-r border-[#111111]">ESTADO {sortConfig?.key === 'estado' && (sortConfig.direction === 'asc' ? '▲' : '▼')}</th>
                <th onClick={() => handleSort('municipio')} className="py-3 px-4 w-[180px] cursor-pointer hover:text-[#00E5FF] transition-colors border-r border-[#111111]">LOCALIDAD {sortConfig?.key === 'municipio' && (sortConfig.direction === 'asc' ? '▲' : '▼')}</th>
                <th onClick={() => handleSort('sector')} className="py-3 px-4 w-[150px] cursor-pointer hover:text-[#FFB000] border-r border-[#111111]">SECTOR {sortConfig?.key === 'sector' && (sortConfig.direction === 'asc' ? '▲' : '▼')}</th>
                <th onClick={() => handleSort('confidence')} className="py-3 px-4 w-[100px] cursor-pointer hover:text-[#FFB000] border-r border-[#111111]">INTEL% {sortConfig?.key === 'confidence' && (sortConfig.direction === 'asc' ? '▲' : '▼')}</th>
                <th onClick={() => handleSort('estatus')} className="py-3 px-4 w-[80px] cursor-pointer hover:text-[#FFB000]">STATUS</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#111111]">
              {filteredData.map((row) => (
                <tr
                  key={row.id_proyecto}
                  onClick={() => setSelectedId(row.id_proyecto)}
                  className={cn(
                    "cursor-pointer transition-colors duration-200 text-[10px] border-l-2",
                    selectedId === row.id_proyecto ? "bg-[#1A1810] text-white border-[#FFB000]" : "hover:bg-[#111111] text-[#AAAAAA] border-transparent"
                  )}
                >
                  <td className={cn(
                      "py-3 px-4 font-bold sticky left-0 z-20 group-hover:bg-[#111111] transition-colors duration-200",
                      selectedId === row.id_proyecto ? "bg-[#1A1810] text-[#FFB000]" : "bg-[#050505]"
                  )}>
                    {row.id_proyecto}
                  </td>
                  <td className="py-2 px-4 truncate text-[#BBBBBB]">{row.modalidad || "ESTÁNDAR"}</td>
                  <td className="py-2 px-4 truncate text-[#BBBBBB]">{row.promovente}</td>
                  <td className="py-2 px-4 truncate uppercase font-bold text-[#FFFFFF]">{row.proyecto}</td>
                  <td className="py-2 px-4 truncate font-bold text-[#00E5FF] group-hover:text-white transition-colors">{row.estado}</td>
                  <td className="py-2 px-4 truncate text-[#BBBBBB] group-hover:text-white transition-colors">{row.municipio}</td>
                  <td className="py-2 px-4 truncate text-[#666666]">{row.sector}</td>
                  <td className="py-2 px-4">
                    <span className={cn(
                        "px-1 py-0.5 font-black",
                        row.anio === 2026 ? "bg-[#FFB000] text-black" : "text-[#666666] border border-[#333333]"
                    )}>{row.anio}</span>
                  </td>
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-2">
                        <div className="flex-1 h-1 bg-[#222222] rounded-full overflow-hidden shadow-[0_0_5px_rgba(255,176,0,0.2)]">
                            <div 
                                className="h-full bg-gradient-to-r from-[#FFB000] to-[#FF8C00] shadow-[0_0_10px_rgba(255,176,0,0.8)]" 
                                style={{ width: `${row.confidence}%` }} 
                            />
                        </div>
                        <span className={cn("font-bold", selectedId === row.id_proyecto ? "text-[#FFB000]" : "text-white")}>{row.confidence}%</span>
                    </div>
                  </td>
                  <td className="py-2 px-4">
                      <span className="font-black px-2 py-0.5 bg-[#27AE60]/20 text-[#27AE60] text-[9px] border border-[#27AE60]/50 rounded animate-pulse shadow-[0_0_8px_rgba(39,174,96,0.3)]">
                        RECABADO
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

      {/* ENHANCED MODAL DIALOG FOR PROJECT DETAILS */}
      {selectedId && selectedRow && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div 
            className="absolute inset-0 bg-black/60 backdrop-blur-md transition-opacity"
            onClick={() => setSelectedId(null)}
          ></div>
          
          <div className="relative bg-gradient-to-b from-[#111111] to-[#0A0A0A] border border-[#333333] shadow-[0_0_50px_rgba(0,0,0,0.9),0_0_15px_rgba(255,176,0,0.15)] ring-1 ring-[#FFB000]/10 w-full max-w-3xl max-h-[85vh] flex flex-col font-mono rounded-lg overflow-hidden animate-in zoom-in-95 duration-200">
            
            {/* Modal Header */}
            <div className="h-14 border-b border-[#222222] flex items-center justify-between px-6 bg-[#000000]/40 shrink-0 backdrop-blur-lg">
              <div className="flex items-center gap-3">
                <span className="flex h-2 w-2 rounded-full bg-[#FFB000] shadow-[0_0_8px_#FFB000]"></span>
                <span className="text-[#FFFFFF] text-[13px] font-black tracking-widest uppercase truncate max-w-sm">
                  {selectedRow.id_proyecto} <span className="opacity-40">|</span> DETALLE
                </span>
              </div>
              <button 
                className="text-[#888888] hover:text-[#FFFFFF] text-[16px] font-black px-3 py-1 bg-[#1A1A1A] hover:bg-[#333333] border border-[#333333] rounded transition-colors" 
                onClick={() => setSelectedId(null)}
              >
                 ✕ 
              </button>
            </div>
            
            {/* Modal Body */}
            <div className="flex-1 overflow-y-auto scrollbar-tactical p-8 space-y-8">
                <div>
                    <h2 className="text-[#FFB000] font-black text-[18px] uppercase border-b border-[#333333] pb-2 mb-4 leading-tight shadow-sm text-shadow">
                      {selectedRow.promovente}
                    </h2>
                </div>

                <div className="space-y-6">
                    <div className="bg-[#151515] p-4 rounded-md border border-[#222222]">
                        <label className="text-[#00E5FF] font-black text-[10px] uppercase tracking-widest block mb-1 opacity-80">NOMBRE DEL PROYECTO</label>
                        <div className="text-[#FFFFFF] font-bold uppercase text-[14px] leading-tight">{selectedRow.proyecto}</div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div className="bg-[#151515] p-4 rounded-md border border-[#222222]">
                            <label className="text-[#00E5FF] font-black text-[10px] uppercase tracking-widest block mb-1 opacity-80">ESTADO</label>
                            <div className="text-[#FFFFFF] font-black uppercase text-[16px]">{selectedRow.estado}</div>
                        </div>
                        <div className="bg-[#151515] p-4 rounded-md border border-[#222222]">
                            <label className="text-[#00E5FF] font-black text-[10px] uppercase tracking-widest block mb-1 opacity-80">LOCALIDAD / MUNICIPIO</label>
                            <div className="text-[#FFFFFF] font-black uppercase text-[16px]">{selectedRow.municipio}</div>
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div className="bg-[#151515] p-4 rounded-md border border-[#222222]">
                            <label className="text-[#00E5FF] font-black text-[10px] uppercase tracking-widest block mb-1 opacity-80">SECTOR TÉCNICO</label>
                            <div className="text-[#FFFFFF] font-black uppercase">{selectedRow.sector}</div>
                        </div>
                        <div className="bg-[#151515] p-4 rounded-md border border-[#222222] flex flex-col items-center justify-center">
                            <label className="text-[#00E5FF] font-black text-[10px] uppercase tracking-widest block mb-1 opacity-80">CALIDAD DE INTELIGENCIA (GROUNDED)</label>
                            <div className="text-[#27AE60] font-black text-[16px] flex items-center gap-2">
                               {selectedRow.grounded && <span className="h-2 w-2 bg-[#27AE60] rounded-full shadow-[0_0_5px_#27AE60] animate-pulse"></span>}
                               {selectedRow.grounded ? "VERIFICADO" : "PENDIENTE"}
                            </div>
                        </div>
                    </div>

                    <div className="space-y-4 border-t border-[#222222] pt-6 mt-6 relative">
                        {/* Decorative HUD bracket */}
                        <div className="absolute top-0 left-0 w-4 h-4 border-t-2 border-l-2 border-[#FFB000]/50 -mt-[1px]"></div>
                        
                        <div>
                            <label className="text-[#FFB000] font-black text-[11px] uppercase tracking-widest block mb-2 flex items-center gap-2">
                                <span>⚡</span> INSIGHT GENERADO POR IA
                            </label>
                            <div className="text-[#DDDDDD] text-[13px] leading-relaxed font-normal bg-[#1A1A1A] p-4 rounded border-l-4 border-[#FFB000] shadow-inner">
                                {selectedRow.insight || "Detectando profundidad de impacto ambiental..."}
                            </div>
                        </div>

                        <div>
                            <label className="text-[#00E5FF] font-black text-[10px] uppercase tracking-widest block mb-2 mt-4 opacity-80">DESCRIPCIÓN ORIGINAL</label>
                            <div className="text-[#888888] text-[11px] leading-relaxed italic bg-[#0A0A0A] p-4 rounded border border-[#1A1A1A]">
                                {selectedRow.description || selectedRow.context?.slice(0, 500) + "..." || "Fragmento no disponible en la API."}
                            </div>
                        </div>
                    </div>

                    <div className="border-t border-[#222222] pt-6 relative">
                        <label className="text-[#00E5FF] font-black text-[10px] uppercase tracking-widest block mb-3 opacity-80">ENLACES DE REFERENCIA TÁCTICA</label>
                        <div className="grid grid-cols-2 gap-3">
                          {['Descargar MIA', 'Visor Geográfico', 'Documento GACETA', 'Expediente Oficial'].map((link, idx) => (
                            <button key={link} className="w-full text-center px-4 py-3 bg-[#111111] border border-[#333333] rounded hover:bg-[#FFB000] hover:text-black hover:border-[#FFB000] transition-all text-[#00E5FF] text-[11px] font-black flex items-center justify-center gap-2 group">
                              <span className="opacity-40 group-hover:text-black">→</span> {link.toUpperCase()}
                            </button>
                          ))}
                        </div>
                    </div>
                </div>

                {/* Modal Footer */}
                <div className="pt-4 pb-4 bg-[#0A0A0A] border-t border-[#111111] text-center shrink-0">
                    <span className="text-[10px] text-[#444444] uppercase font-black tracking-[0.3em] font-mono">ZOHAR_RECORD_ESTRAT_v2.2_SECURED || GACETA_2026</span>
                </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
