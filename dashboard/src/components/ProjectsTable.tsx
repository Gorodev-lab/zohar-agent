'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface Project {
  id_proyecto: string;
  anio: number;
  promovente: string;
  proyecto: string;
  estado: string;
  municipio: string;
  sector: string;
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
    <div className="flex flex-1 overflow-hidden h-full bg-[#0A0A0A]">
      {/* LEFT: TACTICAL DATA GRID */}
      <div className="flex-1 flex flex-col min-w-0 border-r border-[#222222]">
        {/* Search & Header Stats */}
        <div className="h-14 border-b border-[#222222] flex items-center px-8 bg-[#111111] shrink-0">
          <span className="text-[#FFB000] font-mono mr-4 tracking-tighter">CMD&gt;</span>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="FILTER_COMMAND: clave, municipio, promovente..."
            className="bg-transparent border-none text-[#FFFFFF] font-mono text-[11px] outline-none flex-1 placeholder:text-[#333333] uppercase tracking-widest"
          />
          <div className="text-[11px] text-[#222222] font-mono font-black select-none mr-4">
            ZOHAR_INTEL_SYSTEM_v2.1
          </div>
          <div className="text-[12px] font-mono border border-[#333333] px-3 py-1 bg-black">
            <span className="text-[#FFB000]">{filteredData.length}</span>
            <span className="text-[#333333] ml-1">/ {data.length}</span>
          </div>
        </div>

        {/* Dense Table Body */}
        <div className="flex-1 overflow-auto scrollbar-tactical bg-[#050505]">
          <table className="w-full text-left font-mono border-collapse min-w-[1200px]">
            <thead className="sticky top-0 z-20 bg-[#111111]">
              <tr className="border-b-2 border-[#222222] text-[10px] text-[#666666] font-black uppercase tracking-tighter">
                <th className="py-3 px-4 w-[140px] sticky left-0 bg-[#111111] z-30">ID PROYECTO</th>
                <th className="py-3 px-2 w-[50px]">ANIO</th>
                <th className="py-3 px-4 w-[200px]">PROMOVENTE</th>
                <th className="py-3 px-4 w-[250px]">ESTADO / MUNICIPIO</th>
                <th className="py-3 px-4 w-[100px]">SECTOR</th>
                <th className="py-3 px-4 w-[80px]">GROUNDED</th>
                <th className="py-3 px-4 w-[80px]">AUDIT</th>
                <th className="py-3 px-4 w-[70px]">CONF%</th>
                <th className="py-3 px-4 w-[120px]">FECHA CREATED</th>
                <th className="py-3 px-4">INSIGHT_PREVIEW</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1A1A1A]">
              {filteredData.map((row) => (
                <tr
                  key={row.id_proyecto}
                  onClick={() => setSelectedId(row.id_proyecto)}
                  className={cn(
                    "cursor-pointer group transition-none",
                    selectedId === row.id_proyecto ? "bg-[#111111]" : "hover:bg-[#070707]"
                  )}
                >
                  <td className={cn(
                      "py-3 px-4 text-[11px] font-bold sticky left-0 z-20 transition-none",
                      selectedId === row.id_proyecto ? "bg-[#111111] text-[#FFB000]" : "bg-[#050505] text-[#AAAAAA] group-hover:bg-[#070707]"
                  )}>
                    {row.id_proyecto}
                  </td>
                  <td className="py-3 px-2 text-[10px]">
                    <span className={cn(
                        "px-1.5 py-0.5",
                        row.anio === 2026 ? "bg-[#FFB000] text-black font-bold" : "text-[#444444]"
                    )}>{row.anio}</span>
                  </td>
                  <td className="py-3 px-4 text-[11px] text-[#AAAAAA] truncate max-w-[200px]">{row.promovente}</td>
                  <td className="py-3 px-4 text-[10px] uppercase">
                    <span className="text-[#AAAAAA]">{row.estado}</span>
                    <span className="text-[#444444] mx-1">/</span>
                    <span className="text-[#666666]">{row.municipio}</span>
                  </td>
                  <td className="py-3 px-4 text-[10px] text-[#666666] truncate max-w-[100px]">{row.sector}</td>
                  <td className="py-3 px-4">
                    <span className={cn(
                        "text-[10px] font-black px-2 py-0.5 border select-none",
                        row.grounded ? "border-[#27AE60] text-[#27AE60]" : "border-[#C0392B] text-[#C0392B] opacity-40"
                    )}>
                        {row.grounded ? "[ OK ]" : "[ -- ]"}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <span className={cn(
                        "text-[10px] font-black px-2 py-0.5 border select-none",
                        row.audit_status === "VERIFIED" ? "border-[#27AE60] text-[#27AE60]" : "border-[#FFB000] text-[#FFB000]"
                    )}>
                        [{row.audit_status === "VERIFIED" ? ".." : ".."}]
                    </span>
                  </td>
                  <td className="py-3 px-4 text-[11px] font-bold text-[#FFFFFF]">
                    {row.confidence}%
                  </td>
                  <td className="py-3 px-4 text-[10px] text-[#444444]">
                    {row.created_at?.slice(0, 10)}
                  </td>
                  <td className="py-3 px-4 text-[11px] text-[#888888] truncate italic">
                    {row.insight}
                  </td>
                </tr>
              ))}
              {loading && (
                  <tr>
                      <td colSpan={10} className="text-center py-40 animate-pulse text-[#FFB000] font-mono text-[12px] tracking-[0.5em] uppercase font-black">
                        INITIALIZING_DATA_QUERY_ENGINE_
                      </td>
                  </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* RIGHT: TACTICAL DETAIL PANEL */}
      <aside className="w-[500px] flex flex-col bg-[#111111] shrink-0 overflow-hidden border-l border-[#222222]">
        <div className="h-14 border-b border-[#222222] flex items-center justify-between px-8 bg-[#111111] shrink-0 font-mono">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 bg-[#FFB000] animate-pulse" />
            <span className="text-[12px] font-bold text-[#FFFFFF] uppercase tracking-[0.3em]">ANALYSIS_TERMINAL</span>
          </div>
          {selectedRow && (
            <button 
              className="text-[#444444] hover:text-[#FFB000] transition-colors text-[11px] font-black" 
              onClick={() => setSelectedId(null)}
            >
              [CLOSE_WINDOW]
            </button>
          )}
        </div>
        
        <div className="flex-1 overflow-y-auto scrollbar-tactical p-12 space-y-12 font-mono scroll-smooth">
          {!selectedRow ? (
            <div className="h-full flex flex-col items-center justify-center text-center opacity-10 grayscale">
                <div className="text-[#AAAAAA] text-[120px] font-black leading-none tracking-tighter select-none">ZHR</div>
                <p className="text-[#AAAAAA] text-[11px] uppercase tracking-[0.8em] font-bold mt-4">STANDBY_MODE</p>
            </div>
          ) : (
            <>
              {/* Header Info */}
              <section className="space-y-6">
                <div className="text-[12px] text-[#FFB000] font-black tracking-[0.2em] border-b border-[#222222] pb-2">
                  == SECTION_I: IDENTITY_AND_STATUS ==
                </div>
                <div>
                  <label className="text-[10px] text-[#444444] uppercase block mb-1 font-black">Full Project Name</label>
                  <h3 className="text-[22px] font-black text-[#FFFFFF] leading-[1.1] tracking-tight uppercase">{selectedRow.proyecto}</h3>
                </div>
                <div className="flex flex-wrap gap-4 pt-2">
                    <div className="px-4 py-1.5 bg-[#FFB000] text-black text-[11px] font-black tracking-widest border border-transparent">
                        ID: {selectedRow.id_proyecto}
                    </div>
                    <div className="px-4 py-1.5 border border-[#27AE60] text-[#27AE60] text-[11px] font-black tracking-widest">
                        {selectedRow.grounded ? "GROUNDED_OK" : "N/A_GROUNDING"}
                    </div>
                    <div className="px-4 py-1.5 border border-[#444444] text-[#AAAAAA] text-[11px] font-black tracking-widest uppercase">
                        {selectedRow.sector}
                    </div>
                </div>
              </section>

              {/* Data Grid */}
              <section className="grid grid-cols-2 gap-x-12 gap-y-10">
                <div className="col-span-2">
                    <label className="text-[10px] text-[#444444] uppercase block mb-1 font-black">Promovente_Entity</label>
                    <div className="text-[15px] text-[#FFFFFF] font-bold border-b border-[#222222] pb-2">{selectedRow.promovente}</div>
                </div>
                <div>
                    <label className="text-[10px] text-[#444444] uppercase block mb-1 font-black">Audit_Confidence</label>
                    <div className="text-[20px] text-[#FFB000] font-black">{selectedRow.confidence}%</div>
                </div>
                <div>
                    <label className="text-[10px] text-[#444444] uppercase block mb-1 font-black">Cycle_Priority</label>
                    <div className="text-[20px] text-[#FFFFFF] font-black">{selectedRow.anio}</div>
                </div>
                <div>
                    <label className="text-[10px] text-[#444444] uppercase block mb-1 font-black">State_Region</label>
                    <div className="text-[14px] text-[#FFFFFF] font-bold uppercase">{selectedRow.estado}</div>
                </div>
                <div>
                    <label className="text-[10px] text-[#444444] uppercase block mb-1 font-black">Municipality_Site</label>
                    <div className="text-[14px] text-[#FFFFFF] font-bold uppercase">{selectedRow.municipio}</div>
                </div>
              </section>

              {/* Advanced Insights */}
              <section className="space-y-6 pt-8">
                <div className="text-[12px] text-[#FFB000] font-black tracking-[0.2em] border-b border-[#222222] pb-2">
                  == SECTION_II: STRATEGIC_INTELLIGENCE ==
                </div>
                <div className="space-y-8">
                    <div>
                        <label className="text-[10px] text-[#27AE60] uppercase block mb-2 font-black tracking-widest">&gt; DIMENSION_I: ANALYTICAL_INSIGHT</label>
                        <div className="text-[15px] text-[#AAAAAA] leading-relaxed border-l-4 border-[#222222] pl-6 py-2 bg-[#0A0A0A]">
                            {selectedRow.insight || "No data extracted."}
                        </div>
                    </div>
                    <div>
                        <label className="text-[10px] text-[#27AE60] uppercase block mb-2 font-black tracking-widest">&gt; DIMENSION_II: LOGICAL_REASONING</label>
                        <div className="text-[13px] text-[#666666] leading-relaxed border-l-4 border-[#222222] pl-6 py-2 italic">
                            {selectedRow.reasoning || "Agent reasoning trace unavailable."}
                        </div>
                    </div>
                    <div>
                        <label className="text-[10px] text-[#27AE60] uppercase block mb-2 font-black tracking-widest">&gt; DIMENSION_III: EVIDENCE_SOURCES</label>
                        <div className="text-[12px] text-[#AAAAAA] font-mono space-y-2">
                            {selectedRow.sources && selectedRow.sources.length > 0 ? (
                                selectedRow.sources.map((src: any, i: number) => {
                                    const label = typeof src === 'string' ? src : (src.title || src.uri || src.url || 'SOURCE_REF');
                                    return (
                                        <div key={i} className="truncate text-[#444444] hover:text-[#FFB000] transition-colors cursor-pointer">
                                            [{i+1}] {label}
                                        </div>
                                    );
                                })
                            ) : (
                                <div className="text-[#333333]">NO_EXTERNAL_SOURCES_LINKED</div>
                            )}
                        </div>
                    </div>
                </div>
              </section>

              <div className="h-12" />

              {/* Action */}
              <div className="sticky bottom-4 z-10 pt-8">
                <button 
                  className="w-full py-6 bg-[#C0392B] text-white font-black uppercase tracking-[0.5em] text-[12px] hover:bg-[#A93226] transition-all border-2 border-transparent active:scale-95 flex items-center justify-center gap-4"
                >
                  <span className="animate-pulse">☢</span>
                  <span>OPEN_EXTENDED_INTEL_FILE_v1.0</span>
                </button>
                <div className="text-center mt-4 text-[9px] text-[#333333] uppercase font-black tracking-widest">
                    Authorized Personnel Only // Access is Logged
                </div>
              </div>
            </>
          )}
        </div>
      </aside>
    </div>
  );
}
