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
| IA / Inferencia | [llama.cpp](https://github.com/ggerganov/llama.cpp) + Qwen 2.5 1.5B Q4_K_M |
| Backend API | FastAPI + Uvicorn |
| Frontend | Alpine.js + TailwindCSS CDN |
| Extracción PDF | pdftotext (poppler) |
| Base de datos | CSV + JSON Lines (sin dependencias externas) |
| Grafo de relaciones | Triples RDF-like `.triples` |
| Hardware objetivo | AMD A8-7410 · 4GB RAM · Arch Linux |

---

## Requisitos

```bash
# Sistema
pdftotext    # pacman -S poppler
sensors      # pacman -S lm_sensors
jq           # pacman -S jq

# Python (stdlib puro en el agente — sin pip adicional)
# API requiere:
pip install fastapi uvicorn
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

~/zohar_historico_proyectos.csv    Base de datos nacional
~/zohar_grafo.triples              Grafo de relaciones (promovente, estado)
~/zohar-agent/agent/
├── zohar_queue.json               Queue persistente de IDs
├── zohar_seen_gacetas.json        Hashes para detectar cambios
└── zohar_agent.jsonl              Log estructurado JSON Lines
```

---

## Fuentes de Datos

- **Gaceta Ecológica**: https://www.semarnat.gob.mx/gobmx/transparencia/gaceta.html
- **Índice PDFs**: http://sinat.semarnat.gob.mx/Gaceta/gacetapublicacion/?ai={año}
- **Portal Consulta**: https://app.semarnat.gob.mx/consulta-tramite/#/portal-consulta

---

## Licencia

MIT — Software libre para monitoreo ambiental ciudadano.
