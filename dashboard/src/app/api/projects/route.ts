import { NextResponse } from 'next/server';
import { supabase } from '@/lib/supabase';

export async function GET() {
  try {
    // 1. Fetch all records from 'proyectos'
    const { data: projects, error } = await supabase
      .from('proyectos')
      .select('*')
      .order('anio', { ascending: false })
      .order('created_at', { ascending: false });

    if (error) throw error;

    // 2. Map all fields to maintain raw tactical parity with dashboard_legacy
    const normalized = (projects || []).map(row => ({
      ...row,
      // Field normalization for both Legacy UI support and Esoteria conventions
      id_proyecto: row.id_proyecto,
      anio: row.anio,
      promovente: row.promovente,
      proyecto: row.proyecto,
      estado: row.estado,
      municipio: row.municipio,
      sector: row.sector,
      insight: typeof row.insight === 'object' ? JSON.stringify(row.insight) : (row.insight || row.extracted_data?.insight || ""),
      reasoning: typeof row.reasoning === 'object' ? JSON.stringify(row.reasoning) : (row.reasoning || row.extracted_data?.reasoning || ""),
      context: row.context || "",
      grounded: row.grounded === true || row.grounded === "true" || row.grounded === "OK",
      sources: Array.isArray(row.sources) ? row.sources : [],
      audit_status: row.audit_status || "PENDING",
      auditor: row.auditor || "AGENT_ZOHAR",
      confidence: row.confidence || 0,
      coordinates: row.coordinates || "N/A"
    }));

    return NextResponse.json(normalized);
  } catch (error: any) {
    console.error('API Projects error:', error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
