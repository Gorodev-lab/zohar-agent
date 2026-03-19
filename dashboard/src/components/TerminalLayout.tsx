'use client';

import React, { useState, useEffect } from 'react';
import { supabase } from '@/lib/supabase';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface AgentStatus {
  id: number;
  pdf: string;
  action: string;
  target: string;
  last_seen: string;
}

export default function TerminalLayout({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [activeTab, setActiveTab] = useState('projects');
  
  useEffect(() => {
    const fetchStatus = async () => {
      const { data } = await supabase.from('agente_status').select('*').eq('id', 1).single();
      if (data) setStatus(data);
    };

    fetchStatus();
    const statusTimer = setInterval(fetchStatus, 10 * 1000);
    return () => clearInterval(statusTimer);
  }, []);

  return (
    <div className="h-screen w-screen flex flex-col bg-[#0A0A0A] text-[#FFFFFF] overflow-hidden selection:bg-[#FFB000] selection:text-black">
      {/* HEADER (Esoteria Nav Style) */}
      <header className="h-[64px] border-b border-[#222222] flex items-center justify-between px-8 bg-[#0A0A0A] shrink-0">
        <div className="flex items-center gap-12">
          <div className="font-bold text-[14px] flex items-center">
            <span className="text-[#FFB000] mr-2">&gt;</span>
            <span className="tracking-tight uppercase">ZOHAR // STRATEGIC_INTELLIGENCE</span>
          </div>
          
          <nav className="flex items-center gap-8">
            {[
              { id: 'projects', label: 'Proyectos' },
              { id: 'regulatory', label: 'Ordenamiento' },
              { id: 'air_quality', label: 'Calidad Aire' },
              { id: 'map', label: 'Visualizador GIS', link: '/aire' }
            ].map(tab => (
              tab.link ? (
                <a 
                  key={tab.id} 
                  href={tab.link} 
                  target="_blank" 
                  className="text-[13px] font-medium text-[#AAAAAA] hover:text-[#FFB000] transition-colors"
                >
                  {tab.label}
                </a>
              ) : (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    "text-[13px] font-medium transition-colors",
                    activeTab === tab.id ? "text-[#FFB000]" : "text-[#AAAAAA] hover:text-[#FFB000]"
                  )}
                >
                  {tab.label}
                </button>
              )
            ))}
          </nav>
        </div>

        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2 text-[12px] text-[#666666]">
            <span className={cn(
                "w-2 h-2",
                status ? "bg-[#27AE60]" : "bg-[#C0392B]"
            )} />
            <span className="uppercase tracking-widest">{status ? 'LIVE' : 'OFFLINE'}</span>
          </div>
        </div>
      </header>

      {/* MAIN CONTAINER */}
      <main className="flex-1 flex overflow-hidden min-h-0">
        {children}
      </main>

      {/* FOOTER */}
      <footer className="h-8 border-t border-[#222222] flex items-center justify-between px-8 bg-[#0A0A0A] shrink-0">
        <div className="text-[11px] text-[#666666] flex items-center gap-4">
            <span>&copy; 2026 ESOTERIA PLATFORM</span>
            <span className="w-px h-3 bg-[#222222]" />
            <span>ZOHAR_INSTANCE_02</span>
        </div>
        <div className="text-[11px] text-[#666666]">
            DOC_REF: STYLE_GUIDE_v1.0
        </div>
      </footer>
    </div>
  );
}
