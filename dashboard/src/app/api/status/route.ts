import { NextResponse } from 'next/server';
import { getCpuTemp, isAgentAlive, checkLlamaStatus } from '@/lib/system';
import { supabase } from '@/lib/supabase';

// Simple TTL Cache (1s) to handle high-frequency polling
let lastStatus: any = null;
let lastUpdate = 0;
const CACHE_TTL = 1000;

export async function GET() {
  const now = Date.now();
  if (lastStatus && (now - lastUpdate < CACHE_TTL)) {
    return NextResponse.json(lastStatus);
  }

  try {
    // 1. Concurrent checks for system and agent status (Non-blocking pattern)
    const [cpuTemp, llamaOk, agentAlive, sbRes] = await Promise.all([
      getCpuTemp(),
      checkLlamaStatus(),
      isAgentAlive(),
      supabase.from('agente_status').select('*').eq('id', 1).single()
    ]);

    const agentData = {
      pdf: sbRes.data?.pdf || "INACTIVO",
      action: sbRes.data?.action || "CLOUD_MODE",
      target: sbRes.data?.target || "VERCEL",
      time: (sbRes.data?.last_seen || "").slice(-8)
    };

    lastStatus = {
      cpu_temp: cpuTemp,
      llama_status: llamaOk ? "ONLINE" : "OFFLINE",
      agent_running: agentAlive,
      llama_ok: llamaOk,
      mode: "hybrid-nextjs",
      agent_state: agentData
    };
    lastUpdate = now;

    return NextResponse.json(lastStatus);
  } catch (err: any) {
    console.error("Status check error:", err);
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
