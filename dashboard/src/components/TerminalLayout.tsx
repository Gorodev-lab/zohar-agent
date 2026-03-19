'use client';

import React, { useState, useEffect } from 'react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import LogTerminal from './LogTerminal';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export default function TerminalLayout({ children }: { children: React.ReactNode }) {
  const [data, setData] = useState<any>(null);
  const [activeTab, setActiveTab] = useState('projects');
  
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
    <div className="h-screen w-screen flex flex-col bg-[#0A0A0A] text-[#FFFFFF] overflow-hidden selection:bg-[#FFB000] selection:text-black">
      {/* HEADER (Advanced Tactical Style) */}
      <header className="h-[64px] border-b border-[#222222] flex items-center justify-between px-8 bg-[#111111] shrink-0">
        <div className="flex items-center gap-12 h-full">
          <div className="font-bold text-[14px] font-mono flex items-center h-full mr-4">
            <span className="text-[#FFB000] mr-2">ZOHAR //</span>
            <span className="tracking-tight uppercase bg-[#FFB000] text-black px-2 py-0.5 font-black">ESTRATÉGICO_2026</span>
          </div>
          <span className="text-[#666666] font-mono text-[12px] hidden md:block tracking-[0.2em] border-l border-[#222222] pl-8">
            SEMARNAT_MONITOR_v2.1
          </span>
          
          <nav className="flex items-center gap-2 h-full ml-4">
            {[
              { id: 'projects', label: '[ ANÁLISIS_2026 ]' },
              { id: 'map', label: '[ MAPA ↗ ]', link: '/aire' }
            ].map(tab => (
              tab.link ? (
                <a 
                  key={tab.id} href={tab.link} target="_blank" 
                  className="px-4 text-[11px] font-bold text-[#FFB000] hover:bg-[#FFB000] hover:text-black transition-all flex items-center h-10 border border-[#222222] bg-[#0A0A0A]"
                >
                  {tab.label}
                </a>
              ) : (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    "px-4 text-[11px] font-bold transition-all flex items-center h-10 border border-[#222222]",
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
                <div className={cn(
                    "px-2 py-0.5 text-[10px] font-bold border",
                    data?.llama_ok ? "border-[#27AE60] text-[#27AE60]" : "border-[#C0392B] text-[#C0392B]"
                )}>
                    LLM
                </div>
                <div className={cn(
                    "px-2 py-0.5 text-[10px] font-bold border",
                    data?.agent_running ? "border-[#27AE60] text-[#27AE60]" : "border-[#C0392B] text-[#C0392B]"
                )}>
                    AGT
                </div>
            </div>

            {/* SYSTEM METRICS */}
            <div className="grid grid-cols-2 gap-x-8 text-[11px]">
                <div className="flex items-center gap-2">
                    <span className="text-[#666666]">CPU:</span>
                    <span className="text-[#FFB000]">{data?.cpu_temp || '0.0°C'}</span>
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-[#666666]">UP:</span>
                    <span className="text-[#FFB000]">{data?.uptime || '00:00:00'}</span>
                </div>
            </div>
            
            <div className="text-[12px] text-[#FFB000] font-bold border-l border-[#222222] pl-8 hidden lg:block uppercase tracking-widest">
                [EN/ES]
            </div>
        </div>
      </header>

      {/* MID: VIEWPORT */}
      <main className="flex-1 flex overflow-hidden min-h-0 relative">
        {children}
      </main>

      {/* BOTTOM: TELEMETRY TERMINAL */}
      <LogTerminal />

      {/* FOOTER: SYSTEM STATUS BAR */}
      <footer className="h-10 border-t border-[#222222] flex items-center justify-between px-8 bg-[#111111] shrink-0 font-mono">
        <div className="text-[11px] text-[#666666] flex items-center gap-8">
            <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-[#27AE60]" />
                <span className="uppercase text-[#AAAAAA] font-bold tracking-[0.2em]">ZOHAR_CORE: LINK_ACTIVE</span>
            </div>
            {data?.agent_state?.action && data.agent_state.action !== 'ESPERA' && (
                <span className="text-[#FFB000] animate-pulse">
                    &gt; EXECUTING_TASK: {data.agent_state.action} // TARGET: {data.agent_state.target}
                </span>
            )}
        </div>
        <div className="text-[11px] font-bold flex gap-6 text-[#666666] uppercase">
            <span>[F5:RESTART]</span>
            <span>[F6:STOP]</span>
            <span>[F7:RETRY]</span>
            <span className="text-[#AAAAAA] ml-12">(C)2026 ZOHAR_INTEL</span>
        </div>
      </footer>
    </div>
  );
}
