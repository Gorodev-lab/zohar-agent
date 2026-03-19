import { NextResponse } from 'next/server';

const CACHE_TTL_SECONDS = 300;
let sensorsCache: { data: any, lastUpdated: number | null } = {
    data: null,
    lastUpdated: null
};

function calculateAqiLevel(pm25: number): string {
    if (pm25 <= 12.0) return "GOOD";
    if (pm25 <= 35.4) return "MODERATE";
    if (pm25 <= 55.4) return "UNHEALTHY_SENSITIVE";
    if (pm25 <= 150.4) return "UNHEALTHY";
    return "HAZARDOUS";
}

export async function GET() {
    const now = Date.now();
    
    // 1. Check Cache
    if (sensorsCache.data && sensorsCache.lastUpdated && 
        (now - sensorsCache.lastUpdated) < CACHE_TTL_SECONDS * 1000) {
        return NextResponse.json(sensorsCache.data);
    }

    // 2. Fetch from OpenAQ
    const URL = "https://api.openaq.org/v3/locations";
    const params = new URLSearchParams({
        bbox: "-115.0,22.8,-109.4,28.0",
        limit: "100"
    });

    const apiKey = process.env.OPENAQ_API_KEY;
    const headers: any = {};
    if (apiKey) headers["X-API-Key"] = apiKey;

    try {
        const response = await fetch(`${URL}?${params.toString()}`, { 
            headers,
            signal: AbortSignal.timeout(10000)
        });

        if (!response.ok) {
            throw new Error(`OpenAQ Status: ${response.status}`);
        }

        const data = await response.json();
        
        // 3. Transformation to GeoJSON
        const features = data.results?.map((loc: any) => {
            const { coordinates, sensors, name, locality, id, datetimeFirst } = loc;
            if (!coordinates?.longitude || !coordinates?.latitude) return null;

            let pm25Val = 0.0;
            const latestPm25 = sensors?.find((s: any) => s.parameter?.name === "pm25");
            if (latestPm25?.latest) {
                pm25Val = latestPm25.latest.value || 0.0;
            }

            return {
                type: "Feature",
                geometry: {
                    type: "Point",
                    coordinates: [coordinates.longitude, coordinates.latitude]
                },
                properties: {
                    id: id || 0,
                    stationName: name || "ESTACIÓN_DESCONOCIDA",
                    city: locality || "Baja California Sur",
                    pm25: pm25Val,
                    aqi_level: calculateAqiLevel(pm25Val),
                    last_updated: datetimeFirst || new Date().toISOString(),
                    source: "OpenAQ_v3"
                }
            };
        }).filter(Boolean) || [];

        const geojsonResult = {
            type: "FeatureCollection",
            features
        };

        // 4. Update Cache
        sensorsCache = {
            data: geojsonResult,
            lastUpdated: now
        };

        return NextResponse.json(geojsonResult);

    } catch (err: any) {
        console.error("OpenAQ Link Error:", err);
        return NextResponse.json({
            msg: "ERROR_DE_ENLACE_TELEMETRICO",
            system: "ZOHAR_INTEL_BCS",
            code: "LINK_TIMEOUT_OR_API_FAIL"
        }, { status: 503 });
    }
}
