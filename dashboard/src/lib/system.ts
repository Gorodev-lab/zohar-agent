import { exec } from 'child_process';
import { promisify } from 'util';
import os from 'os';
import fs from 'fs';
import { promises as fsp } from 'fs';
import path from 'path';

const execAsync = promisify(exec);
const HOME = os.homedir();
const BASE_DIR = path.resolve(process.cwd(), '..');

export const PATHS = {
  HOME,
  BASE_DIR,
  DB_PATH: path.join(HOME, 'zohar_intelligence.db'),
  DUCK_PATH: path.join(HOME, 'zohar_warehouse.duckdb'),
  CSV_PATH: path.join(HOME, 'zohar_historico_proyectos.csv'),
  STATE_FILE: path.join(HOME, 'zohar_agent_state.json'),
  QUEUE_FILE: path.join(BASE_DIR, 'agent', 'zohar_queue.json'),
  LOG_FILE: path.join(BASE_DIR, 'agent', 'zohar_agent.jsonl'),
  HISTORIC_FILE: path.join(BASE_DIR, 'agent', 'semarnat_historic_consultations.json'),
  HEARTBEAT_FILE: path.join(HOME, '.zohar_heartbeat'),
};

export async function touchHeartbeat() {
  try {
    const now = new Date();
    if (fs.existsSync(PATHS.HEARTBEAT_FILE)) {
        await fsp.utimes(PATHS.HEARTBEAT_FILE, now, now);
    } else {
        await fsp.writeFile(PATHS.HEARTBEAT_FILE, '');
    }
  } catch (err) {
    // Ignore errors
  }
}

export async function getCpuTemp(): Promise<string> {
  try {
    const { stdout } = await execAsync('sensors');
    const match = stdout.match(/(?:CPU|temp1|Tdie):\s+\+?([\d.]+)/);
    return match ? `${match[1]}°C` : 'N/A';
  } catch (err) {
    return 'N/A';
  }
}

export async function checkLlamaStatus(): Promise<boolean> {
  try {
    const res = await fetch('http://127.0.0.1:8001/v1/models', { signal: AbortSignal.timeout(2000) });
    return res.status === 200;
  } catch (err) {
    return false;
  }
}

export async function isAgentAlive(): Promise<boolean> {
  try {
    const { stdout } = await execAsync('pgrep -f zohar_agent_v2');
    return stdout.trim().length > 0;
  } catch (err) {
    return false;
  }
}
