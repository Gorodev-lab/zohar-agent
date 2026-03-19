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
    <div className="flex flex-1 flex-col min-w-0 bg-[#0A0A0A] font-mono">
      {/* Search & Header Stats */}
      <div className="h-10 border-b border-[#222222] flex items-center px-8 bg-[#111111] shrink-0 font-mono">
        <div className="flex items-center gap-3 mr-8 border-r border-[#222222] pr-8 h-full">
            <span className="text-[#FFB000] text-[11px] font-black uppercase tracking-tight">{title}</span>
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
          {filteredData.length}/{data.length}
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
            {filteredData.map((row, i) => (
              <tr key={i} className="hover:bg-[#111111] transition-none group text-[10px]">
                {headers.map(h => (
                  <td key={h} className="py-2 px-4 text-[#AAAAAA] truncate max-w-[300px] group-hover:text-[#FFB000]">
                    {row[h] !== null && row[h] !== undefined ? String(row[h]) : '---'}
                  </td>
                ))}
              </tr>
            ))}
            {loading && (
                <tr>
                    <td colSpan={headers.length || 1} className="text-center py-40 animate-pulse text-[#FFB000] font-mono text-[11px] uppercase font-black">
                      QUERYING_ZOHAR_DATABASE_
                    </td>
                </tr>
            )}
            {!loading && data.length === 0 && (
                <tr>
                    <td colSpan={headers.length || 1} className="text-center py-40 text-[#444444] font-mono text-[10px] uppercase tracking-widest font-black">
                      NO_RECORDS_FOUND_IN_DATALAKE
                    </td>
                </tr>
            )}
          </tbody>
        </table>
      </div>
      
      <footer className="h-8 border-t border-[#222222] bg-[#0A0A0A] flex items-center px-8 justify-between">
          <div className="text-[9px] text-[#333333] uppercase font-black tracking-widest">
              Source: {type === 'regulatory' ? 'ordenamientos_ecologicos_expedidos.csv' : 'ingresos_2024.csv'} // Sync_OK
          </div>
          <div className="text-[9px] text-[#333333] uppercase font-black tracking-widest">
              ZOHAR_SYSTEMS_DATA_ACCESS_v1.0
          </div>
      </footer>
    </div>
  );
}
