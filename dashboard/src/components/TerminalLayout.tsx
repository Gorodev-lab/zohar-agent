'use client';

import React, { useState, useEffect } from 'react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import LogTerminal from './LogTerminal';
import ProjectsTable from './ProjectsTable';
import GenericDataTable from './GenericDataTable';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export default function TerminalLayout() {
  const [data, setData] = useState<any>(null);
  const [activeTab, setActiveTab] = useState('analysis');
  
  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch('/api/status');
        const s = await res.json();
        setData(s);
      } catch (err) {}
    };

    fetchData();
    const timer = setInterval(fetchData, 4000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="h-screen w-screen flex flex-col bg-[#0A0A0A] text-[#FFFFFF] overflow-hidden selection:bg-[#FFB000] selection:text-black font-mono">
      {/* HEADER (Advanced Tactical Style) */}
      <header className="h-[64px] border-b border-[#222222] flex items-center justify-between px-8 bg-[#111111] shrink-0">
        <div className="flex items-center gap-12 h-full">
          <div className="font-bold text-[14px] font-mono flex items-center h-full mr-4">
            <span className="text-[#FFB000] mr-2 text-[18px]">▲</span>
            <span className="text-[#FFB000] mr-2">ZOHAR //</span>
            <span className="tracking-tight uppercase bg-[#FFB000] text-black px-2 py-0.5 font-black">ESTRATÉGICO_2026</span>
          </div>
          <span className="text-[#666666] font-mono text-[12px] hidden xl:block tracking-[0.2em] border-l border-[#222222] pl-8">
            SEMARNAT_MONITOR_v2.1
          </span>
          
          <nav className="flex items-center gap-2 h-full ml-4">
            {[
              { id: 'analysis', label: '[ ANÁLISIS_2026 ]' },
              { id: 'projects', label: '[ PROYECTOS ]' },
              { id: 'regulatory', label: '[ ORD_ECOLÓGICO ]' },
              { id: 'air_quality', label: '[ CALIDAD_AIRE ]' },
              { id: 'map', label: '[ MAPA ↗ ]', link: '/aire' }
            ].map(tab => (
              tab.link ? (
                <a 
                  key={tab.id} href={tab.link} target="_blank" 
                  className="px-4 text-[11px] font-black text-[#FFB000] hover:bg-[#FFB000] hover:text-black transition-all flex items-center h-10 border border-[#222222] bg-[#0A0A0A]"
                >
                  {tab.label}
                </a>
              ) : (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    "px-4 text-[11px] font-black transition-all flex items-center h-10 border border-[#222222] tracking-tighter whitespace-nowrap",
                    activeTab === tab.id ? "bg-[#FFB000] text-black" : "bg-[#0A0A0A] text-[#666666] hover:border-[#FFB000]"
                  )}
                >
                  {tab.label}
                </button>
              )
            ))}
          </nav>
        </div>

        <div className="flex items-center gap-6 font-mono">
            {/* AGENT INDICATORS */}
            <div className="flex items-center gap-4 border-r border-[#222222] pr-8 mr-4 h-10">
                <div className="flex items-center gap-2">
                    <span className={cn("w-2 h-2", data?.llama_ok ? "bg-[#27AE60]" : "bg-[#C0392B]")} />
                    <span className="text-[10px] text-[#666666] font-bold">[ LLM ]</span>
                </div>
                <div className="flex items-center gap-2">
                    <span className={cn("w-2 h-2", data?.agent_running ? "bg-[#27AE60]" : "bg-[#C0392B]")} />
                    <span className="text-[10px] text-[#666666] font-bold">[ AGT ]</span>
                </div>
            </div>

            {/* SYSTEM METRICS */}
            <div className="flex items-center gap-6 text-[11px]">
                <div className="flex items-center gap-2">
                    <span className="text-[#666666]">CPU:</span>
                    <span className="text-[#FFB000] font-black">{data?.cpu_temp || '0.0°C'}</span>
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-[#666666]">UP:</span>
                    <span className="text-[#FFB000] font-black">{data?.uptime || '00:00:00'}</span>
                </div>
                <div className="text-[#FFB000] font-bold border-l border-[#222222] pl-6 uppercase tracking-widest text-[10px]">
                  [EN]
                </div>
            </div>
        </div>
      </header>

      {/* MID: VIEWPORT */}
      <main className="flex-1 flex overflow-hidden min-h-0 relative">
        {activeTab === 'analysis' && <ProjectsTable />}
        {activeTab === 'projects' && <GenericDataTable type="financial" title="PROYECTOS_ACTIVOS" />}
        {activeTab === 'regulatory' && <GenericDataTable type="regulatory" title="ORD_ECOLÓGICO_INTEL" />}
        {activeTab === 'air_quality' && <GenericDataTable type="air_quality" title="CALIDAD_AIRE_INTEL" />}
      </main>

      {/* BOTTOM: TELEMETRY TERMINAL */}
      <LogTerminal />

      {/* FOOTER: SYSTEM STATUS BAR */}
      <footer className="h-[32px] border-t border-[#222222] flex items-center justify-between px-8 bg-[#050505] shrink-0 font-mono">
        <div className="text-[10px] text-[#666666] flex items-center gap-8">
            <div className="flex items-center gap-2">
                <span className="uppercase text-[#FFB000] font-bold">ZOHAR_CORE: LINK_ACTIVE</span>
            </div>
            {data?.agent_state?.action && data.agent_state.action !== 'ESPERA' && (
                <span className="text-[#FFB000]">
                    &gt; EXECUTING_TASK: {data.agent_state.action} // TARGET: {data.agent_state.target}
                </span>
            )}
        </div>
        <div className="text-[10px] font-bold flex gap-6 text-[#666666] uppercase">
            <span>[F5:RESTART]</span>
            <span>[F6:STOP]</span>
            <span>[F7:RETRY]</span>
            <div className="flex items-center gap-2 ml-10">
                <span className="text-[#444444]">23:25:27</span>
                <span className="text-[#444444]">(C)2026 ZOHAR_INTEL</span>
            </div>
        </div>
      </footer>
    </div>
  );
}
