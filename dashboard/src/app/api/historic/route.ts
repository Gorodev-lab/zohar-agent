import { NextResponse } from 'next/server';
import { supabase } from '@/lib/supabase';
import fs from 'fs';
import path from 'path';

export async function GET() {
  try {
    // 1. Cargar datos históricos desde el JSON estático
    const jsonPath = path.join(process.cwd(), 'src', 'semarnat_historic_consultations.json');
    let historicData: any[] = [];
    
    if (fs.existsSync(jsonPath)) {
      const raw = fs.readFileSync(jsonPath, 'utf8');
      historicData = JSON.parse(raw);
    }

    // Normalizar formato histórico - UNICAMENTE 2026
    const normalizedHistoric = historicData
      .filter((item: any) => String(item.anio) === "2026")
      .map((item: any) => ({
        Clave: item.clave,
        Modalidad: item.modalidad,
        Promovente: item.promovente,
        Proyecto: item.proyecto,
        Ubicacion: item.ubicacion,
        Sector: item.sector,
        Fecha: item.fechas,
        Año: item.anio,
        Estatus: "CONCLUIDO_2026",
        links: item.links || {}
      }));

    // 2. Obtener extracciones LIVE de 2026 desde Supabase
    const { data: liveData, error: liveError } = await supabase
      .from('proyectos')
      .select('*')
      .eq('anio', 2026)
      .order('created_at', { ascending: false });

    // 3. Merge inteligente (Priorizar Live sobre estático)
    const existingClaves = new Set(normalizedHistoric.map((h: any) => h.Clave ? h.Clave.toUpperCase() : ""));
    const merged = [...normalizedHistoric];

    if (liveData) {
      liveData.forEach((row: any) => {
        const clave = row.id_proyecto.toUpperCase();
        if (!existingClaves.has(clave)) {
          merged.unshift({
            Clave: row.id_proyecto,
            Modalidad: row.grounded ? "MIA-P" : "MIA",
            Promovente: row.promovente,
            Proyecto: row.proyecto,
            Ubicacion: `${row.estado}, ${row.municipio}`,
            Sector: row.sector,
            Fecha: row.created_at,
            Año: row.anio,
            Estatus: "EXTRACTED_LIVE_2026",
            links: row.sources || {}
          });
        }
      });
    }

    return NextResponse.json(merged);
  } catch (error: any) {
    console.error('API Historic error:', error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
