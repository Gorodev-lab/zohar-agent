/**
 * ★ Insight ─────────────────────────────────────
 * El mapeo TONL v1.2 incluye campos para reportes ambientales. 
 * Al comprimir "violations" y "execution_path" en claves cortas, 
 * el registro on-chain se vuelve 5x más barato en términos de storage fees.
 */

export const TONL_MAP: Record<string, string> = {
    "pid": "0",
    "promovente": "1",
    "proyecto": "2",
    "ubicacion": "3",
    "sector": "4",
    "score": "5",
    "grounding_status": "6",
    "year": "y",
    "environmental_report": "r",
    "timestamp": "t",
    "cycle_2026": "c",
    "metrics": "m",
    "avg": "a",
    "max": "x",
    "violations": "v",
    "metric": "i",
    "value": "q",
    "limit": "l",
    "excess_pct": "p",
    "risk_score": "s",
    "execution_path": "e"
};

export function serializeTONL(data: any): string {
    const serializeValue = (val: any): string => {
        if (Array.isArray(val)) {
            return `[${val.map(v => serializeValue(v)).join(",")}]`;
        }
        if (typeof val === 'object' && val !== null) {
            return `(${serializeObject(val)})`;
        }
        return String(val).replace(/\^|\|/g, " ");
    };

    const serializeObject = (obj: any): string => {
        return Object.entries(obj)
            .filter(([_, v]) => v !== null && v !== undefined)
            .map(([k, v]) => `${TONL_MAP[k] || k}:${serializeValue(v)}`)
            .join("^");
    };

    if (Array.isArray(data)) return data.map(serializeObject).join("|");
    return serializeObject(data);
}
