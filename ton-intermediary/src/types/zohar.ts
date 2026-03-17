/**
 * ★ Insight ─────────────────────────────────────
 * El tipado estricto asegura que los reportes de cumplimiento ambiental 
 * se sincronicen sin pérdida de precisión. La inclusión de 'execution_path' 
 * permite al Intermediario decidir de forma determinista la ruta de 
 * ejecución (Highload vs. TON Connect).
 */

export interface EnvironmentalReport {
    timestamp: string;
    cycle_2026: boolean;
    pid: string;
    metrics: {
        avg: Record<string, number>;
        max: Record<string, number>;
    };
    violations: Array<{
        metric: string;
        value: number;
        limit: number;
        excess_pct: number;
    }>;
    risk_score: number;
    execution_path: 'AUTONOMOUS' | 'CRITICAL_SIGNATURE_REQUIRED';
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
    environmental_report?: EnvironmentalReport;
}

export interface TONTransactionRequest {
    targetAddress: string;
    amount: bigint;
    payload?: string;
}
