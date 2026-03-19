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

  const handleTogglePause = async () => {
    const action = data?.is_paused ? 'resume' : 'pause';
    try {
      await fetch('/api/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ service: 'agent', action })
      });
      // Update local state immediately for responsiveness
      setData({ ...data, is_paused: action === 'pause' });
    } catch (err) {
      console.error("Failed to toggle pause:", err);
    }
  };

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
              { id: 'diagnostics', label: '[ DIAGNÓSTICOS ]' },
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
                <div className="flex flex-col border-l border-[#222222] pl-6 h-10 justify-center">
                    <div className="flex items-center gap-2">
                        <span className="text-[9px] text-[#666666]">TOKENS:</span>
                        <span className="text-[#FFB000] text-[10px] font-bold">{(data?.total_tokens / 1000).toFixed(1)}K</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="text-[9px] text-[#666666]">CREDIT:</span>
                        <span className="text-[#FFB000] text-[10px] font-bold">${data?.total_cost?.toFixed(3)}</span>
                    </div>
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
        {activeTab === 'diagnostics' && data && (
            <div className="flex-1 p-8 overflow-y-auto font-mono text-[12px]">
                <h2 className="text-[#FFB000] text-[18px] font-black mb-8 border-b border-[#222222] pb-4 uppercase tracking-[0.2em]">
                    AUDITORÍA_DIAGNÓSTICA_SISTEMA_2026
                </h2>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-12">
                    {/* RESOURCE MONITOR */}
                    <section className="space-y-6">
                        <div className="border border-[#222222] bg-[#111111] p-6 shadow-[4px_4px_0px_#222222]">
                            <h3 className="text-[#FFB000] font-black mb-4 flex items-center gap-2">
                                <span className="animate-pulse">●</span> RECURSOS_LOCALES
                            </h3>
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <div className="text-[#666666] text-[10px]">CPU_TEMP</div>
                                    <div className={cn("text-[14px] font-black", parseFloat(data?.cpu_temp) > 75 ? "text-red-500" : "text-white")}>
                                        {data?.cpu_temp}
                                    </div>
                                </div>
                                <div>
                                    <div className="text-[#666666] text-[10px]">DISK_ROOT_AVAIL</div>
                                    <div className="text-[14px] font-black text-white">{data?.disk_avail || 'N/A'}</div>
                                </div>
                                <div className="col-span-2">
                                    <div className="text-[#666666] text-[10px] mb-1">MEMORIA_RAM_SYS [{data?.mem_used}% USED]</div>
                                    <div className="w-full bg-[#222222] h-2">
                                        <div className="bg-[#FFB000] h-full" style={{ width: `${data?.mem_used}%` }}></div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="border border-[#222222] bg-[#0A0A0A] p-6">
                            <h3 className="text-[#FFB000] font-black mb-4">ESTRATEGIA_EFICIENCIA_IA</h3>
                            <ul className="space-y-3 text-[#CCCCCC]">
                                <li className="flex items-start gap-2">
                                    <span className="text-[#FFB000]">→</span>
                                    <span>Uso de <b className="text-[#FFB000]">Qwen-1.5B</b> para filtrado previo de relevancia.</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="text-[#FFB000]">→</span>
                                    <span>Gemini Flash 2.0 restringido a extracción final.</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="text-[#FFB000]">→</span>
                                    <span>Log Rotation activo: Limita crecimiento de .jsonl</span>
                                </li>
                            </ul>
                        </div>
                    </section>

                    {/* API KEY & ACCOUNT INTEL */}
                    <section className="space-y-6">
                        <div className="border border-[#222222] bg-[#111111] p-6 shadow-[-4px_4px_0px_#222222]">
                            <h3 className="text-[#FFB000] font-black mb-4 flex items-center gap-2">
                                IND_CUENTA_GOOGLE_AI
                            </h3>
                            <div className="space-y-4">
                                <div className="flex justify-between items-center border-b border-[#222222] pb-2">
                                    <span className="text-[#666666] text-[10px]">API_KEY_ID</span>
                                    <span className="text-white font-black">AIzaSy...AZoijs</span>
                                </div>
                                <div className="flex justify-between items-center border-b border-[#222222] pb-2">
                                    <span className="text-[#666666] text-[10px]">CUENTA_VINCULADA</span>
                                    <span className="text-[#FFB000] font-black">GOOGLE_AI_STUDIO_PRIMARY</span>
                                </div>
                                <div className="flex justify-between items-center border-b border-[#222222] pb-2">
                                    <span className="text-[#666666] text-[10px]">PROYECTO_GCP</span>
                                    <span className="text-white font-black">zohar-agent-dev (DEFAULT)</span>
                                </div>
                                <div className="flex justify-between items-center bg-[#FFB000]/10 p-2 mt-4">
                                    <span className="text-[#FFB000] text-[10px]">TIER_LEVEL</span>
                                    <span className="text-[#FFB000] font-black uppercase">PAID / GEN_PRO_READY</span>
                                </div>
                            </div>
                        </div>

                        <div className="p-4 border border-[#FFB000]/30 bg-[#FFB000]/5 text-[11px] text-[#FFB000] italic">
                            [!] NOTA: La API Key de Gemini se utiliza exclusivamente para 
                            la extracción estructurada de MIAs y auditoría social profunda. 
                            Relacionada a la cuenta de desarrollador Principal (gorops).
                        </div>
                    </section>
                </div>
            </div>
        )}
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
        <div className="text-[10px] font-bold flex items-center gap-6 text-[#666666] uppercase">
            <button onClick={() => window.location.reload()} className="hover:text-[#FFB000] transition-colors">[F5:RESTART]</button>
            <button 
                onClick={handleTogglePause}
                className={cn(
                    "px-3 py-0.5 border transition-all font-black text-[9px]",
                    data?.is_paused 
                        ? "bg-[#27AE60] text-white border-[#27AE60] animate-pulse" 
                        : "bg-[#C0392B] text-white border-[#C0392B] hover:bg-red-600"
                )}
            >
                {data?.is_paused ? "[ REANUDAR_TRABAJO ]" : "[ KILL_SWITCH_STOP ]"}
            </button>
            <span className="opacity-30">[F7:RETRY]</span>
            <div className="flex items-center gap-2 ml-10">
                <span className="text-[#444444]">23:25:27</span>
                <span className="text-[#444444]">(C)2026 ZOHAR_INTEL</span>
            </div>
        </div>
      </footer>
    </div>
  );
}
