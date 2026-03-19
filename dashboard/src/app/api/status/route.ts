import { NextResponse } from 'next/server';
import { getCpuTemp, isAgentAlive, checkLlamaStatus, getUptime } from '@/lib/system';
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
    const isVercel = process.env.VERCEL === '1';

    // 1. Concurrent checks for system and agent status
    const [cpuTempLocal, llamaOkLocal, agentAliveLocal, sbRes] = await Promise.all([
      getCpuTemp(),
      checkLlamaStatus(),
      isAgentAlive(),
      supabase.from('agente_status').select('*').eq('id', 1).single()
    ]);

    // 2. Cloud-Aware Logic: If on Vercel, use Supabase values reported by local agent
    const cpuTemp = isVercel ? (sbRes.data?.cpu_temp || "N/A") : cpuTempLocal;
    const uptime = isVercel ? (sbRes.data?.uptime || "00:00:00") : getUptime();
    const llamaOk = isVercel ? (sbRes.data?.llama_ok ?? false) : llamaOkLocal;
    const agentAlive = isVercel ? (sbRes.data?.agent_alive ?? false) : agentAliveLocal;

    const agentData = {
      pdf: sbRes.data?.pdf || "INACTIVO",
      action: sbRes.data?.action || "CLOUD_MODE",
      target: sbRes.data?.target || "VERCEL",
      time: (sbRes.data?.last_seen || "").slice(-8)
    };

    lastStatus = {
      cpu_temp: cpuTemp,
      uptime: uptime,
      llama_status: llamaOk ? "ONLINE" : "OFFLINE",
      agent_running: agentAlive,
      llama_ok: llamaOk,
      mode: isVercel ? "cloud-tactical" : "hybrid-local",
      agent_state: agentData
    };
    lastUpdate = now;

    return NextResponse.json(lastStatus);
  } catch (err: any) {
    console.error("Status check error:", err);
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
