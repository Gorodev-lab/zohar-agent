# ZOHAR AGENT v2.3: Libro Blanco de Inteligencia Ambiental
> **Arquitectura de Monitoreo Nacional y Extracción de Alta Fidelidad**

## 1. Resumen Ejecutivo
Zohar Agent es un ecosistema de inteligencia artificial diseñado para el monitoreo, extracción y verificación de proyectos de impacto ambiental en México (SEMARNAT). La versión 2.3 marca la transición hacia una **localización total al español** y la implementación de una tubería de **visión multimodal nativa** impulsada por Google Gemini, permitiendo una precisión sin precedentes en la captura de datos de fuentes gubernamentales históricamente complejas.

## 2. Pilares de la Versión 2.3

### 2.1 Localización y Experiencia de Usuario (UX)
Se ha implementado una traducción integral de extremo a extremo:
*   **Interfaz del Dashboard:** Visualización en tiempo real con terminología técnica en español.
*   **Logs y Telemetría:** Mensajería operativa localizada para facilitar el mantenimiento y la supervisión.
*   **Inteligencia Nativa:** Los modelos de lenguaje han sido reconfigurados con prompts especializados para generar razonamiento (CoT) y síntesis técnica directamente en español.

### 2.2 Tubería de Visión Forense (Gemini Vision)
Superando las limitaciones del OCR tradicional, el agente utiliza ahora **Gemini 2.0 Flash** en modo multimodal:
*   **Captura de Documentos:** Los PDFs degradados o con tablas complejas se procesan como imágenes de alta resolución (200 DPI).
*   **Análisis Multimodal:** La IA "ve" el documento, interpretando la estructura visual de las Gacetas Ecológicas para extraer inteligencia prístina donde el texto plano fallaría.

### 2.3 Protocolo de Fundamentación (Grounding)
Integración nativa con **Google Search Grounding**:
*   **Verificación en Tiempo Real:** Cada registro extraído es contrastado con fuentes web externas para asegurar la veracidad de coordenadas, promoventes y estados de los proyectos.
*   **Score de Confianza:** Un sistema de pesaje dinámico (FIELD_WEIGHTS) califica cada registro, asegurando que solo la información de alta calidad llegue al libro de inteligencia.

## 3. Arquitectura Técnica

### 3.1 Stack de Confiabilidad
*   **Motor de Inferencia:** Híbrido entre **Gemini 2.5/2.0** (Nube) y **Mistral/Qwen** (Local) para garantizar continuidad operativa ante fallos de red.
*   **Base de Datos:** Arquitectura de niveles con **SQLite** para datos operativos y **DuckDB** para analítica de alto rendimiento (Data Warehousing).
*   **Sincronización:** Espejo automático con **Supabase** para visualización global desde Vercel sin comprometer la seguridad local.

### 3.2 Optimización de Hardware (Ryzen 5)
El agente incluye un **Monitor Térmico Inteligente** que ajusta la carga de procesamiento según la temperatura del CPU (Cool-down dinámico), garantizando la longevidad del hardware en operaciones 24/7.

## 4. Protocolo de Inteligencia (CoT)
El proceso de extracción sigue un rigor doctoral:
1.  **Descubrimiento:** Detección de IDs únicos en documentos oficiales.
2.  **Visión/OCR:** Recuperación de fragmentos tabulares mediante visión multimodal.
3.  **Razonamiento:** Bloques `<razonamiento>` donde la IA explica su lógica de desambiguación.
4.  **Auditoría:** Validación cruzada de códigos postales y catálogos INEGI para coherencia geográfica.

---
**ZOHAR INTEL 2026**
*Soberanía de Datos · Vigilancia Ambiental · Ingeniería de Prompts Avanzada*
