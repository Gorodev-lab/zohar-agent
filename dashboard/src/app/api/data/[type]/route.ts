import { NextResponse } from 'next/server';
import { supabase } from '@/lib/supabase';
import { PATHS } from '@/lib/system';
import fs from 'fs';
import path from 'path';

export async function GET(req: Request, { params }: { params: Promise<{ type: string }> }) {
  const { type } = await params;
  
  try {
    if (type === 'air_quality') {
        // 1. Try Supabase first (Cloud mode parity)
        try {
            const { data: sbData, error } = await supabase
                .from('aire_emisiones')
                .select('*')
                .limit(5000);
            
            if (sbData && !error) {
                return NextResponse.json(sbData.map((row: any) => ({
                    Entidad_federativa: row.entidad || "",
                    Municipio: row.municipio || "",
                    Tipo_de_Fuente: row.fuente || "",
                    SO_2: row.so2,
                    CO: row.co,
                    NOx: row.nox,
                    COV: row.cov,
                    PM_010: row.pm10,
                    PM_2_5: row.pm25,
                    NH_3: row.nh3,
                    lat: row.lat,
                    lon: row.lon,
                })));
            }
        } catch (err) {
            console.error("Supabase air quality error:", err);
        }

        // 2. Try snapshot fallback (Vercel friendly)
        const snapshotPath = path.resolve(process.cwd(), '..', 'dashboard_legacy', 'aire_snapshot.json');
        if (fs.existsSync(snapshotPath)) {
            const data = fs.readFileSync(snapshotPath, 'utf8');
            return NextResponse.json(JSON.parse(data));
        }

        // Check if there is a CSV fallback
        if (fs.existsSync(PATHS.CSV_PATH)) {
            // Very basic CSV parser for the sake of the refactor
            const raw = fs.readFileSync(PATHS.CSV_PATH, 'utf8');
            const lines = raw.split('\n');
            const headers = lines[0].split(',');
            const result = lines.slice(1).map(line => {
                const values = line.split(',');
                return headers.reduce((obj: any, header, i) => {
                    obj[header.trim()] = values[i]?.trim();
                    return obj;
                }, {});
            });
            return NextResponse.json(result);
        }
    } else if (type === 'regulatory') {
        const { data: sbData, error } = await supabase
            .from('environmental_zoning')
            .select('*')
            .order('consecutivo', { ascending: true })
            .limit(500);
        
        if (sbData && !error) {
            return NextResponse.json(sbData.map((row: any) => ({
                "Consecutivo": row.consecutivo,
                "Estado": row.estado,
                "Programa": row.programa,
                "Modalidad": row.modalidad,
                "Expedicion": row.expedicion,
                "Superficie (ha)": row.superficie_ha,
                "Fecha": row.fecha,
                "fn.superficie (ha)": row.fn_superficie_ha,
            })));
        }
    } else if (type === 'financial') {
        const { data: sbData, error } = await supabase
            .from('ingresos_2024')
            .select('*')
            .order('no', { ascending: true })
            .limit(500);
        
        if (sbData && !error) {
            return NextResponse.json(sbData.map((row: any) => ({
                "Consecutivo": row.no,
                "Bitácora": row.bitacora,
                "Clave Proyecto": row.clave,
                "Promovente": row.promovente,
                "Nombre Proyecto": row.proyecto,
                "Modalidad": row.estudio,
                "Estatus": row.estatus,
                "Fecha ingreso": row.fecha_ingreso,
                "Fecha Resolución": row.fecha_resolucion,
                "Resolución": row.resolucion,
                "Quién Resolvió": row.tipo_resolucion,
                "Oficio Resolución": row.folio_resolucion,
                "Entidad Federativa donde Ingresó": row.entidad_ingreso,
                "Entidad Federativa Resolución": row.entidad_gestion,
                "Estado": row.entidad_mas_afectada,
                "Municipio": row.municipio_mas_afectado,
                "Días Laborables Transcurridos": row.dia,
                "Plazo Máximo Días": row.dias,
                "Situación Plazo": row.eficiencia,
                "Sector": row.subsector
            })));
        }
    }

    return NextResponse.json([]);
  } catch (err: any) {
    console.error(`Data API error (${type}):`, err);
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
