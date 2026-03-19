import { NextResponse } from 'next/server';
import { touchHeartbeat, PATHS } from '@/lib/system';
import { execSync } from 'child_process';
import path from 'path';
import fs from 'fs';

export async function POST(req: Request) {
  touchHeartbeat();
  
  const { service, action } = await req.json();
  const validActions = ["start", "stop", "restart", "retry-failed"];
  
  if (!validActions.includes(action)) {
    return NextResponse.json({ error: "Acción no válida" }, { status: 400 });
  }

  if (service === "agent") {
    const ctlScript = path.join(PATHS.BASE_DIR, 'agent', 'zohar_ctl.sh');
    if (!fs.existsSync(ctlScript)) {
      return NextResponse.json({ error: "Script de control no encontrado" }, { status: 500 });
    }

    try {
      if (action === "restart") {
        execSync(`${ctlScript} stop`, { encoding: 'utf8' });
        execSync(`${ctlScript} start`, { encoding: 'utf8' });
        return NextResponse.json({ status: "ok", msg: "Agente reiniciado" });
      }

      execSync(`${ctlScript} ${action}`, { encoding: 'utf8' });
      return NextResponse.json({ status: "ok", msg: `Comando ${action} ejecutado para agente` });
    } catch (err: any) {
      console.error("Agent control error:", err);
      return NextResponse.json({ error: err.message }, { status: 500 });
    }
  } else if (["llm", "ocr"].includes(service)) {
    return NextResponse.json({ status: "ok", msg: `Simulación: Comando ${action} ejecutado para ${service.toUpperCase()}` });
  }

  return NextResponse.json({ error: "Servicio no encontrado" }, { status: 404 });
}
