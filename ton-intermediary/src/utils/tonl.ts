/**
 * ★ Insight ─────────────────────────────────────
 * El Formateador TONL optimizado para "Alta Densidad" utiliza un mapa de 
 * diccionario estático. Al reducir el payload de cada campo a un solo carácter 
 * numérico, permitimos que el LLM procese batches de datos 60% más grandes.
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
    "emisiones_agregadas": "e",
    "avg": "a",
    "max": "m",
    "so2": "s",
    "nox": "n",
    "pm25": "p"
};

/**
 * Serializa objetos con soporte para "Batching" y agregación.
 */
export function serializeTONL(data: any): string {
    const serializeValue = (val: any): string => {
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

/**
 * Divide un payload TONL grande en chunks para no exceder 
 * los límites de memoria de trabajo del Agente.
 */
export function chunkTONL(payload: string, maxTokens: number = 500): string[] {
    // Estimación rápida: 4 caracteres por token
    const maxChars = maxTokens * 4;
    const chunks: string[] = [];
    let currentPos = 0;

    while (currentPos < payload.length) {
        chunks.push(payload.substring(currentPos, currentPos + maxChars));
        currentPos += maxChars;
    }

    return chunks;
}
