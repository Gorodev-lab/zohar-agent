import { NextResponse } from 'next/server';
import { supabase } from '@/lib/supabase';
import fs from 'fs';
import path from 'path';

export async function GET(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  
  try {
    // 1. Fetch project data from Supabase
    const { data: project, error } = await supabase
      .from('proyectos')
      .select('*')
      .eq('id_proyecto', id)
      .single();
    
    if (error || !project) {
      return NextResponse.json({ error: "Proyecto no hallado" }, { status: 404 });
    }

    const { municipio, anio } = project;

    // 2. Fetch air quality data from snapshot
    const snapshotPath = path.resolve(process.cwd(), '..', 'dashboard_legacy', 'aire_snapshot.json');
    if (!fs.existsSync(snapshotPath)) {
        return NextResponse.json({ id, execution_path: "SKIPPED_NO_SNAPSHOT" });
    }

    const raw = fs.readFileSync(snapshotPath, 'utf8');
    const airData: any[] = JSON.parse(raw);
    
    // 3. Aggregate metrics for the municipio
    const municipioData = airData.filter(d => 
        d.municipio?.toLowerCase().includes(municipio?.toLowerCase()) || 
        municipio?.toLowerCase().includes(d.municipio?.toLowerCase())
    );

    if (municipioData.length === 0) {
        return NextResponse.json({ id, execution_path: "SKIPPED_NO_DATA" });
    }

    const metrics = {
        avg: { so2: 0, nox: 0, pm25: 0 },
        max: { so2: 0, nox: 0, pm25: 0 }
    };

    let count = 0;
    municipioData.forEach(d => {
        if (d.so2 != null) {
            metrics.avg.so2 += d.so2;
            metrics.max.so2 = Math.max(metrics.max.so2, d.so2);
        }
        if (d.nox != null) {
            metrics.avg.nox += d.nox;
            metrics.max.nox = Math.max(metrics.max.nox, d.nox);
        }
        if (d.pm25 != null) {
            metrics.avg.pm25 += d.pm25;
            metrics.max.pm25 = Math.max(metrics.max.pm25, d.pm25);
        }
        count++;
    });

    if (count > 0) {
        metrics.avg.so2 = Number((metrics.avg.so2 / count).toFixed(2));
        metrics.avg.nox = Number((metrics.avg.nox / count).toFixed(2));
        metrics.avg.pm25 = Number((metrics.avg.pm25 / count).toFixed(2));
    }

    // 4. Report logic
    const THRESHOLDS: any = { so2: 40.0, nox: 70.0, pm25: 25.0 };
    const violations: any[] = [];
    let riskScore = 0;

    for (const [m, limit] of Object.entries(THRESHOLDS)) {
        const current = (metrics.avg as any)[m] || 0;
        if (current > (limit as number)) {
            const pct = ((current - (limit as number)) / (limit as number)) * 100;
            violations.push({ metric: m, value: current, limit, excess_pct: Number(pct.toFixed(2)) });
            riskScore += pct;
        }
    }

    let pathLabel = "AUTONOMOUS";
    if (violations.some(v => v.excess_pct > 20.0) || riskScore > 50.0) {
        pathLabel = "CRITICAL_SIGNATURE_REQUIRED";
    }

    return NextResponse.json({
        timestamp: new Date().toISOString(),
        cycle_2026: anio === 2026,
        pid: id,
        metrics,
        violations,
        risk_score: Number(riskScore.toFixed(2)),
        execution_path: pathLabel
    });

  } catch (err: any) {
    console.error("Project report error:", err);
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
