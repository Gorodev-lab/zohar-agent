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
        <div className="h-10 border-b border-[#222222] flex items-center px-8 bg-[#111111] shrink-0 font-mono">
          <span className="text-[#FFB000] text-[10px] mr-4 font-black">CMD&gt;</span>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="FILTRO: clave, municipio, promovente..."
            className="bg-transparent border-none text-[#FFFFFF] font-mono text-[10px] outline-none flex-1 placeholder:text-[#333333] uppercase tracking-widest"
          />
          <div className="text-[10px] text-[#FFB000] font-black select-none border-l border-[#222222] pl-4">
            {filteredData.length}/{data.length}
          </div>
        </div>

        {/* Dense Table Body */}
        <div className="flex-1 overflow-auto scrollbar-tactical bg-[#050505]">
          <table className="w-full text-left font-mono border-collapse min-w-[1200px]">
            <thead className="sticky top-0 z-20 bg-[#111111]">
              <tr className="border-b border-[#222222] text-[10px] text-[#666666] font-black uppercase">
                <th className="py-2 px-4 w-[140px] sticky left-0 bg-[#111111] z-30">CLAVE</th>
                <th className="py-2 px-4 w-[150px]">MODALIDAD</th>
                <th className="py-2 px-4 w-[200px]">PROMOVENTE</th>
                <th className="py-2 px-4 w-[250px]">PROYECTO</th>
                <th className="py-2 px-4 w-[180px]">UBICACION</th>
                <th className="py-2 px-4 w-[180px]">SECTOR</th>
                <th className="py-2 px-4 w-[130px]">FECHA</th>
                <th className="py-2 px-4 w-[60px]">AÑO</th>
                <th className="py-2 px-4 w-[100px]">ESTATUS</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#111111]">
              {filteredData.map((row) => (
                <tr
                  key={row.id_proyecto}
                  onClick={() => setSelectedId(row.id_proyecto)}
                  className={cn(
                    "cursor-pointer transition-none text-[10px]",
                    selectedId === row.id_proyecto ? "bg-[#FFB000] text-black" : "hover:bg-[#111111] text-[#AAAAAA]"
                  )}
                >
                  <td className={cn(
                      "py-2 px-4 font-bold sticky left-0 z-20",
                      selectedId === row.id_proyecto ? "bg-[#FFB000] text-black" : "bg-[#050505]"
                  )}>
                    {row.id_proyecto}
                  </td>
                  <td className="py-2 px-4 truncate max-w-[150px]">{row.modalidad || "MIA PARTICULAR"}</td>
                  <td className="py-2 px-4 truncate max-w-[200px]">{row.promovente}</td>
                  <td className="py-2 px-4 truncate max-w-[250px] uppercase">{row.proyecto}</td>
                  <td className="py-2 px-4 truncate max-w-[180px]">
                    {row.estado} {row.municipio}
                  </td>
                  <td className="py-2 px-4 truncate max-w-[180px] text-[#666666]">{row.sector}</td>
                  <td className="py-2 px-4 text-[#666666]">{row.fecha || 'Del 13/03/26 al 14/04/26'}</td>
                  <td className="py-2 px-4">
                    <span className={cn(
                        "px-1 py-0.5",
                        row.anio === 2026 && selectedId !== row.id_proyecto ? "bg-[#FFB000] text-black font-black" : ""
                    )}>{row.anio}</span>
                  </td>
                  <td className="py-2 px-4">
                    <span className={cn(
                        "font-black px-2 py-0.5 border",
                        selectedId === row.id_proyecto ? "border-black text-black" : "border-[#27AE60] text-[#27AE60]"
                    )}>
                        [ {row.grounded ? "OK" : ".." } ]
                    </span>
                  </td>
                </tr>
              ))}
              {loading && (
                  <tr>
                      <td colSpan={9} className="text-center py-40 animate-pulse text-[#FFB000] font-mono text-[11px] uppercase font-black">
                        QUERYING_ZOHAR_DATABASE_
                      </td>
                  </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* RIGHT: TACTICAL DETAIL PANEL (DETALLE) */}
      <aside className="w-[450px] flex flex-col bg-[#050505] shrink-0 overflow-hidden border-l border-[#222222]">
        <div className="h-10 border-b border-[#222222] flex items-center justify-between px-6 bg-[#111111] shrink-0 font-mono">
          <div className="flex items-center gap-2">
            <span className="text-[#FFB000] text-[12px] font-black">== DETALLE ==</span>
          </div>
          {selectedRow && (
            <button 
              className="text-[#666666] hover:text-[#FFB000] text-[11px] font-black transition-none" 
              onClick={() => setSelectedId(null)}
            >
              [X]
            </button>
          )}
        </div>
        
        <div className="flex-1 overflow-y-auto scrollbar-tactical p-6 space-y-6 font-mono">
          {!selectedRow ? (
            <div className="h-full flex items-center justify-center text-center opacity-20">
                <p className="text-[#666666] text-[10px] uppercase tracking-[0.4em] font-black border border-[#222222] px-4 py-2">STANDBY_DETALLE</p>
            </div>
          ) : (
            <div className="space-y-6 text-[11px]">
                <div>
                  <label className="text-[#FFB000] font-black block mb-1">CLAVE</label>
                  <div className="text-[#FFFFFF]">{selectedRow.id_proyecto}</div>
                </div>
                <div>
                  <label className="text-[#FFB000] font-black block mb-1">MODALIDAD</label>
                  <div className="text-[#AAAAAA] uppercase">{selectedRow.modalidad || "MIA REGIONAL.- MOD A; NO INCLUYE RIESGO"}</div>
                </div>
                <div>
                  <label className="text-[#FFB000] font-black block mb-1">PROMOVENTE</label>
                  <div className="text-[#FFFFFF] uppercase leading-tight">{selectedRow.promovente}</div>
                </div>
                <div>
                  <label className="text-[#FFB000] font-black block mb-1">PROYECTO</label>
                  <div className="text-[#AAAAAA] uppercase leading-tight">{selectedRow.proyecto}</div>
                </div>
                <div>
                  <label className="text-[#FFB000] font-black block mb-1">UBICACION</label>
                  <div className="text-[#FFFFFF] uppercase">{selectedRow.estado} {selectedRow.municipio}</div>
                </div>
                <div>
                  <label className="text-[#FFB000] font-black block mb-1">SECTOR</label>
                  <div className="text-[#AAAAAA] uppercase leading-tight">{selectedRow.sector}</div>
                </div>
                <div>
                  <label className="text-[#FFB000] font-black block mb-1">FECHA</label>
                  <div className="text-[#FFFFFF]">Del 13/03/26 al 14/04/26</div>
                </div>
                <div>
                  <label className="text-[#FFB000] font-black block mb-1">AÑO</label>
                  <div className="text-[#FFFFFF] font-black">{selectedRow.anio}</div>
                </div>
                <div>
                  <label className="text-[#FFB000] font-black block mb-1">ESTATUS</label>
                  <div className="text-[#FFFFFF] font-black uppercase">{selectedRow.estatus || "CONCLUIDO_2026"}</div>
                </div>

                <div className="pt-8 space-y-4">
                    <div className="text-[#666666] font-black">-- ENLACES --</div>
                    <div className="flex flex-col gap-2 text-[#27AE60] font-black">
                        <span className="hover:text-[#FFB000] cursor-pointer">→ MIA</span>
                        <span className="hover:text-[#FFB000] cursor-pointer">→ Visor Geográfico</span>
                        <span className="hover:text-[#FFB000] cursor-pointer">→ GACETA</span>
                        <span className="hover:text-[#FFB000] cursor-pointer">→ Expediente del Trámite</span>
                    </div>
                </div>
                
                <div className="h-8" />
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}
