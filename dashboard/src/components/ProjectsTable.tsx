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
  insight?: string;
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
          // Refactorizado: Llamar a nuestra propia API interna de Next.js
          const res = await fetch('/api/projects');
          const projects = await res.json();
          if (Array.isArray(projects)) {
            setData(projects);
          }
      } catch (err) {
          console.error("Error fetching projects from internal API:", err);
      }
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
      {/* LEFT: TABLE CONTENT */}
      <div className="flex-1 flex flex-col min-w-0 border-r border-[#222222]">
        {/* Search Header */}
        <div className="h-14 border-b border-[#222222] flex items-center px-8 bg-[#111111]">
          <span className="text-[#FFB000] font-mono mr-4">&gt;</span>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="FILTER_COMMAND_INPUT..."
            className="bg-transparent border-none text-[#FFFFFF] font-mono text-[13px] outline-none flex-1 placeholder:text-[#444444] uppercase tracking-wider"
          />
          <div className="text-[12px] text-[#666666] font-mono whitespace-nowrap">
            RECORDS_FOUND: <span className="text-[#FFFFFF]">{filteredData.length}</span>
          </div>
        </div>

        {/* Table Body */}
        <div className="flex-1 overflow-auto scrollbar-tactical">
          <table className="w-full text-left font-mono">
            <thead className="sticky top-0 z-10 bg-[#111111]">
              <tr className="border-b border-[#222222]">
                <th className="w-[160px] text-[12px] font-bold py-4 px-6 text-[#666666]">ID_EXPEDIENTE</th>
                <th className="w-[80px] text-[12px] font-bold py-4 px-6 text-[#666666]">CYCLE</th>
                <th className="w-[220px] text-[12px] font-bold py-4 px-6 text-[#666666]">PROMOVENTE</th>
                <th className="text-[12px] font-bold py-4 px-6 text-[#666666]">DESCRIPTION</th>
                <th className="w-[140px] text-[12px] font-bold py-4 px-6 text-[#666666]">LOCATION</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#222222]">
              {filteredData.map((row) => (
                <tr
                  key={row.id_proyecto}
                  onClick={() => setSelectedId(row.id_proyecto)}
                  className={cn(
                    "cursor-pointer group transition-colors",
                    selectedId === row.id_proyecto ? "bg-[#111111]" : "hover:bg-[#050505]"
                  )}
                >
                  <td className={cn(
                      "py-4 px-6 text-[13px]",
                      selectedId === row.id_proyecto ? "text-[#FFB000]" : "text-[#AAAAAA]"
                  )}>{row.id_proyecto}</td>
                  <td className="py-4 px-6">
                    <span className={cn(
                        "px-2 py-0.5 text-[11px] font-bold",
                        row.anio === 2026 ? "bg-[#FFB000] text-black" : "bg-[#222222] text-[#AAAAAA]"
                    )}>
                        {row.anio}
                    </span>
                  </td>
                  <td className="py-4 px-6 truncate max-w-[220px] text-[13px] text-[#AAAAAA]">{row.promovente}</td>
                  <td className="py-4 px-6 whitespace-normal leading-tight">
                    <div className="line-clamp-2 text-[#FFFFFF] group-hover:text-[#FFB000] transition-colors text-[13px] uppercase tracking-tight">
                        {row.proyecto}
                    </div>
                  </td>
                  <td className="py-4 px-6">
                    <div className="text-[12px] uppercase text-[#FFFFFF]">{row.municipio}</div>
                    <div className="text-[10px] text-[#666666] uppercase">{row.estado}</div>
                  </td>
                </tr>
              ))}
              {loading && (
                  <tr>
                      <td colSpan={5} className="text-center py-20 animate-pulse text-[#FFB000] font-mono text-[12px] tracking-[0.3em]">
                        DATA_BUFFER_ACCESSING_SEMARNAT_RECORDS...
                      </td>
                  </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* RIGHT: DETAIL PANEL (Esoteria institutional style) */}
      <aside className="w-[450px] flex flex-col bg-[#111111] shrink-0 overflow-hidden">
        <div className="h-14 border-b border-[#222222] flex items-center justify-between px-8 bg-[#111111] shrink-0 font-mono">
          <span className="text-[12px] font-bold text-[#FFFFFF] uppercase tracking-[0.2em]">Intel_Module_v1.0</span>
          {selectedRow && (
            <button 
              className="text-[#666666] hover:text-[#FFB000] transition-colors text-[12px] font-bold" 
              onClick={() => setSelectedId(null)}
            >
              [TERMINATE]
            </button>
          )}
        </div>
        
        <div className="flex-1 overflow-y-auto scrollbar-tactical p-10 space-y-10 font-mono">
          {!selectedRow ? (
            <div className="h-full flex flex-col items-center justify-center text-center">
                <div className="text-[#1A1A1A] text-[64px] font-black mb-6 select-none leading-none tracking-tighter">ZOHAR</div>
                <p className="text-[#444444] text-[12px] uppercase tracking-[0.4em]">Initialize_Record_Selection_By_Expediente_ID_</p>
            </div>
          ) : (
            <>
              <section className="space-y-4">
                <div className="text-[13px] text-[#FFB000] font-bold tracking-[0.1em]">
                  &gt; DIMENSION_I // IDENTITY_AND_CLASSIFICATION
                </div>
                <div>
                  <label className="text-[11px] text-[#666666] uppercase block mb-1">Project Name</label>
                  <h3 className="text-[20px] font-bold text-[#FFFFFF] leading-snug tracking-tight">{selectedRow.proyecto}</h3>
                </div>
                <div className="flex gap-3">
                    <span className="px-3 py-1 bg-[#FFB000] text-black text-[10px] font-bold tracking-[0.2em]">MISSION_ACTIVE</span>
                    <span className="px-3 py-1 border border-[#222222] text-[#AAAAAA] text-[10px] font-bold uppercase tracking-[0.1em]">{selectedRow.sector}</span>
                </div>
              </section>

              <div className="h-px bg-[#222222]" />

              <div className="grid grid-cols-2 gap-y-8 gap-x-6">
                <div>
                  <label className="text-[11px] text-[#666666] uppercase block mb-1">Record_ID</label>
                  <div className="text-[15px] font-bold text-[#FFB000] tracking-wider">{selectedRow.id_proyecto}</div>
                </div>
                <div>
                  <label className="text-[11px] text-[#666666] uppercase block mb-1">Cycle_Priority</label>
                  <div className="text-[15px] font-bold text-[#FFFFFF]">{selectedRow.anio}</div>
                </div>
                <div className="col-span-2">
                  <label className="text-[11px] text-[#666666] uppercase block mb-1">Promovente_Legal_Entity</label>
                  <div className="text-[14px] text-[#FFFFFF] leading-tight">{selectedRow.promovente}</div>
                </div>
                <div>
                  <label className="text-[11px] text-[#666666] uppercase block mb-1">Subdivision_State</label>
                  <div className="text-[14px] text-[#FFFFFF]">{selectedRow.estado}</div>
                </div>
                <div>
                  <label className="text-[11px] text-[#666666] uppercase block mb-1">Regional_Municipality</label>
                  <div className="text-[14px] text-[#FFFFFF]">{selectedRow.municipio}</div>
                </div>
              </div>

              <div className="h-px bg-[#222222]" />

              <section className="space-y-4">
                <div className="text-[13px] text-[#FFB000] font-bold tracking-[0.1em]">
                  &gt; DIMENSION_II // STRATEGIC_INSIGHT_OVERVIEW
                </div>
                <div className="text-[15px] text-[#AAAAAA] leading-relaxed italic border-l-2 border-[#222222] pl-6">
                  "{selectedRow.insight || "Telemetric data analysis currently pending review by human auditor. Grounded extraction requested."}"
                </div>
              </section>

              <div className="pt-12">
                <button 
                  className="w-full py-5 bg-[#C0392B] text-white font-bold uppercase tracking-[0.3em] text-[12px] hover:bg-[#A93226] transition-colors flex items-center justify-center gap-3"
                >
                  <span>&gt; ACCESS_EXTENDED_INTEL_REPORTS</span>
                </button>
              </div>
            </>
          )}
        </div>
      </aside>
    </div>
  );
}
