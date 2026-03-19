import { NextResponse } from 'next/server';
import { supabase } from '@/lib/supabase';

// 1. Configuración del Runtime a 'edge' para mínima latencia (TTFB) y despliegue global
export const runtime = 'edge';

// 2. Definición del TTL de Caché (5 min en CDN, 10 min de servido 'stale' mientras revalida)
const CACHE_CONTROL = 'public, s-maxage=300, stale-while-revalidate=600';

// Tipado estricto para las propiedades de GeoJSON (Esoteria Tactical Schema)
interface SensorProperties {
    id: string | number;
    stationName: string;
    city: string;
    pm25: number;
    aqi_level: string;
    last_updated: string;
    source: 'OpenAQ_v3' | 'SUPABASE_ZOHAR';
    status?: string;
}

// Lógica de cálculo AQI (Mantenemos coherencia con dashboard)
function calculateAqiLevel(pm25: number): string {
    if (pm25 <= 12.0) return "GOOD";
    if (pm25 <= 35.4) return "MODERATE";
    if (pm25 <= 55.4) return "UNHEALTHY_SENSITIVE";
    if (pm25 <= 150.4) return "UNHEALTHY";
    return "HAZARDOUS";
}

/**
 * Función resiliente para obtener datos de OpenAQ con timeout controlado
 */
async function fetchOpenAQ(signal: AbortSignal) {
    const URL = "https://api.openaq.org/v3/locations";
    const params = new URLSearchParams({
        bbox: "-115.0,22.8,-109.4,28.0", // Región Baja California Sur
        limit: "100"
    });

    const apiKey = process.env.OPENAQ_API_KEY;
    const headers: Record<string, string> = {};
    if (apiKey) headers["X-API-Key"] = apiKey;

    const response = await fetch(`${URL}?${params.toString()}`, { 
        headers, 
        signal,
        next: { revalidate: 300 } // Caché nativa de Next.js para peticiones internas
    });

    if (!response.ok) throw new Error(`OpenAQ_FAIL_${response.status}`);
    const data = await response.json();
    
    return (data.results || []).map((loc: any) => {
        const pm25Val = loc.sensors?.find((s: any) => s.parameter?.name === "pm25")?.latest?.value || 0.0;
        return {
            type: "Feature",
            geometry: {
                type: "Point",
                coordinates: [loc.coordinates.longitude, loc.coordinates.latitude]
            },
            properties: {
                id: loc.id,
                stationName: loc.name || "ESTACIÓN_OPENAQ",
                city: loc.locality || "MX_REGION",
                pm25: pm25Val,
                aqi_level: calculateAqiLevel(pm25Val),
                last_updated: loc.datetimeFirst || new Date().toISOString(),
                source: "OpenAQ_v3"
            }
        };
    });
}

/**
 * Función resiliente para obtener datos de Supabase (Zohar Internal Database)
 */
async function fetchSupabaseSensors() {
    // Nota: El cliente de Supabase ya usa fetch internamente en Edge
    const { data, error } = await supabase
        .from('aire_emisiones')
        .select('id, municipio, entidad, pm25, lat, lon, created_at, fuente')
        .not('lat', 'is', null)
        .limit(200);

    if (error) throw error;

    return (data || []).map((s: any) => ({
        type: "Feature",
        geometry: {
            type: "Point",
            coordinates: [s.lon, s.lat]
        },
        properties: {
            id: s.id,
            stationName: s.municipio || "ZOHAR_STATION",
            city: s.entidad || "INTERIOR",
            pm25: s.pm25 || 0.0,
            aqi_level: calculateAqiLevel(s.pm25 || 0.0),
            last_updated: s.created_at,
            source: "SUPABASE_ZOHAR",
            status: "INTERNAL_PROB"
        }
    }));
}

export async function GET() {
    // 3. Implementación de AbortController para evitar funciones colgadas (I/O Resiliency)
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 8000); // Máximo 8 segundos de espera

    try {
        // 4. Patrón de Concurrencia (Fan-out): Ejecutamos peticiones en paralelo
        // allSettled permite que el mapa funcione aunque una de las dos fuentes falle
        const results = await Promise.allSettled([
            fetchOpenAQ(controller.signal),
            fetchSupabaseSensors()
        ]);

        clearTimeout(timeoutId);

        // Orquestación de resultados (Transformación Eficiente)
        const features = results.flatMap((res, index) => {
            if (res.status === 'fulfilled') return res.value;
            console.error(`Source ${index === 0 ? 'OpenAQ' : 'Supabase'} failed:`, res.reason);
            return [];
        });

        const geojson = {
            type: "FeatureCollection",
            features: features.filter(f => f !== null),
            metadata: {
                last_aggregated: new Date().toISOString(),
                active_sources: results.filter(r => r.status === 'fulfilled').length
            }
        };

        // 5. Envío de respuesta con encabezados SWR para infraestructura de Next.js/Vercel
        return NextResponse.json(geojson, {
            status: 200,
            headers: {
                'Cache-Control': CACHE_CONTROL,
                'X-Aggregated-At': new Date().toISOString()
            }
        });

    } catch (err: any) {
        // 6. Manejo de Errores Resiliente (Degraded Mode)
        // Se devuelve 200 con un FeatureCollection vacío para asegurar que el componente del plano (mapa)
        // no crashee y pueda mostrar al menos la base del mapa sin puntos.
        console.error("CRITICAL_GEOJSON_ERROR:", err);
        return NextResponse.json({
            type: "FeatureCollection",
            features: [],
            status: "DEGRADED_MODE",
            msg: "ERROR_DE_ENLACE_TELEMETRICO",
            code: err.name === 'AbortError' ? 'TIMEOUT' : 'SERVICE_UNAVAILABLE'
        }, { 
            status: 200, 
            headers: { 'Cache-Control': 'no-store' } 
        });
    }
}
