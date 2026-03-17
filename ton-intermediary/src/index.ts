import express, { Request, Response } from 'express';
import { serializeTONL, chunkTONL } from './utils/tonl.js';
import { Address } from 'ton-core';
import dotenv from 'dotenv';
import { ZoharProject } from './types/zohar.js';
import { TransactionDispatcher } from './utils/dispatcher.js';

dotenv.config();

/**
 * ★ Insight ─────────────────────────────────────
 * La arquitectura de "Despacho Dual" separa las responsabilidades: 
 * Node.js gestiona la infraestructura de red TON y la validación de 
 * seguridad, mientras que Python provee la inteligencia analítica. 
 * Esto permite escalar el Agente sin comprometer la custodia de llaves.
 */

const app = express();
const PORT = process.env.PORT || 3000;
const PYTHON_API_BASE = process.env.PYTHON_API_BASE || 'http://localhost:8081';
const TON_ENDPOINT = process.env.TON_ENDPOINT || 'https://toncenter.com/api/v2/jsonRPC';

const dispatcher = new TransactionDispatcher(TON_ENDPOINT);

app.use(express.json());

app.get('/agent/sync/:pid', async (req: Request, res: Response) => {
    const { pid } = req.params;
    
    try {
        const response = await fetch(`${PYTHON_API_BASE}/proyectos/${pid}`);
        if (!response.ok) throw new Error(`Source API error: ${response.status}`);
        
        const data: ZoharProject = await response.json();

        // 1. Guardián de Determinismo
        if (data.year && data.year !== 2026) {
            return res.status(403).send("ERR:OUT_OF_CURRENT_CYCLE_2026");
        }

        // 2. Generar Reporte Ambiental HITL (Vía Python)
        const reportResponse = await fetch(`${PYTHON_API_BASE}/proyectos/${pid}/report`);
        if (reportResponse.ok) {
            data.environmental_report = await reportResponse.json();
        }

        // 3. Orquestación del Despacho TON
        let dispatchResult = null;
        if (data.environmental_report) {
            dispatchResult = await dispatcher.dispatch(data.environmental_report);
        }

        // 4. Compactación TONL para storage/LLM
        const optimizedPayload = serializeTONL(data);
        
        res.json({
            tonl: optimizedPayload,
            dispatch: dispatchResult,
            standard: "TONL-1.2-HITL"
        });
        
    } catch (error) {
        console.error(`Error syncing ${pid}:`, error);
        res.status(500).send("ERR:INTERMEDIARY_SYNC_FAILED");
    }
});

app.listen(PORT, () => {
    console.log(`🛡️ Intermediario HITL Zohar activo en puerto ${PORT}`);
});
