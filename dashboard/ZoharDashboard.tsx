import React, { useState, useEffect } from 'react';
import { 
  Terminal, 
  Cpu, 
  Database, 
  Activity, 
  Shield, 
  Clock, 
  Search, 
  Circle,
  ExternalLink,
  Zap,
  Microscope
} from 'lucide-react';

/**
 * ★ Insight ─────────────────────────────────────
 * El uso estratégico del "espacio negativo" (whitespace) y bordes de opacidad ultra-baja 
 * ([0.03]) no es solo una elección estética; es una herramienta de ergonomía cognitiva. 
 * Al eliminar las líneas ASCII pesadas y los marcos de contraste agresivo, permitimos que 
 * la mirada del operador se deslice sin fricción hacia los números críticos. Las sombras 
 * de 'brillo profundo' (deep glow) separan los planos de información sin necesidad de 
 * rellenos sólidos, reduciendo la fatiga visual en turnos de monitoreo de alta densidad.
 */

// --- Componentes de UI de Lujo ---

const CyberCard = ({ children, className = "" }: { children: React.ReactNode, className?: string }) => (
  <div className={`
    bg-[#070707] 
    border border-white/[0.03] 
    shadow-[0_0_30px_rgba(139,92,246,0.02)] 
    backdrop-blur-sm 
    rounded-sm
    ${className}
  `}>
    {children}
  </div>
);

const SectionTitle = ({ children }: { children: React.ReactNode }) => (
  <h2 className="text-[10px] font-sans uppercase tracking-[0.25em] text-zinc-500 mb-4 px-1">
    {children}
  </h2>
);

// --- Dashboard Component ---

export default function PremiumZoharUI() {
  const [currentTime, setCurrentTime] = useState(new Date().toLocaleTimeString());
  const [agentStatus] = useState("OPERATIONAL");

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date().toLocaleTimeString()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="min-h-screen bg-[#050505] text-zinc-400 font-mono selection:bg-violet-500/20 p-8 antialiased">
      {/* Luz Abisal de Fondo */}
      <div className="fixed inset-0 bg-radial-at-t from-violet-900/5 via-transparent to-transparent pointer-events-none" />

      {/* Header Ejecutivo */}
      <header className="relative z-10 flex items-center justify-between mb-12">
        <div className="flex items-center gap-10">
          <div className="flex items-center gap-4">
            <div className="w-1.5 h-6 bg-violet-600 shadow-[0_0_15px_rgba(139,92,246,0.5)]" />
            <span className="text-zinc-100 font-sans font-bold tracking-[0.3em] uppercase text-xl">
              Zohar <span className="text-violet-400/80 font-light">// Intel</span>
            </span>
          </div>
          
          <div className="flex items-center gap-8 text-[11px] tracking-wider text-zinc-500">
            <div className="flex items-center gap-2">
              <Cpu className="w-3.5 h-3.5 text-violet-500/60" />
              <span>AMD EPYC™</span>
              <span className="text-zinc-100 italic">42°C</span>
            </div>
            <div className="flex items-center gap-2 border-l border-white/5 pl-8">
              <Database className="w-3.5 h-3.5 text-violet-500/60" />
              <span>DUCKDB_WAREHOUSE</span>
              <span className="text-zinc-100 uppercase">Sync_Ok</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-8">
          <div className="flex items-center gap-3">
            <span className="text-[10px] uppercase tracking-widest text-zinc-600">Status</span>
            <div className="flex items-center gap-2 px-3 py-1 bg-emerald-500/[0.03] border border-emerald-500/20 rounded-full">
              <div className="relative w-1.5 h-1.5">
                <div className="absolute inset-0 bg-emerald-500 rounded-full animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.8)]" />
                <div className="absolute -inset-1 border border-emerald-500/30 rounded-full animate-ping opacity-20" />
              </div>
              <span className="text-[10px] font-bold text-emerald-500/90 tracking-widest leading-none pt-0.5">
                {agentStatus}
              </span>
            </div>
          </div>
          <div className="text-right">
            <span className="text-[10px] uppercase tracking-[0.2em] text-zinc-600 block mb-0.5">System Time</span>
            <span className="text-zinc-200 text-sm font-light tracking-widest">{currentTime}</span>
          </div>
        </div>
      </header>

      {/* Main Layout */}
      <div className="relative z-10 grid grid-cols-12 gap-8 h-[calc(100vh-200px)]">
        
        {/* Camara 01: Monitor de Orquestación */}
        <section className="col-span-3 flex flex-col gap-8">
          <div className="flex-1">
            <SectionTitle>01 // ORCHESTRATION</SectionTitle>
            <CyberCard className="p-6 h-full flex flex-col justify-between">
              <div className="space-y-6">
                <div>
                  <span className="text-[10px] uppercase text-zinc-600 block mb-2">Current Pipeline</span>
                  <div className="text-zinc-100 flex items-center justify-between">
                    <span className="text-xs uppercase tracking-widest">Environmental_v2.2</span>
                    <Zap className="w-3 h-3 text-violet-500 animate-pulse" />
                  </div>
                </div>
                
                <div className="space-y-2">
                  <div className="flex justify-between text-[10px] uppercase tracking-wider">
                    <span className="text-zinc-500">Processing Load</span>
                    <span className="text-violet-400/80">68.4%</span>
                  </div>
                  <div className="h-[2px] w-full bg-white/[0.02]">
                    <div className="h-full bg-gradient-to-r from-violet-600 to-indigo-500 w-[68%] shadow-[0_0_10px_rgba(139,92,246,0.3)]" />
                  </div>
                </div>
              </div>

              <div className="pt-8 grid grid-cols-2 gap-4">
                <div className="p-4 bg-white/[0.01] border border-white/[0.02]">
                  <span className="text-[9px] text-zinc-600 block mb-1">Queue_Success</span>
                  <span className="text-xl text-zinc-100 font-light">1,720</span>
                </div>
                <div className="p-4 bg-white/[0.01] border border-white/[0.02]">
                  <span className="text-[9px] text-zinc-600 block mb-1">Queue_Pending</span>
                  <span className="text-xl text-violet-400 font-light">318</span>
                </div>
              </div>
            </CyberCard>
          </div>
        </section>

        {/* Camara 02: Intelligence Grounding */}
        <section className="col-span-6 flex flex-col overflow-hidden">
          <SectionTitle>02 // DEEP_GROUNDING_LEDGER</SectionTitle>
          <CyberCard className="flex-1 overflow-hidden flex flex-col">
            <div className="p-4 border-b border-white/[0.03] flex justify-between items-center bg-white/[0.01]">
              <div className="flex items-center gap-4">
                <Search className="w-3.5 h-3.5 text-zinc-600" />
                <input 
                  type="text" 
                  placeholder="FILTER_BY_PID..." 
                  className="bg-transparent border-none outline-none text-[11px] text-zinc-400 w-48 placeholder:text-zinc-700 font-mono tracking-widest"
                />
              </div>
              <Shield className="w-4 h-4 text-violet-500/40" />
            </div>

            <div className="flex-1 overflow-auto scrollbar-hide">
              <table className="w-full text-[11px]">
                <thead className="sticky top-0 bg-[#070707] text-zinc-600 uppercase tracking-widest border-b border-white/[0.1]">
                  <tr>
                    <th className="px-6 py-4 font-normal text-left">Internal_ID</th>
                    <th className="px-6 py-4 font-normal text-left">Gaceta_Text_Description</th>
                    <th className="px-6 py-4 font-normal text-right">Ground_Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.02]">
                  {[
                    { id: '15EM24U01', desc: 'Planta de cogeneración de energía térmica...', status: 'VERIFIED' },
                    { id: '04CA25E17', desc: 'Extracción de materiales pétreos en lecho de río...', status: 'PENDING' },
                    { id: '18NA25N51', desc: 'Restauración de ecosistema costero Nayarit...', status: 'VERIFIED' },
                    { id: '22BJ26F02', desc: 'Desarrollo habitacional de alta densidad...', status: 'REJECTED' },
                    { id: '09GT24M12', desc: 'Infraestructura vial de conexión metropolitana...', status: 'VERIFIED' }
                  ].map((row, i) => (
                    <tr key={i} className="group hover:bg-white/[0.02] transition-colors duration-200">
                      <td className="px-6 py-4">
                        <span className="text-violet-400/80 group-hover:text-violet-400">{row.id}</span>
                      </td>
                      <td className="px-6 py-4">
                        <span className="text-zinc-400 group-hover:text-zinc-200 block truncate max-w-xs">{row.desc}</span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <span className={`text-[9px] px-2 py-0.5 rounded-sm border ${
                          row.status === 'VERIFIED' ? 'border-emerald-500/20 text-emerald-500/80' : 
                          row.status === 'PENDING' ? 'border-amber-500/20 text-amber-500/80' : 
                          'border-rose-500/20 text-rose-500/80'
                        }`}>
                          {row.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CyberCard>
        </section>

        {/* Camara 03: Activity & Event Logs */}
        <section className="col-span-3 flex flex-col gap-4">
          <SectionTitle>03 // EVENT_STREAM</SectionTitle>
          <CyberCard className="flex-1 p-6 flex flex-col overflow-hidden bg-black/40">
            <div className="flex-1 overflow-auto space-y-3 font-mono text-[10px]">
              {[
                { time: '09:20:12', tag: 'INF', msg: 'Syncing_Warehouse_2026' },
                { time: '09:21:05', tag: 'DEB', msg: 'Llama_Inference: Batch_Ok' },
                { time: '09:21:44', tag: 'WAR', msg: 'Timeout_Portal: Retrying_Seq_03' },
                { time: '09:22:01', tag: 'INF', msg: 'Grounding: PID_04CA25E17_Matched' }
              ].map((log, i) => (
                <div key={i} className="flex gap-4 group">
                  <span className="text-zinc-700 shrink-0">{log.time}</span>
                  <span className={`${
                    log.tag === 'WAR' ? 'text-amber-500' : 
                    log.tag === 'DEB' ? 'text-zinc-600' : 'text-violet-500'
                  } font-bold shrink-0`}>{log.tag}</span>
                  <span className="text-zinc-500 group-hover:text-zinc-300 leading-relaxed truncate">
                    {log.msg}
                  </span>
                </div>
              ))}
              <div className="animate-pulse text-zinc-800 flex items-center gap-2">
                <div className="w-1 h-3 bg-zinc-800" />
                <span>LISTENING_FOR_EVENTS...</span>
              </div>
            </div>
          </CyberCard>
        </section>
      </div>

      {/* Footer Minimalista */}
      <footer className="fixed bottom-6 left-8 right-8 flex justify-between items-center text-[9px] text-zinc-700 uppercase tracking-[0.2em]">
        <div className="flex gap-12">
          <span>Core_v2.3_Landed</span>
          <span className="flex items-center gap-2">
            <div className="w-1 h-1 bg-violet-600 rounded-full" />
            Active_Tunnels: 02
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span>Secured by Esoteria Cipher</span>
          <Shield className="w-3 h-3" />
        </div>
      </footer>
    </div>
  );
}
