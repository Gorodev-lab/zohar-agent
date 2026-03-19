import { NextResponse } from 'next/server';
import { touchHeartbeat, PATHS } from '@/lib/system';
import { exec } from 'child_process';
import { promisify } from 'util';
import { promises as fsp } from 'fs';
import fs from 'fs';

const execAsync = promisify(exec);

export async function GET() {
  // 1. Non-blocking heartbeat update
  touchHeartbeat();
  
  const stats: any = {};
  
  try {
    // 2. Run diagnostics concurrently
    const [agentStatus, queueDataRaw] = await Promise.all([
      // Check agent process
      (async () => {
        try {
          const { stdout } = await execAsync('pgrep -f zohar_agent_v2');
          const pid = stdout.trim();
          if (pid) {
            const { stdout: psInfo } = await execAsync(`ps -p ${pid} -o %cpu,%mem,cmd`);
            const psOutput = psInfo.split('\n');
            if (psOutput.length > 1) {
              const [cpu, mem] = psOutput[1].trim().split(/\s+/);
              return { cpu, mem, running: true };
            }
          }
        } catch (e) {}
        return { running: false };
      })(),
      // Read queue file
      (async () => {
        if (fs.existsSync(PATHS.QUEUE_FILE)) {
          try {
            const content = await fsp.readFile(PATHS.QUEUE_FILE, 'utf8');
            return JSON.parse(content);
          } catch (e) {}
        }
        return null;
      })()
    ]);

    stats.agent = agentStatus;

    if (queueDataRaw) {
      const entries = Object.values(queueDataRaw) as any[];
      const total = entries.length;
      const success = entries.filter(v => v.status === 'success').length;
      const pending = entries.filter(v => v.status === 'pending').length;
      const failed = entries.filter(v => v.status === 'failed').length;

      stats.queue = {
        total,
        success,
        pending,
        failed,
        progress_pct: total > 0 ? Number(((success / total) * 100).toFixed(1)) : 0
      };
    }
  } catch (err) {
    console.error("Diagnostics error:", err);
  }

  return NextResponse.json({
    ts: new Date().toISOString(),
    services: stats,
    mode: "arch-linux-tactical-performance"
  });
}
