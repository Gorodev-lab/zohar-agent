/**
 * ★ Insight ─────────────────────────────────────
 * El tipado estricto asegura que los datos agregados (promedios y máximos) 
 * mantengan la precisión decimal necesaria para el oráculo ambiental, 
 * evitando desbordamientos en la serialización TONL.
 */

export interface AggregatedEmissions {
    avg: {
        so2: number;
        nox: number;
        pm25: number;
    };
    max: {
        so2: number;
        nox: number;
        pm25: number;
    };
}

export interface ZoharProject {
    pid: string;
    promovente: string;
    proyecto: string;
    ubicacion: string;
    sector: string;
    score: number;
    grounding_status: "verified" | "unverified" | "rejected";
    year?: number;
    fechas_consulta?: string;
    emisiones_agregadas?: AggregatedEmissions;
}

export interface TONTransactionRequest {
    targetAddress: string;
    amount: bigint;
    payload?: string;
}
