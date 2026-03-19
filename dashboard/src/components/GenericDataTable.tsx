'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface GenericDataTableProps {
  type: 'regulatory' | 'financial' | 'air_quality';
  title: string;
}

export default function GenericDataTable({ type, title }: GenericDataTableProps) {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedId, setSelectedId] = useState<number | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const res = await fetch(`/api/data/${type}`);
        const json = await res.json();
        if (Array.isArray(json)) {
          setData(json);
        }
      } catch (err) {
        console.error(`Error fetching ${type} data:`, err);
      }
      setLoading(false);
    };

    fetchData();
    setSelectedId(null);
  }, [type]);

  const headers = useMemo(() => {
    if (data.length === 0) return [];
    return Object.keys(data[0]);
  }, [data]);

  const filteredData = useMemo(() => {
    const s = searchQuery.toLowerCase();
    if (!s) return data;
    return data.filter(row => 
      Object.values(row).some(val => 
        String(val).toLowerCase().includes(s)
      )
    );
  }, [data, searchQuery]);

  return (
    <div className="flex flex-1 overflow-hidden bg-[#0A0A0A] font-mono">
      {/* LEFT: TABLE AREA */}
      <div className="flex-1 flex flex-col min-w-0 border-r border-[#222222]">
        {/* Search & Header Stats */}
        <div className="h-10 border-b border-[#222222] flex items-center px-8 bg-[#111111] shrink-0">
          <div className="flex items-center gap-3 mr-8 border-r border-[#222222] pr-8 h-full">
              <span className="text-[#FFB000] text-[11px] font-black uppercase">{title}</span>
          </div>
          <span className="text-[#FFB000] text-[10px] mr-4 font-black">CMD&gt;</span>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={`FILTRO: ${type.toUpperCase()}...`}
            className="bg-transparent border-none text-[#FFFFFF] font-mono text-[10px] outline-none flex-1 placeholder:text-[#333333] uppercase tracking-widest"
          />
          <div className="text-[10px] text-[#FFB000] font-black select-none border-l border-[#222222] pl-4">
            {filteredData.length}/{data.length} REGS CAPTURADOS
          </div>
        </div>

        {/* Dense Table Body */}
        <div className="flex-1 overflow-auto scrollbar-tactical bg-[#050505]">
          <table className="w-full text-left font-mono border-collapse">
            <thead className="sticky top-0 z-20 bg-[#111111]">
              <tr className="border-b border-[#222222] text-[10px] text-[#666666] font-black uppercase">
                {headers.map(h => (
                  <th key={h} className="py-2 px-4 whitespace-nowrap">{h.replace(/_/g, ' ')}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[#111111]">
              {filteredData.map((row, i) => {
                const isSelected = selectedId === i;
                return (
                  <tr 
                    key={i} 
                    onClick={() => setSelectedId(isSelected ? null : i)}
                    className={cn(
                      "cursor-pointer transition-none group text-[10px] border-l-2",
                      isSelected ? "bg-[#FFB000] text-black border-black" : "hover:bg-[#111111] text-[#AAAAAA] border-transparent"
                    )}
                  >
                    {headers.map(h => (
                      <td key={h} className={cn(
                        "py-2 px-4 truncate max-w-[300px]",
                        isSelected ? "text-black font-bold" : "group-hover:text-[#FFB000]"
                      )}>
                        {row[h] !== null && row[h] !== undefined ? String(row[h]) : '---'}
                      </td>
                    ))}
                  </tr>
                );
              })}
              {loading && (
                  <tr>
                      <td colSpan={headers.length || 1} className="text-center py-40 animate-pulse text-[#FFB000] font-mono text-[11px] uppercase font-black">
                        QUERYING_ZOHAR_DATABASE_
                      </td>
                  </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* RIGHT: TACTICAL DETAIL PANEL (MATCHING AGENT CONSOLE) */}
      <aside className={cn(
        "bg-[#050505] shrink-0 overflow-hidden border-l border-[#222222] font-mono transition-all duration-300 flex flex-col",
        selectedId !== null ? "w-[400px]" : "w-0 border-none"
      )}>
        <div className="h-10 border-b border-[#222222] flex items-center justify-between px-6 bg-[#111111] shrink-0">
          <span className="text-[#FFB000] text-[12px] font-black tracking-widest uppercase italic">== DETALLE ==</span>
          <button 
            className="text-[#666666] hover:text-[#FFFFFF] text-[11px] font-black" 
            onClick={() => setSelectedId(null)}
          >
            [X]
          </button>
        </div>
        
        <div className="flex-1 overflow-y-auto scrollbar-tactical p-6">
          {selectedId !== null && filteredData[selectedId] && (
            <div className="space-y-4 text-[11px] leading-tight animate-in slide-in-from-right duration-300">
              {Object.entries(filteredData[selectedId]).map(([k, v]) => (
                <div key={k} className="border-b border-[#111111] pb-2">
                  <label className="text-[#00E5FF] font-black uppercase tracking-widest block mb-0.5 whitespace-nowrap overflow-hidden text-ellipsis">
                    {k.replace(/_/g, ' ')}
                  </label>
                  <div className="text-[#FFB000] font-bold uppercase whitespace-pre-wrap break-words">
                    {v !== null && v !== undefined ? String(v) : 'N/A'}
                  </div>
                </div>
              ))}
              
              <div className="pt-4 space-y-2">
                <label className="text-[#00E5FF] font-black uppercase tracking-widest block mb-1">ACCIONES</label>
                <button className="w-full text-left p-2 bg-[#111111] text-[#00E5FF] hover:bg-[#FFB000] hover:text-black transition-all text-[9px] font-black">→ DESCARGAR PDF</button>
                <button className="w-full text-left p-2 bg-[#111111] text-[#00E5FF] hover:bg-[#FFB000] hover:text-black transition-all text-[9px] font-black">→ VER EN MAPA</button>
              </div>
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}
