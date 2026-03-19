import { NextResponse } from 'next/server';
import { supabase } from '@/lib/supabase';

export async function GET() {
  try {
    // 1. Intentar obtener 2026 (prioridad absoluta del usuario)
    const { data: projects2026, error: err2026 } = await supabase
      .from('proyectos')
      .select('*')
      .eq('anio', 2026)
      .order('created_at', { ascending: false })
      .limit(200);

    if (err2026) throw err2026;

    let finalData = projects2026 || [];

    // 2. Fallback a 2025 solo si no hay nada en 2026
    if (finalData.length === 0) {
      const { data: projects2025, error: err2025 } = await supabase
        .from('proyectos')
        .select('*')
        .order('anio', { ascending: false })
        .order('created_at', { ascending: false })
        .limit(100);
      
      if (err2025) throw err2025;
      finalData = projects2025 || [];
    }

    // 3. Normalizar columnas para el Dashboard (Mayúsculas como espera el componente)
    // Nota: El componente actual pide id_proyecto en minúsculas en el estado, pero la UI muestra IDs.
    // Mantendremos la estructura de Supabase pero normalizada.
    const normalized = finalData.map(row => ({
      ID_PROYECTO: row.id_proyecto,
      id_proyecto: row.id_proyecto, // Compatibilidad con cliente actual
      ANIO: row.anio,
      anio: row.anio,
      PROMOVENTE: row.promovente,
      promovente: row.promovente,
      PROYECTO: row.proyecto,
      proyecto: row.proyecto,
      ESTADO: row.estado,
      estado: row.estado,
      MUNICIPIO: row.municipio,
      municipio: row.municipio,
      SECTOR: row.sector,
      sector: row.sector,
      INSIGHT: row.insight,
      insight: row.insight,
      CREATED_AT: row.created_at,
      created_at: row.created_at,
      GROUNDED: row.grounded,
      grounded: row.grounded
    }));

    return NextResponse.json(normalized);
  } catch (error: any) {
    console.error('API Projects error:', error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
