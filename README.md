# zohar-agent

> **ZOHAR_SRE_LEAN · NATIONAL_MONITORING_PIPELINE_V5.0**

Pipeline local de agente IA para monitoreo continuo de la **Gaceta Ecológica Nacional** (SEMARNAT) y extracción estructurada de proyectos de impacto ambiental. Optimizado para hardware AMD A8 con Arch Linux.

---

## ¿Qué hace?

1. **MONITOREA** nuevas publicaciones en la Gaceta Ecológica (`sinat.semarnat.gob.mx`)
2. **DESCARGA** los PDFs de cada Gaceta automáticamente
3. **EXTRAE** con IA (Gemini 2.0 Flash / Vision Multimodal) los datos de cada proyecto:
   - ID de expediente, promovente, estado, municipio, nivel de riesgo
4. **CONSULTA** el portal SEMARNAT para descargar estudios, resúmenes y resolutivos
5. **VISUALIZA** la telemetría ambiental (AQI) y proyectos en un mapa interactivo táctico.
6. **EXPONE** todo en un dashboard web en tiempo real (`localhost:8081` o Vercel)

---

## Arquitectura

```
zohar-agent/
├── api/
│   └── main.py                FastAPI backend + Servicio de Datos CSV/Supabase
├── agent/
│   ├── zohar_agent_v2.py      Agente principal (monitor + extracción multimodal)
│   ├── zohar_queue.json       Cola de procesamiento inteligente
│   └── zohar_ctl.sh           Script de control (start/stop/status/logs)
├── dashboard/                 Frontend "Terminal Táctica"
│   ├── index.html             Dashboard principal (Alpine.js)
│   ├── src/                   Componentes de Próxima Generación (React)
│   │   └── components/
│   │       └── ZoharAirMap.tsx  Mapa interactivo (MapLibre GL JS)
│   └── package.json           Gestión de dependencias (Supabase, React)
└── warehouse/                 Data Lake & Pipeline
    ├── extractors/            Módulos de extracción (PDF/Vision)
    └── loaders/               Carga a PostgreSQL/DuckDB
```

---

## 🌍 Arquitectura Dual de Visualización (v2.4)

ZOHAR opera ahora con dos interfaces especializadas servidas desde el núcleo FastAPI (`localhost:8081`):

1.  **Centro de Operaciones (Tabular)** (`/`): Optimizado para la gestión de datos forenses de la Gaceta Ecológica y auditoría regulatoria.
2.  **Monitor Táctico Geoespacial** (`/aire`): Visualización en tiempo real de contaminantes criterio (PM2.5) utilizando MapLibre GL JS y la telemetría asíncrona de OpenAQ v3.

---

## Stack Técnico

| Componente | Tecnología |
|---|---|
| Infraestructura | **Docker + Docker Compose + Vercel** |
| IA / Inferencia | **Gemini 2.0 Flash (Multimodal) + llama.cpp (Local)** |
| Backend API | **FastAPI + Uvicorn + DuckDB** |
| Frontend UI | **Alpine.js + TypeScript + CSS Vanilla** |
| Visualización GIS | **MapLibre GL JS + react-map-gl** |
| Base de Datos | **Supabase (PostgreSQL) + SQLite (Cold Storage)** |
| Lenguajes | **Python 3.12 + TypeScript 5.x** |

---

## Visualización Táctica Geoespacial (New v2.4)

ZOHAR ahora incluye `ZoharAirMap.tsx`, un componente de visualización de alto rendimiento diseñado para monitorear el Índice de Calidad del Aire (AQI) en Baja California Sur.

- **Motor**: MapLibre GL JS para renderizado WebGL fluido de miles de puntos.
- **Estética**: Mapa base "CartoDB Dark Matter" modificado para eliminar ruido visual.
- **Escala Neutra / Neón**: Mapeo de PM2.5 a una paleta de alto contraste (`#00FF41` safe a `#FF0000` crítico).
- **Telemetría**: Integración de datos de estaciones OpenAQ y sensores terrestres propios.

---

## Características de Inteligencia (v2.4)

| Módulo | Funcionalidad | Estado |
|---|---|---|
| **Vision Multimodal** | Uso de Gemini 2.0 Flash para procesar tablas y PDFs complejos como imagen. | ✅ Producción |
| **Grounding Ambiental** | Verificación de datos contra el índice de SEMARNAT y búsqueda en tiempo real. | ✅ Producción |
| **ZoharAirMap** | Visualización geoespacial táctica de contaminantes (PM2.5, NO2, O3). | ✅ Producción |
| **Geostadística BCS** | Transformación de municipios a coordenadas precisas via GeoTransformer. | ✅ Producción |

---

## Despliegue Híbrido (Local + Vercel)

El sistema opera bajo una arquitectura de **Observabilidad Aterrizada**:

1.  **Procesamiento Local**: El motor de extracción (`agent/zohar_agent_v2.py`) corre en tu hardware local para aprovechar la potencia del LLM y acceder a la red gubernamental. Los datos se sincronizan automáticamente con **Supabase**.
2.  **Dashboard en Vercel**: El dashboard (`/dashboard`) se despliega en Vercel para acceso global. Este lee directamente de Supabase ("información aterrizada"), permitiendo monitorear los resultados sin exponer tu infraestructura local.

Para desplegar el dashboard en Vercel:
```bash
# Solo se requiere la carpeta dashboard y vercel.json
vercel deploy
```

---

## Fuentes de Datos

- **Gaceta Ecológica**: https://www.semarnat.gob.mx/gobmx/transparencia/gaceta.html
- **Índice PDFs**: http://sinat.semarnat.gob.mx/Gaceta/gacetapublicacion/?ai={año}
- **Portal Consulta**: https://app.semarnat.gob.mx/consulta-tramite/#/portal-consulta

---

## Licencia

MIT — Software libre para monitoreo ambiental ciudadano.
