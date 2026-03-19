# ZOHAR AGENT v2.4: Libro Blanco de Inteligencia Ambiental
> **Arquitectura de Monitoreo Nacional y Visualización Táctica de Alta Fidelidad**

## 1. Resumen Ejecutivo
Zohar Agent es un ecosistema de inteligencia artificial diseñado para el monitoreo, extracción y verificación de proyectos de impacto ambiental en México (SEMARNAT). La versión 2.4 marca la integración de **Visualización Geoespacial Táctica** y la consolidación de la **visión multimodal nativa** impulsada por Google Gemini, permitiendo una precisión sin precedentes en la captura y representación de datos ambientales.

## 2. Pilares de la Versión 2.4

### 2.1 Visualización Táctica GIS (ZoharAirMap)
Se ha implementado una capa de visualización de alto rendimiento utilizando **MapLibre GL JS** y **React**:
*   **Data-to-Ink Ratio**: Eliminación de ruido visual cartográfico (nombres de calles, puntos de interés comerciales) para centrar la atención exclusivamente en la telemetría de contaminantes.
*   **Escala Crítica Neón**: Mapeo de valores PM2.5 a una paleta de alto contraste optimizada para terminales tácticas (`#00FF41` safe a `#FF0000` crítico).
*   **Rendimiento Multipolar**: Capacidad de renderizar miles de puntos de datos (OpenAQ + Sensores Propios) con 60 FPS garantizados mediante WebGL.

### 2.2 Tubería de Visión Forense (Gemini 2.0 Flash)
Superando las limitaciones del OCR tradicional, el agente utiliza ahora **Gemini 2.0 Flash** en modo multimodal:
*   **Captura de Documentos**: Los PDFs de la Gaceta Ecológica se procesan como imágenes para interpretar estructuras visuales complejas (tablas anidadas, firmas, sellos).
*   **Razonamiento Espacial**: La IA identifica la ubicación de los datos clave no solo por texto, sino por su posición estructural en el documento oficial.

### 2.3 Geo-Estadística Aterrizada (GeoTransformer)
Integración de un catálogo municipal preciso para Baja California Sur:
*   **Desambiguación Territorial**: Conversión automática de menciones textuales de municipios a coordenadas geográficas precisas (Lat/Lng) mediante un motor de transformación local (`GeoTransformer`).
*   **Grounding Geográfico**: Verificación de coherencia entre el nombre del proyecto y su ubicación reportada en la Gaceta.

## 3. Arquitectura Técnica

### 3.1 Stack de Confiabilidad
*   **Inferencia Híbrida**: Gemini 2.0 Flash (Nube) para visión compleja y modelos locales (.gguf) para tareas de clasificación de bajo costo.
*   **Almacenamiento Inteligente**: Niveles de datos en **Supabase** (PostgreSQL) para visualización en tiempo real y **DuckDB** para analítica pesada local.
*   **Pipeline de Datos**: Sistema de carga asíncrona optimizado para evitar latencia en el dashboard durante ciclos de extracción masiva.

### 3.2 Despliegue en el Edge y Operación Dual
*   **Dashboards Divergentes**: Operación paralela del Centro de Operaciones Tabular (`/`) para auditoría y el Monitor Táctico Geoespacial (`/aire`) para telemetría inmersiva.
*   **Nodos de Datos**: Sincronización cifrada entre infraestructura local (Extracción masiva) y Vercel (Visualización global).

## 4. Protocolo de Inteligencia (CoT)
El proceso de extracción sigue un rigor doctoral:
1.  **Detección**: Identificación de nuevas publicaciones en la Gaceta Ecológica.
2.  **Visión Multimodal**: Extracción de datos tabulares desde la imagen del documento.
3.  **Cross-Validation**: Cotejo de la información con el histórico de Supabase para evitar duplicidad semántica.
4.  **Geolocalización**: Transformación de la ubicación a coordenadas para el `ZoharAirMap`.

---
**ZOHAR INTEL 2026**
*Soberanía de Datos · Vigilancia Ambiental · Ingeniería de Visualización Crítica*
