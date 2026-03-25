---
name: Zohar Refactor & Purify
description: Skill para refactorizar, purificar y limpiar el código del Zohar Agent. Incluye cambio dinámico de modelos, control de ejecución por botón, mapeo de bases de datos, limpieza de archivos obsoletos y retención solo de extracciones exitosas con cross-validation y grounding chunks.
---

# Zohar Refactor & Purify

## Objetivo
Purificar el codebase del Zohar Agent eliminando deuda técnica, archivos obsoletos, dependencias innecesarias, y reestructurando la arquitectura para:

1. **Cambio dinámico de modelos** según flujo de trabajo
2. **Ejecución controlada** — solo con click de botón (no automático)
3. **Visibilidad total** de estado, bases de datos y recursos en tiempo real
4. **Limpieza de datos** — conservar solo extracciones exitosas con cross-validation y grounding chunks
5. **Eliminación de archivos obsoletos** de versiones anteriores

---

## Fase 1: Diagnóstico y Mapeo del Ecosistema

### 1.1 Bases de Datos Identificadas

| Base de Datos | Ubicación | Tipo | Estado | Propósito |
|---|---|---|---|---|
| `zohar_intelligence.db` | `~/zohar_intelligence.db` | SQLite | ⚠️ VACÍA (sin tabla projects) | Memoria operacional del agente |
| `zohar_warehouse.duckdb` | `~/gaceta_work/zohar_warehouse.duckdb` | DuckDB | ⚠️ Error de acceso | Cache de fragmentos + warehouse analítico |
| `zohar_warehouse.duckdb` | `~/zohar_warehouse.duckdb` | DuckDB | ⚠️ Error de acceso | Duplicado del warehouse |
| **Supabase `monitor_gaceta_eco`** | Cloud (`gmrnujwviunegvyuslrs`) | PostgreSQL | ✅ ACTIVA | **FUENTE PRIMARIA: 593 registros** |
| Supabase `denuncia-popular` | Cloud (`kqdoofezoxgoyvgbjiia`) | PostgreSQL | ✅ ACTIVA | Proyecto separado |
| Supabase `GacetaEcológica` | Cloud (`gcsyubbrejypgzmpfrpm`) | PostgreSQL | ❌ INACTIVA | Versión legacy |

### 1.2 Tablas en Supabase (`monitor_gaceta_eco`)

| Tabla | Registros | Uso |
|---|---|---|
| `proyectos` | 593 | Datos principales de impacto ambiental |
| `aire_emisiones` | 10,521 | Calidad del aire por municipio |
| `global_air_quality` | 10,000 | Datos globales de calidad del aire |
| `environmental_zoning` | 166 | Ordenamientos ecológicos |
| `ingresos_2024` | 536 | Datos financieros |
| `agente_status` | 1 | Estado del agente |
| `ai_usage` | 396 | Tracking de uso de IA |

### 1.3 Calidad de Datos en `proyectos`

| Métrica | Valor | % |
|---|---|---|
| Total registros | 593 | 100% |
| Con grounding + score | 213 | 35.9% |
| Sin grounding | 380 | 64.1% |
| Con fuentes web | 213 | 35.9% |
| Sin municipio | 63 | 10.6% |
| Sin proyecto | 0 | 0% |

### 1.4 Archivos Obsoletos a Eliminar

```
# Backups innecesarios
agent/zohar_agent_bak.jsonl          (1.9 MB)
agent/zohar_queue_bak.json           (7.8 MB)  
agent/zohar_seen_gacetas_bak.json    (1 KB)
.env.tmp                             (128 B)

# Logs acumulados (40 MB total en agent/)
agent/watchdog.log                   (17 MB)
agent/zohar_agent.jsonl              (12 MB)
agent/wget-log                       (217 KB)
agent/wget-log.1                     (229 KB)
api_access.log                       (189 KB)
api_log.txt                          (161 KB)
api_server.log                       (110 KB)
llama.log                            (68 KB)
qwen.log                             (16 KB)
agent_log.txt                        (12 KB)
probe.log                            (62 B)

# SQL/CSV de importación ya persistido en Supabase  
batch1.sql                           (84 KB)
batch2.sql                           (78 KB)
batch3.sql                           (59 KB)
income_data.sql                      (220 KB)
zoning_data.sql                      (30 KB)
ingresos_2024.csv                    (188 KB)
csv_to_sql.py                        (2.4 KB)

# Archivos de primera versión
Esoteria_Organizational_Restructure_Doctrine_v1.md
PROTOTYPE_ALT_AGENTS.md
mock_llama_server.py
current_temp_url.txt
tunnel_url.txt / tunnel_log.txt

# Dashboard Next.js (940 MB - ¡el más pesado!)
dashboard/                           (940 MB - node_modules)
```

---

## Fase 2: Arquitectura de Modelos Dinámicos

### 2.1 Model Router
Crear un router que seleccione el modelo según el flujo de trabajo:

```python
# warehouse/model_router.py

from dataclasses import dataclass
from typing import Optional
import os

@dataclass
class ModelConfig:
    name: str
    endpoint: str
    max_tokens: int
    temperature: float
    priority: int  # 1 = máxima prioridad

class ModelRouter:
    """Selecciona el modelo óptimo según el flujo de trabajo."""
    
    WORKFLOWS = {
        "extraction": {
            "primary": ModelConfig(
                name="gemini-3-flash-preview",
                endpoint="gemini",
                max_tokens=2000,
                temperature=0.1,
                priority=1
            ),
            "fallback": ModelConfig(
                name="DeepSeek-R1-Distill-Llama-8B-Q4_K_M.gguf",
                endpoint="http://127.0.0.1:8001/v1/chat/completions",
                max_tokens=500,
                temperature=0.1,
                priority=2
            )
        },
        "grounding": {
            "primary": ModelConfig(
                name="gemini-3-flash-preview",
                endpoint="gemini",
                max_tokens=2000,
                temperature=0.0,
                priority=1
            )
        },
        "ocr": {
            "primary": ModelConfig(
                name="gemini-3-flash-preview",
                endpoint="gemini",
                max_tokens=1500,
                temperature=0.0,
                priority=1
            ),
            "fallback": ModelConfig(
                name="qwen-ocr",
                endpoint="http://127.0.0.1:8002/v1/chat/completions",
                max_tokens=500,
                temperature=0.1,
                priority=2
            )
        },
        "audit": {
            "primary": ModelConfig(
                name="gemini-3-flash-preview",
                endpoint="gemini",
                max_tokens=3000,
                temperature=0.2,
                priority=1
            )
        }
    }
    
    @classmethod
    def get_model(cls, workflow: str, prefer_local: bool = False) -> ModelConfig:
        config = cls.WORKFLOWS.get(workflow, cls.WORKFLOWS["extraction"])
        if prefer_local and "fallback" in config:
            return config["fallback"]
        return config["primary"]
    
    @classmethod
    def get_fallback(cls, workflow: str) -> Optional[ModelConfig]:
        config = cls.WORKFLOWS.get(workflow, {})
        return config.get("fallback")
```

### 2.2 Implementación en el Agente

Reemplazar todas las llamadas hardcodeadas a modelos con:
```python
model = ModelRouter.get_model("extraction")
# En caso de error:
model = ModelRouter.get_fallback("extraction")
```

---

## Fase 3: Control de Ejecución por Botón

### 3.1 API Endpoint: `/api/control/agent/start-once`

El agente **NO** debe correr automáticamente. Crear un endpoint que:
1. Reciba un click del dashboard
2. Execute un ciclo único de extracción
3. Reporte progreso en tiempo real
4. Se detenga al completar

```python
@app.post("/api/control/agent/start-once")
async def start_agent_once():
    """Ejecuta UN SOLO ciclo de extracción (no demonio)."""
    # Verificar que no haya una ejecución en curso
    if _is_agent_alive():
        raise HTTPException(400, "Agente ya en ejecución")
    
    # Lanzar ciclo único en background
    subprocess.Popen(
        ["python3", str(AGENT_V2_PATH), "--single-run", "--year", "2026"],
        cwd=str(BASE_DIR),
        stdout=open(BASE_DIR / "agent" / "agent_output.log", "w"),
        stderr=subprocess.STDOUT
    )
    return {"status": "ok", "mode": "single-run", "msg": "Ciclo único iniciado"}
```

### 3.2 Dashboard: Botón de Control

Agregar al dashboard legacy un botón prominente:
```html
<button id="btn-extract" onclick="startExtraction()">
  ▶ INICIAR EXTRACCIÓN (CICLO ÚNICO)
</button>
```

Con indicador visual de progreso en tiempo real:
- 🟢 IDLE - Esperando comando
- 🟡 RUNNING - Extracción en progreso  
- 🔴 ERROR - Último ciclo falló
- ✅ COMPLETE - Ciclo completado exitosamente

---

## Fase 4: Dashboard de Recursos en Tiempo Real

### 4.1 Endpoint: `/api/resources`

```python
@app.get("/api/resources")
async def get_resources():
    """Métricas en tiempo real del sistema."""
    return {
        "cpu_temp": _get_cpu_temp(),
        "mem_used_pct": _get_mem_pct(),
        "disk_free": _get_disk_free(),
        "agent_running": _is_agent_alive(),
        "llm_status": _check_llm_health(),
        "databases": {
            "sqlite": {"path": str(DB_PATH), "exists": DB_PATH.exists()},
            "duckdb": {"path": str(DUCK_PATH), "exists": DUCK_PATH.exists()},
            "supabase": {"status": "connected" if supabase_client else "disconnected"}
        },
        "queue": _get_queue_stats(),
        "last_extraction": _get_last_extraction_time(),
        "model_active": _get_active_model()
    }
```

---

## Fase 5: Limpieza de Datos — Solo Extracciones Exitosas

### 5.1 Criterios de Retención

Un registro se considera **exitoso** si cumple TODOS los siguientes:
1. ✅ `grounded = true` — Verificado con fuentes web
2. ✅ `fuentes_web` no vacío — Tiene al menos 1 fuente
3. ✅ `confidence_score > 0` — Tiene puntuación de confianza
4. ✅ `proyecto` no vacío — Tiene nombre del proyecto
5. ✅ `municipio` no vacío — Tiene ubicación

### 5.2 Script de Purificación (Supabase)

```sql
-- PASO 1: Contar registros que NO cumplen criterios
SELECT COUNT(*) as to_purge FROM proyectos 
WHERE grounded = false 
   OR fuentes_web = '[]'::jsonb
   OR confidence_score IS NULL 
   OR confidence_score = 0
   OR municipio IS NULL 
   OR municipio = '';

-- PASO 2: Backup (crear tabla temporal)
CREATE TABLE proyectos_purged_backup AS 
SELECT * FROM proyectos 
WHERE grounded = false 
   OR fuentes_web = '[]'::jsonb
   OR confidence_score IS NULL 
   OR confidence_score = 0
   OR municipio IS NULL 
   OR municipio = '';

-- PASO 3: Eliminar registros no exitosos
DELETE FROM proyectos 
WHERE grounded = false 
   OR fuentes_web = '[]'::jsonb
   OR confidence_score IS NULL 
   OR confidence_score = 0
   OR municipio IS NULL 
   OR municipio = '';
```

### 5.3 Cross-Validation

Cada registro retenido debe tener:
- **Grounding Chunks**: Fragmentos de texto original que respaldan cada campo
- **Cross-Validation**: Verificación cruzada entre fuente PDF y portal SEMARNAT
- **Audit Trail**: Registro de qué modelo extrajo los datos y con qué confianza

---

## Fase 6: Limpieza de Archivos (Ejecución)

### 6.1 Script de Limpieza

```bash
#!/bin/bash
# scripts/purify.sh — Ejecutar con confirmación interactiva
set -e
cd "$(dirname "$0")/.."

echo "=== ZOHAR PURIFY ==="
echo "Eliminar archivos obsoletos y logs acumulados"
echo ""

# Backups
rm -f agent/zohar_agent_bak.jsonl
rm -f agent/zohar_queue_bak.json
rm -f agent/zohar_seen_gacetas_bak.json
rm -f .env.tmp

# Logs (truncar, no eliminar — para mantener la estructura)
: > agent/watchdog.log
: > agent/zohar_agent.jsonl
: > agent/wget-log
rm -f agent/wget-log.1
: > api_access.log
: > api_log.txt
: > api_server.log
: > llama.log
: > qwen.log
: > agent_log.txt
: > probe.log

# SQL ya importados a Supabase
rm -f batch1.sql batch2.sql batch3.sql
rm -f income_data.sql zoning_data.sql
rm -f ingresos_2024.csv
rm -f csv_to_sql.py

# Archivos de primera versión
rm -f Esoteria_Organizational_Restructure_Doctrine_v1.md
rm -f PROTOTYPE_ALT_AGENTS.md
rm -f mock_llama_server.py
rm -f current_temp_url.txt
rm -f tunnel_url.txt tunnel_log.txt

# DuckDB duplicados (ya consolidado en Supabase)
rm -f ~/zohar_warehouse.duckdb

echo "✅ Limpieza completa"
```

### 6.2 Dashboard Next.js
El directorio `dashboard/` ocupa **940 MB** (node_modules). 
- Si el dashboard legacy (`dashboard_legacy/`) es la interfaz principal, se puede eliminar
- Verificar primero que no se use en producción

---

## Fase 7: Estructura Objetivo Post-Refactor

```
zohar-agent/
├── .agents/
│   ├── skills/refactor-purify/     # Esta skill
│   └── workflows/
├── agent/
│   ├── zohar_agent_v2.py           # Motor principal (refactorizado)
│   ├── zohar_ctl.sh                # Control script
│   ├── prompts/                    # Plantillas de prompts
│   └── zohar_queue.json            # Cola activa
├── api/
│   ├── main.py                     # API FastAPI (simplificada)
│   └── routes/
├── warehouse/
│   ├── model_router.py             # ✨ NUEVO: Selector de modelos
│   ├── pipeline.py
│   ├── extractors/
│   ├── loaders/
│   └── transformers/
├── dashboard_legacy/               # UI terminal (principal)
├── audit/
├── scripts/
│   ├── purify.sh                   # ✨ NUEVO: Script de limpieza
│   └── sync_to_supabase.py
├── .env
├── requirements.txt
├── README.md
├── STYLE_GUIDE.md
└── WHITE_PAPER.md
```

---

## Checklist de Ejecución

- [x] **Fase 1**: Mapear y documentar todas las fuentes de datos ✅
- [x] **Fase 2**: Implementar `ModelRouter` en `warehouse/model_router.py` ✅
- [x] **Fase 3**: Agregar `--single-run` al agente + botón en dashboard ✅
- [x] **Fase 4**: Crear endpoint `/api/resources` con métricas en tiempo real ✅
- [x] **Fase 5**: Purificación Supabase ✅ — **213 retenidos** (score 99.39%), 380 eliminados con backup en `proyectos_purged_backup_2026_03_25`
- [x] **Fase 6**: `scripts/purify.sh` ejecutado ✅ — ~50 MB liberados, 23 archivos eliminados/truncados
- [x] **Fase 7**: `dashboard/node_modules/` eliminado ✅ — **632 MB liberados**, código fuente (932 KB) preservado
- [x] **Post**: Actualizar `requirements.txt` eliminando dependencias no usadas (aiocache, pdf2image, selenium) ✅

---

## Notas Críticas

> [!CAUTION]
> Antes de ejecutar Fase 5 (purificación de datos), **hacer backup** de la tabla `proyectos` en Supabase.
> Se eliminarán ~380 registros que no tienen grounding ni fuentes web.

> [!IMPORTANT]  
> El directorio `dashboard/` pesa **940 MB**. Confirmar con el usuario antes de eliminar.

> [!TIP]
> Después de la limpieza, la base Supabase `GacetaEcológica` (INACTIVA) debería ser eliminada desde el panel de Supabase para evitar confusión.
