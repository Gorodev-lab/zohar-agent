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

  const [sortConfig, setSortConfig] = useState<{ key: string, direction: 'asc' | 'desc' } | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const res = await fetch(`/api/data/${type}`);
        const json = await res.json();
        if (Array.isArray(json)) {
          // Filtro estricto: forzar retención ÚNICAMENTE de proyectos que cuenten con '2026' en algún campo (generalmente AÑO o F_INGRESO)
          const only2026 = json.filter(row => 
            Object.values(row).some(val => String(val).includes('2026'))
          );
          setData(only2026);
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

  const FACET_COLUMNS = ['estado', 'municipio', 'localidad', 'sector', 'estatus', 'modalidad'];

  const facetsToRender = useMemo(() => {
    if (!data.length) return {};
    const options: Record<string, string[]> = {};
    const keys = Object.keys(data[0]);
    
    keys.forEach(k => {
      if (FACET_COLUMNS.some(f => k.toLowerCase().includes(f))) {
        const uniqueVals = Array.from(new Set(data.map(r => r[k]))).filter(Boolean).map(String);
        if (uniqueVals.length > 0 && uniqueVals.length < 50) {
          options[k] = uniqueVals.sort();
        }
      }
    });
    return options;
  }, [data]);

  const [activeFacets, setActiveFacets] = useState<Record<string, string>>({});

  const filteredData = useMemo(() => {
    let result = sortedData;
    
    // Aplicar facetas estrictas (Dropdowns)
    Object.entries(activeFacets).forEach(([key, val]) => {
      if (val) {
        result = result.filter(row => String(row[key]) === val);
      }
    });

    // Aplicar búsqueda de texto residual
    const s = searchQuery.toLowerCase();
    if (s) {
      result = result.filter(row => 
        Object.values(row).some(val => 
          String(val).toLowerCase().includes(s)
        )
      );
    }
    return result;
  }, [sortedData, searchQuery, activeFacets]);

  const handleFacetChange = (key: string, val: string) => {
    setActiveFacets(prev => ({ ...prev, [key]: val }));
  };

  const handleSort = (key: string) => {
    let direction: 'asc' | 'desc' = 'asc';
    if (sortConfig && sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };

  return (
    <div className="flex flex-1 overflow-hidden bg-[#0A0A0A] font-mono">
      {/* LEFT: TABLE AREA */}
      <div className="flex-1 flex flex-col min-w-0 border-r border-[#222222]">
        {/* Search & Header Stats */}
        <div className="h-12 border-b border-[#222222] flex items-center px-4 md:px-8 bg-[#111111] shrink-0 overflow-x-auto scrollbar-tactical">
          <div className="flex items-center gap-3 mr-6 border-r border-[#222222] pr-6 h-full shrink-0">
              <span className="text-[#FFB000] text-[11px] font-black uppercase">{title}</span>
          </div>
          
          {/* FACET DROPDOWNS */}
          <div className="flex items-center gap-2 mr-6 shrink-0">
            {Object.entries(facetsToRender).map(([k, options]) => (
              <select 
                key={k}
                className="bg-[#1A1A1A] border border-[#333333] text-[#00E5FF] text-[9px] font-black uppercase outline-none px-2 py-1.5 appearance-none cursor-pointer hover:border-[#FFB000] transition-colors max-w-[150px] truncate"
                value={activeFacets[k] || ""}
                onChange={e => handleFacetChange(k, e.target.value)}
              >
                <option value="">{k.replace(/_/g, ' ')} [ALL]</option>
                {options.map(o => (
                  <option key={o} value={o}>{o}</option>
                ))}
              </select>
            ))}
          </div>

          <span className="text-[#FFB000] text-[10px] mr-3 font-black shrink-0">CMD&gt;</span>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={`FILTRO DE TEXTO: ${type.toUpperCase()}...`}
            className="bg-transparent border-none text-[#FFFFFF] font-mono text-[10px] outline-none min-w-[150px] flex-1 placeholder:text-[#333333] uppercase tracking-widest"
          />
          <div className="text-[10px] text-[#FFB000] font-black select-none border-l border-[#222222] pl-4 shrink-0">
            {filteredData.length}/{data.length} REGS_ACTIVOS
          </div>
        </div>

        {/* Dense Table Body - min-w-max stops column squishing */}
        <div className="flex-1 overflow-auto scrollbar-tactical bg-[#050505]">
          <table className="w-full text-left font-mono border-collapse min-w-max">
            <thead className="sticky top-0 z-20 bg-[#111111]">
              <tr className="border-b border-[#222222] text-[9px] text-[#666666] font-black uppercase tracking-tighter">
              {headers.map(h => (
                <th key={h} onClick={() => handleSort(h)} className="py-3 px-4 whitespace-nowrap min-w-[150px] border-r border-[#111111] bg-[#1a1a1a] cursor-pointer hover:text-[#00E5FF] transition-colors">
                  {h.replace(/_/g, ' ')} {sortConfig?.key === h && (sortConfig.direction === 'asc' ? '▲' : '▼')}
                </th>
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
                      "cursor-pointer transition-colors duration-200 text-[10px] border-l-2",
                      isSelected ? "bg-[#1A1810] text-[#FFB000] border-[#FFB000]" : "hover:bg-[#111111] text-[#AAAAAA] border-transparent"
                    )}
                  >
                    {headers.map(h => (
                    <td key={h} className={cn(
                      "py-2 px-4 truncate max-w-[300px]",
                      isSelected ? "text-white font-black bg-[#1A1810]" : "group-hover:text-[#FFFFFF]"
                    )} title={row[h] !== null && row[h] !== undefined ? String(row[h]) : ''}>
                      {row[h] !== null && row[h] !== undefined ? String(row[h]) : '---'}
                    </td>
                  ))}
                  </tr>
                );
              })}
              {loading && (
                  <tr>
                      <td colSpan={headers.length || 1} className="text-center py-40 animate-pulse text-[#FFB000] font-mono text-[11px] uppercase font-black">
                        QUERYING_ZOHAR_DATABASE_ESTRAT_
                      </td>
                  </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* MODAL DIALOG HUD FOR ROW DETAILS */}
      {selectedId !== null && filteredData[selectedId] && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div 
            className="absolute inset-0 bg-black/60 backdrop-blur-md transition-opacity"
            onClick={() => setSelectedId(null)}
          ></div>

          <div className="relative bg-[#0A0A0A] border border-[#222222] shadow-[0_0_50px_rgba(0,0,0,0.9)] ring-1 ring-[#FFB000]/20 w-full max-w-4xl max-h-[85vh] flex flex-col font-mono rounded-lg overflow-hidden animate-in zoom-in-95 duration-200">
            
            {/* HUD Header */}
            <div className="h-14 border-b border-[#222222] flex items-center justify-between px-6 bg-[#111111] shrink-0">
              <div className="flex items-center gap-3">
                <span className="flex h-2 w-2 rounded-full bg-[#FFB000] shadow-[0_0_8px_#FFB000] animate-pulse"></span>
                <span className="text-[#FFFFFF] text-[13px] font-black tracking-widest uppercase truncate max-w-sm">
                  {filteredData[selectedId]?.Clave || filteredData[selectedId]?.id_proyecto || 'EXPEDIENTE_ZOHAR'} <span className="opacity-40">|</span> DETALLE
                </span>
              </div>
              <button 
                className="text-[#888888] hover:text-[#FFFFFF] text-[16px] font-black px-3 py-1 bg-[#1A1A1A] hover:bg-[#333333] border border-[#333333] rounded transition-colors" 
                onClick={() => setSelectedId(null)}
              >
                 ✕ 
              </button>
            </div>
            
            {/* Record Data Fields */}
            <div className="flex-1 overflow-y-auto scrollbar-tactical p-8 bg-gradient-to-b from-[#111111] to-[#050505]">
              <div className="grid grid-cols-2 gap-6 text-[12px] leading-tight">
                {Object.entries(filteredData[selectedId]).map(([k, v]) => (
                  <div key={k} className="bg-[#151515] p-4 rounded-md border border-[#222222] shadow-sm transform transition duration-300 hover:border-[#FFB000]/50 hover:-translate-y-0.5">
                    <label className="text-[#00E5FF] font-black uppercase tracking-widest block mb-1 opacity-80 whitespace-nowrap overflow-hidden text-ellipsis text-[10px]">
                      {k.replace(/_/g, ' ')}
                    </label>
                    <div className="text-[#FFFFFF] font-bold uppercase whitespace-pre-wrap break-words">
                      {v !== null && v !== undefined ? String(v) : 'N/A'}
                    </div>
                  </div>
                ))}
              </div>
              
              {/* Tactical Actions */}
              <div className="pt-8 mt-6 border-t border-[#222222]">
                <label className="text-[#FFB000] font-black uppercase tracking-widest block mb-4 flex items-center gap-2 text-[11px]">
                  <span>⚡</span> ACCIONES TÁCTICAS VINCULADAS
                </label>
                <div className="grid grid-cols-2 gap-4">
                  <button className="w-full text-center px-4 py-3 bg-[#111111] border border-[#333333] rounded hover:bg-[#FFB000] hover:text-black transition-all text-[#00E5FF] text-[11px] font-black flex justify-center items-center gap-2 group">
                    <span className="opacity-40 group-hover:text-black text-lg leading-none">↓</span> <span className="pt-0.5">EXTRAER RESOLUTIVO PDF</span>
                  </button>
                  <button className="w-full text-center px-4 py-3 bg-[#111111] border border-[#333333] rounded hover:bg-[#FFB000] hover:text-black transition-all text-[#00E5FF] text-[11px] font-black flex justify-center items-center gap-2 group">
                    <span className="opacity-40 group-hover:text-black text-lg leading-none">↗</span> <span className="pt-0.5">VER TRAZO GEOESPACIAL</span>
                  </button>
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="pt-4 pb-4 bg-[#0A0A0A] border-t border-[#111111] text-center shrink-0">
                <span className="text-[10px] text-[#444444] uppercase font-black tracking-[0.3em] font-mono">ZOHAR_RECORD_ESTRAT_v2.2_SECURED || FILTRO: 2026_ACTIVO</span>
            </div>

          </div>
        </div>
      )}
    </div>
  );
}
