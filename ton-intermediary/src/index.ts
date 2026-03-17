import express, { Request, Response } from 'express';
import { serializeTONL, chunkTONL } from './utils/tonl.js';
import { Address } from 'ton-core';
import dotenv from 'dotenv';
import { ZoharProject } from './types/zohar.js';

dotenv.config();

/**
 * ★ Insight ─────────────────────────────────────
 * El "Guardián de Determinismo" actúa como la última línea de defensa. 
 * Al filtrar por el ciclo 2026 antes de la serialización, eliminamos la 
 * latencia de procesamiento de datos obsoletos, asegurando que el 
 * Intermediario solo orqueste transacciones vigentes sobre la red TON.
 */

const app = express();
const PORT = process.env.PORT || 3000;
const PYTHON_API_BASE = process.env.PYTHON_API_BASE || 'http://localhost:8081';

app.use(express.json());

app.get('/agent/sync/:pid', async (req: Request, res: Response) => {
    const { pid } = req.params;
    
    try {
        const response = await fetch(`${PYTHON_API_BASE}/proyectos/${pid}`);
        if (!response.ok) throw new Error(`Source API error: ${response.status}`);
        
        const data: ZoharProject = await response.json();

        // --- Guardián de Determinismo (Ciclo 2026) ---
        if (data.year && data.year !== 2026) {
            console.warn(`[REJECT] Project ${pid} excluded: Cycle mismatch (${data.year})`);
            return res.status(403).send("ERR:OUT_OF_CURRENT_CYCLE_2026");
        }

        // --- Capa de Agregación y Compactación ---
        const optimizedPayload = serializeTONL(data);

        // --- Handling de Batches si el payload es masivo ---
        if (optimizedPayload.length > 2000) {
            const chunks = chunkTONL(optimizedPayload);
            res.setHeader('X-Batch-Mode', 'Chunked');
            return res.json({ batches: chunks.length, data: chunks });
        }
        
        res.setHeader('X-Format', 'TONL-1.1-DENSITY');
        res.send(optimizedPayload);
        
    } catch (error) {
        console.error(`Error syncing ${pid}:`, error);
        res.status(500).send("ERR:INTERMEDIARY_SYNC_FAILED");
    }
});

/**
 * @deprecated Los endpoints que devuelven JSON crudo sin agregación ambiental 
 * han sido marcados como ineficientes.
 */
app.get('/legacy/fetch/:pid', (req, res) => {
    res.status(410).send("DEPRECATED: Use /agent/sync/:pid instead.");
});

app.listen(PORT, () => {
    console.log(`🛡️ Guardián Zohar (2026) activo en puerto ${PORT}`);
});
