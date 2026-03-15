# zohar-agent

> **ZOHAR_SRE_LEAN · NATIONAL_MONITORING_PIPELINE_V5.0**

Pipeline local de agente IA para monitoreo continuo de la **Gaceta Ecológica Nacional** (SEMARNAT) y extracción estructurada de proyectos de impacto ambiental. Optimizado para hardware AMD A8 con Arch Linux.

---

## ¿Qué hace?

1. **MONITOREA** nuevas publicaciones en la Gaceta Ecológica (`sinat.semarnat.gob.mx`)
2. **DESCARGA** los PDFs de cada Gaceta automáticamente
3. **EXTRAE** con IA (Qwen 2.5 1.5B / llama.cpp) los datos de cada proyecto:
   - ID de expediente, promovente, estado, municipio, nivel de riesgo
4. **CONSULTA** el portal SEMARNAT para descargar estudios, resúmenes y resolutivos
5. **EXPONE** todo en un dashboard web en tiempo real (`localhost:8081`)

---

## Arquitectura

```
zohar-agent/
├── api/
│   └── zohar_api.py           FastAPI backend + dashboard server (puerto 8081)
├── agent/
│   ├── zohar_agent_v2.py      Agente principal (monitor + extracción)
│   ├── zohar_queue_inspector.py  TUI monitor de la queue
│   └── zohar_ctl.sh           Script de control (start/stop/status/logs)
└── dashboard/
    └── index.html             Dashboard Alpine.js + TailwindCSS
```

---

## Stack Técnico

| Componente | Tecnología |
|---|---|
| Infraestructura | **Docker + Docker Compose** |
| CI/CD | **GitHub Actions (CDD - Continuous Quality)** |
| IA / Inferencia | [llama.cpp](https://github.com/ggerganov/llama.cpp) + Qwen / Mistral / Gemini |
| Backend API | FastAPI + Uvicorn |
| Frontend | Alpine.js + TailwindCSS |
| Extracción | Poppler + Selenium + Gemini Grounding |
| Base de Datos | SQLite (Gold) + CSV (Silver) |

---

## Despliegue Profesional (Estrategia A)

Para un entorno de producción o de desarrollo profesional, se recomienda usar Docker:

```bash
# 1. Configurar variables de entorno
cp .env.example .env # y editar según sea necesario

# 2. Levantar servicios (Agent + API)
docker-compose up -d --build

# 3. Ver logs unificados
docker-compose logs -f
```

### Garantía de Calidad (TDD)
El proyecto utiliza un enfoque de **Continuous Quality Assurance**. Puedes ejecutar la suite de pruebas localmente:

```bash
# Ejecutar suite Red/Green
pytest test_zohar_agent.py test_zohar_api.py
```

---

## Inicio Rápido

```bash
# 1. Clonar
git clone https://github.com/Gorodev-lab/zohar-agent.git
cd zohar-agent

# 2. Arrancar llama-server con Qwen 2.5 1.5B en puerto 8001
# (requiere llama.cpp compilado y el modelo .gguf)

# 3. Arrancar el dashboard API
cd api && pip install fastapi uvicorn && python zohar_api.py &

# 4. Abrir http://localhost:8081

# 5. Correr el agente
cd agent
bash zohar_ctl.sh status      # ver estado
bash zohar_ctl.sh dry-run     # probar sin escribir al CSV
bash zohar_ctl.sh start       # ciclo de extracción real
bash zohar_ctl.sh start-daemon # modo 24/7
```

---

## Características de Inteligencia (Fase 2 & 3)

| Módulo | Funcionalidad | Estado |
|---|---|---|
| **Agentic Chain of Custody** | Captura de razonamiento LLM y extractos de fuente (Grounding) por cada registro. | ✅ Producción |
| **Optimización Predictiva** | Deduplicación semántica cross-year para evitar conteo doble de proyectos recurrentes. | ✅ Producción |
| **Gobernanza de Datos** | Dashboard HITL (Human-in-the-Loop) para auditoría manual de registros. | ✅ Producción |
| **Señales de Alerta** | Detección automática de anomalías (ej. Alta Densidad de Proponentes). | ✅ Producción |

---

## Comandos del Agente

| Comando | Descripción |
|---|---|
| `zohar_ctl.sh start` | Ciclo único: detectar + extraer |
| `zohar_ctl.sh start-daemon` | Monitoreo continuo (polling cada N min) |
| `zohar_ctl.sh dry-run` | Prueba sin escribir al CSV ni al grafo |
| `zohar_ctl.sh stop` | Detener limpiamente (SIGTERM) |
| `zohar_ctl.sh status` | Estado, queue, CSV rows, gacetas vistas |
| `zohar_ctl.sh logs` | Stream de logs en tiempo real |
| `zohar_ctl.sh inspect` | Dashboard TUI de la queue |
| `zohar_ctl.sh dedup-rebuild` | Escanea el histórico para vincular duplicados semánticos |
| `zohar_ctl.sh retry-failed` | Resetear IDs fallidos a pendiente |
| `zohar_ctl.sh reset-seen` | Forzar re-escaneo de todas las gacetas |

---

## Datos Generados

```
~/gaceta_work/
├── 2026/
│   ├── gaceta_0001-26.pdf     PDFs originales de SEMARNAT
│   ├── gaceta_0001-26.txt     Texto extraído
│   └── ...
└── documentos/
    └── {ID_PROYECTO}/
        ├── estudio.pdf        Estudio de Impacto Ambiental
        ├── resumen.pdf        Resumen Ejecutivo
        └── resolutivo.pdf     Resolución SEMARNAT

## Despliegue Híbrido (Local + Vercel)

El sistema opera bajo una arquitectura de **Observabilidad Aterrizada**:

1.  **Procesamiento Local**: El motor de extracción (`agent/zohar_agent_v2.py`) corre en tu hardware local para aprovechar la potencia del LLM y acceder a la red gubernamental. Los datos se sincronizan automáticamente con **Supabase**.
2.  **Dashboard en Vercel**: El dashboard (`/dashboard`) se despliega en Vercel para acceso global. Este lee directamente de Supabase ("información aterrizada"), permitiendo monitorear los resultados sin exponer tu infraestructura local.

Para desplegar el dashboard en Vercel:
```bash
# Solo se requiere la carpeta dashboard y vercel.json
vercel deploy
```
```

---

## Fuentes de Datos

- **Gaceta Ecológica**: https://www.semarnat.gob.mx/gobmx/transparencia/gaceta.html
- **Índice PDFs**: http://sinat.semarnat.gob.mx/Gaceta/gacetapublicacion/?ai={año}
- **Portal Consulta**: https://app.semarnat.gob.mx/consulta-tramite/#/portal-consulta

---

## Licencia

MIT — Software libre para monitoreo ambiental ciudadano.
