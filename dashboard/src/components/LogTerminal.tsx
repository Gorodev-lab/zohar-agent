'use client';

import React, { useEffect, useState, useRef } from 'react';

interface LogEntry {
  ts: string;
  lvl: string;
  msg: string;
}

export default function LogTerminal() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fetchLogs = async () => {
      try {
        const res = await fetch('/api/logs');
        const data = await res.json();
        if (Array.isArray(data)) {
          setLogs(data);
        }
      } catch (e) {}
    };

    fetchLogs();
    const timer = setInterval(fetchLogs, 3000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <div className="h-[180px] bg-[#050505] border-t border-[#222222] font-mono text-[11px] overflow-hidden flex flex-col shrink-0">
      <div className="h-6 px-4 bg-[#111111] border-b border-[#222222] flex items-center justify-between text-[#666666] shrink-0">
        <span className="uppercase tracking-[0.2em] font-bold text-[10px]">Telemetry_Terminal_Stream</span>
        <span>AUTO_SCROLL: ON</span>
      </div>
      <div 
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-4 space-y-1 scrollbar-tactical"
      >
        {logs.length === 0 && (
          <div className="text-[#222222] italic">Waiting for telemetry data...</div>
        )}
        {logs.map((log, i) => (
          <div key={i} className="flex gap-4">
            <span className="text-[#444444] shrink-0">[{log.ts?.split(' ')[1] || '00:00:00'}]</span>
            <span className={`shrink-0 font-bold ${
              log.lvl === 'INFO' ? 'text-blue-500' : 
              log.lvl === 'DEBUG' ? 'text-amber-600' : 
              log.lvl === 'ERROR' ? 'text-red-500' : 'text-[#666666]'
            }`}>[{log.lvl}]</span>
            <span className="text-[#AAAAAA] break-all">{log.msg}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
