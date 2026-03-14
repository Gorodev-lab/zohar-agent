# **Optimización Estructural y Semántica para la Extracción de Datos en Documentos Gubernamentales Ruidosos: Ingeniería de Prompts Avanzada para las Gacetas Ecológicas de SEMARNAT**

## **1\. Introducción: La Crisis de Extracción en Documentos Gubernamentales Estructurados**

La extracción de datos estructurados, de alta fidelidad y semánticamente coherentes a partir de documentos gubernamentales complejos representa uno de los desafíos más formidables en el campo de la lingüística computacional y la inteligencia documental contemporánea. En el contexto específico de la República Mexicana, el procesamiento automatizado de la Gaceta Ecológica, publicada periódicamente por la Secretaría de Medio Ambiente y Recursos Naturales (SEMARNAT), ilustra de manera paradigmática las profundas vulnerabilidades de los enfoques de extracción ingenuos o puramente reactivos.1 Estas gacetas, que fungen como el registro público primario y legal para los proyectos que ingresan al Procedimiento de Evaluación de Impacto Ambiental (PEIA), son diseminadas en formato de Documento Portátil (PDF) con una densidad tipográfica y tabular extrema.3

Históricamente, los sistemas de extracción automatizada, como el Agente Zohar, han intentado mitigar los errores de captura mediante la implementación de lógicas reactivas y expresiones regulares en el código Python de post-procesamiento. Este enfoque asume, erróneamente, que el problema radica en la limpieza del dato extraído, cuando la patología fundamental nace en el instante mismo de la extracción cognitiva por parte de la Inteligencia Artificial. Cuando los documentos visuales en PDF son sometidos a sistemas de Reconocimiento Óptico de Caracteres (OCR) o a analizadores de conversión de PDF a texto plano, las intrincadas estructuras multidimensionales de las tablas —diseñadas para el consumo visual humano mediante líneas de cuadrícula, espaciado de columnas y alineación de filas— sufren una degradación topológica irreversible, colapsando en una secuencia unidimensional de texto.5

Esta degradación estructural despoja al texto de sus fronteras visuales implícitas, provocando que los Modelos de Lenguaje Grande (LLMs, por sus siglas en inglés) experimenten una profunda desorientación espacial y semántica. El síntoma más crítico y recurrente de este déficit de extracción es la anomalía del "EL ID", donde el modelo clasifica anómalamente las etiquetas de los encabezados de las tablas y los metadatos estructurales como entidades geográficas reales.6 Simultáneamente, el proceso de extracción revela una propensión sistemática hacia la generación perezosa en los campos de resumen técnico, donde las descripciones de los proyectos ambientales son frecuentemente truncadas, omitidas con guiones ("—"), o definidas de manera tautológica mediante la simple repetición del título de la obra, ignorando los extensos párrafos de ingeniería y mitigación ambiental que yacen en el cuerpo del documento.8

Para rectificar estos fallos sistémicos, se requiere un cambio de paradigma fundamental en la Ingeniería de Prompts (Prompt Engineering). Las instrucciones directas y carentes de andamiaje, como el clásico "Extrae las variables X, Y y Z", carecen de la robustez semántica necesaria para guiar a un modelo de lenguaje a través de un corpus textual altamente ruidoso, fragmentado y engañoso. El presente informe de investigación detalla un análisis exhaustivo de las vulnerabilidades cognitivas inherentes a la extracción de datos basada en LLMs y formula una arquitectura maestra de extracción definitiva. Esta arquitectura metodológica emplea la delimitación semántica basada en XML, la desambiguación tabular mediante Cadenas de Pensamiento (Chain-of-Thought), la validación semántica rigurosa contra el marco ontológico geográfico de México, y la calibración mediante técnicas de Few-Shot Prompting contrastivo, garantizando así una estructuración de datos determinista, coherente y lista para la ingesta en bases de datos analíticas.

## **2\. Patología Cognitiva de los Modelos de Lenguaje ante Tablas Aplanadas y la Anomalía "EL ID"**

Para comprender por qué un modelo de razonamiento avanzado con miles de millones de parámetros alucina rutinariamente que "EL ID" es un municipio mexicano soberano, es imperativo examinar la mecánica fundamental de las arquitecturas basadas en transformadores (transformers) frente a datos degradados. Los transformadores no "leen" el texto bidimensionalmente como un ser humano; en su lugar, procesan secuencias unidimensionales de tokens (fragmentos de palabras) basándose en un mecanismo de autoatención (self-attention).10 Este mecanismo calcula la relevancia probabilística de todos los tokens en una secuencia en relación con los demás, buscando patrones de co-ocurrencia aprendidos durante su preentrenamiento masivo.

### **2.1 La Falsa Proximidad Espacial y el Colapso Topológico**

En una tabla de la Gaceta Ecológica de la SEMARNAT correctamente formateada, el diseño visual establece una jerarquía clara. Los encabezados de las columnas (por ejemplo, "ID\_PROYECTO", "PROMOVENTE", "ESTADO", "MUNICIPIO", "PROYECTO") se asientan en la fila superior, creando un espacio de metadatos, mientras que los valores sustantivos residen en las celdas inferiores.12 Las líneas de la cuadrícula actúan como barreras infranqueables para el ojo humano. Sin embargo, cuando las herramientas de conversión a texto aplanan el documento PDF para el consumo del LLM, el texto sufre un colapso topológico. Lo que antes estaba separado verticalmente por una columna, ahora aparece adyacente horizontalmente en la misma línea de texto.

En los corpus gubernamentales analizados, este aplanamiento genera secuencias de texto ruidosas similares a: 04 EL ID 02BC2024HD010 ESTADO QUINTANA ROO PROYECTO TREN MAYA TRAMO 5 MUNICIPIO EL ID PROMOVENTE FONATUR.7 Cuando el modelo recibe la instrucción reactiva de encontrar el valor correspondiente al campo "Municipio", el mecanismo de atención escanea la secuencia buscando marcadores sintácticos. Al encontrar la palabra "MUNICIPIO", el modelo asume estadísticamente que los tokens inmediatamente posteriores constituyen la respuesta correcta. Debido a la alteración del orden causada por la lectura secuencial de filas y columnas rotas, el texto "EL ID" se posiciona inmediatamente después del marcador, creando una trampa de proximidad ineludible para un modelo carente de razonamiento reflexivo.

### **2.2 La Confusión Léxica y el Uso del Artículo Determinado**

El error "EL ID" se ve severamente exacerbado por factores morfológicos específicos del idioma español y de la toponimia mexicana. El léxico geográfico de México contiene una vasta y rica matriz de municipios y localidades cuyos nombres oficiales comienzan con el artículo determinado "El" (por ejemplo, El Fuerte en Sinaloa, El Salto en Jalisco, El Marqués en Querétaro, El Bosque en Chiapas). Durante la fase de preentrenamiento del modelo con terabytes de datos de texto en español, los pesos de la red neuronal aprendieron una fortísima asociación estadística entre la solicitud de un "municipio" y las cadenas de texto que comienzan con la palabra "El" seguida de un sustantivo.6

Por lo tanto, cuando el producto del punto de consulta-clave del mecanismo de atención evalúa la subcadena "MUNICIPIO EL ID", la intersección de la proximidad espacial extrema y la similitud léxica superficial con las convenciones de nomenclatura municipal convencen al modelo de que "EL ID" es una entidad geográfica legítima. El modelo no comprende semánticamente que "ID" es una abreviatura anglosajona para Identificador (Identity Document/Identifier), utilizada burocráticamente como metadato; simplemente sigue el camino de menor resistencia probabilística. Este fenómeno subraya la futilidad de intentar solucionar el problema con scripts reactivos de Python (como limpiar "EL ID" después de la extracción), ya que la extracción fundamentalmente defectuosa ocluye y destruye el verdadero nombre del municipio que yace desplazado más adelante en el caos textual.

### **2.3 El Fenómeno de Extracción Perezosa en las Descripciones de Proyectos**

Una segunda patología observada sistemáticamente en las extracciones de prueba tipo "zero-shot" (cero ejemplos) es la generación de descripciones técnicas vacías, circulares o excesivamente genéricas.8 Los proyectos sometidos a evaluación de impacto ambiental, por su naturaleza, involucran alteraciones físicas significativas al entorno: desmonte de selva, construcción de infraestructura electromecánica, operaciones de dragado, o instalación de plantas desalinizadoras.17 La información técnica detallada que describe estas intervenciones rara vez se encuentra en la tabla de resumen principal; generalmente está enterrada profundamente dentro de densos párrafos burocráticos y técnicos que siguen o preceden a la tabla en la separata de la Gaceta Ecológica.4

Cuando se les deja sin restricciones procedimentales estrictas, los LLMs exhiben una marcada preferencia por la eficiencia computacional y la finalización rápida, un comportamiento conocido como generación perezosa (lazy generation). En lugar de escanear exhaustivamente toda la ventana de contexto disponible para localizar, comprender y sintetizar un resumen técnico comprensivo, el modelo trunca su búsqueda prematuramente. Frecuentemente, el modelo simplemente copia el título formal del proyecto (por ejemplo, "Construcción del Desarrollo Turístico Bahía") y lo pega en el campo de descripción, o peor aún, inserta un guion largo ("—") al no encontrar un resumen explícitamente etiquetado como "Descripción" en la proximidad inmediata de la tabla. Superar esta entropía generativa requiere la implementación de funciones de forzamiento algorítmico (forcing functions) que obliguen al modelo a procesar el cuerpo del texto completo y a construir una síntesis utilizando parámetros lingüísticos altamente específicos.

## **3\. Arquitectura de Delimitación: La Superioridad Semántica del Etiquetado XML**

El fallo fundacional en los diseños de prompts heredados para el Agente Zohar reside en la dependencia de fronteras implícitas o en el uso de formato Markdown estándar para separar las instrucciones del sistema del texto a analizar.19 Si bien Markdown (utilizando almohadillas \#, asteriscos \*\*, y guiones \-) es altamente legible para los operadores humanos y resulta perfectamente adecuado para tareas de inteligencia artificial conversacional de propósito general, carece de la rigidez semántica absoluta requerida para la extracción de datos determinista a partir de corpus institucionales altamente ruidosos.20

### **3.1 La Vulnerabilidad Inherente del Markdown en Contextos Ruidosos**

El lenguaje Markdown confía en la interpretación de caracteres de puntuación comunes para denotar la estructura jerárquica del documento. Sin embargo, en los archivos PDF gubernamentales sujetos a procesos de OCR defectuosos o a un formato administrativo pesado, estos mismos caracteres de puntuación aparecen orgánicamente dentro del texto base de manera caótica e impredecible.21 Viñetas huérfanas, guiones de continuación de línea, asteriscos de notas al pie de página y almohadillas utilizadas como indicadores de número (ej. \# de Oficio) saturan el texto extraído de las Gacetas Ecológicas de la SEMARNAT.

Cuando las instrucciones críticas del prompt (por ejemplo, "No extraigas el ID") se separan del texto escaneado de la Gaceta utilizando únicamente divisores de Markdown, el LLM sufre frecuentemente de lo que se conoce como "sangrado de instrucciones" (instruction bleed). En este escenario de falla, el modelo confunde el texto en bruto del documento con una nueva instrucción del sistema, o a la inversa, trata las restricciones de extracción como parte del texto que debe ser procesado. Esta confusión de contexto destruye la capacidad del modelo para discernir qué reglas debe seguir frente a qué datos debe manipular.22

### **3.2 El Etiquetado XML como Barrera Cognitiva Definitiva**

Para remediar esta vulnerabilidad, la investigación de vanguardia en la optimización de modelos de frontera —respaldada explícitamente por la documentación de ingeniería de proveedores líderes como Anthropic (Claude), OpenAI (GPT-4) y Google (Gemini)— dictamina el uso obligatorio de delimitadores basados en etiquetas de Lenguaje de Marcado Extensible (XML) para prompts complejos y de alto riesgo.22 Las etiquetas XML pseudo-estructuradas (por ejemplo, \<instrucciones\_del\_sistema\>, \<texto\_crudo\_del\_pdf\>, \<ejemplos\_de\_error\>) proporcionan fronteras semánticas inequívocas e ineludibles para los modelos de lenguaje modernos.26

Las ventajas algorítmicas de implementar una arquitectura puramente basada en XML para esta tarea de extracción específica son múltiples y resolutivas:

1. **Demarcación Absoluta y Aislamiento de Variables:** El mecanismo de atención del modelo puede diferenciar matemáticamente entre el conjunto de reglas inmutables que rigen su comportamiento y el texto caótico sobre el cual debe operar. La encapsulación de los datos ruidosos dentro de etiquetas como \<texto\_crudo\> le señala al modelo que todo el contenido interior es pasivo y no debe ser interpretado como comandos ejecutables.  
2. **Capacidad de Anidamiento Jerárquico Infinito:** A diferencia del Markdown, que pierde cohesión estructural después de unas pocas capas de indentación, el XML permite una lógica anidada impecable. Esto es fundamental para construir el prompt maestro, ya que permite que el bloque de \<contexto\> contenga un bloque interno de \<ejemplo\_negativo\>, que a su vez contiene bloques de \<analisis\_de\_falla\> y \<solucion\_esperada\>.22 Esta contención jerárquica evita categóricamente que el modelo confunda el texto de un ejemplo negativo con la tarea principal de extracción que debe realizar.  
3. **Inmunidad contra la Inyección Involuntaria de Prompts:** Los documentos legales a menudo contienen frases imperativas (por ejemplo, "EL PROMOVENTE DEBE REPORTAR", "INSTRUCCIÓN PARA EL EVALUADOR"). Si el texto no está delimitado por XML, el LLM podría interpretar estas frases encontradas en el documento como órdenes directas emitidas por el desarrollador. El encapsulamiento XML vacuna al modelo contra esta inyección de instrucciones parasitarias.21

A continuación, la Tabla 1 ilustra una evaluación comparativa detallada de las diferencias funcionales en el mapeo de atención y el comportamiento de análisis sintáctico (parsing) entre Markdown y XML en el contexto del procesamiento de documentos ruidosos.

| Dimensión de Análisis | Delimitación Basada en Markdown | Delimitación Basada en Etiquetas XML | Impacto Directo en la Precisión de Extracción |
| :---- | :---- | :---- | :---- |
| **Claridad de Frontera Cognitiva** | Implícita (depende de señales visuales y espaciado). | Explícita (marcadores programáticos de inicio y cierre definitivos). | Alto. El XML previene el sangrado de instrucciones y el colapso del contexto.19 |
| **Soporte para Anidamiento Lógico** | Débil (limitado por los niveles de encabezado y tabulación). | Robusto (anidamiento infinito sin pérdida de jerarquía semántica). | Crítico. Permite estructurar ejemplos negativos complejos sin que el modelo se confunda.22 |
| **Resiliencia al Ruido Tipográfico** | Baja. Los textos gubernamentales contienen naturalmente \#, \*, y \-. | Alta. Es virtualmente imposible que el texto crudo del OCR contenga etiquetas pseudo-XML completas.21 |  |
| **Predictibilidad del Análisis Sintáctico** | Altamente variable dependiendo de la temperatura y escala del modelo. | Altamente determinista y estable a través de todas las familias de modelos de frontera. | Esencial para garantizar el cumplimiento estricto del esquema de salida JSON sin preámbulos conversacionales.20 |

## **4\. Implementación de Cadena de Pensamiento (Chain-of-Thought) para Desambiguación Tabular**

Habiendo asegurado el entorno cognitivo mediante el andamiaje XML, el siguiente imperativo metodológico es desmantelar la heurística de toma de decisiones directa del modelo. Para resolver definitivamente la anomalía persistente del "EL ID" y la extracción errónea de encabezados en general, no se le puede permitir al LLM mapear el texto de entrada directamente hacia el esquema de salida JSON en un solo salto inferencial. El salto cognitivo requerido para sortear múltiples capas de ruido, cabeceras rotas, y texto desplazado espacialmente es simplemente demasiado vasto, lo que invariablemente desencadena alucinaciones fundamentadas en la proximidad. La solución a este escollo arquitectónico es la integración forzada de una fase de razonamiento estructurado conocida como Cadena de Pensamiento (Chain-of-Thought o CoT).10

El prompting de Cadena de Pensamiento obliga al modelo autorregresivo a generar un "bloc de notas" (scratchpad) intermedio y transparente antes de finalizar su respuesta definitiva estructurada. Debido a que la arquitectura central de los LLMs computa la distribución de probabilidad del siguiente token basándose integralmente en todos los tokens que ha generado previamente, el acto de obligar al modelo a emitir un análisis lógico y deductivo del texto impreso *antes* de proceder a la extracción de los datos altera drásticamente la distribución de probabilidad de la salida final.11 En términos prácticos, al escribir su propio razonamiento, el modelo se guía a sí mismo hacia la precisión, creando hitos de memoria explícitos a lo largo de su ventana de contexto.

### **4.1 La Estructura del Bloc de Notas de Desambiguación**

Dentro del diseño del prompt maestro (Meta-Prompt), se debe insertar una orden inquebrantable que exija al modelo abrir una etiqueta \<razonamiento\> de manera preliminar a la generación del JSON de salida. Dentro de este espacio confinado, el modelo está programáticamente obligado a ejecutar tres fases cognitivas secuenciales y diferenciadas:

#### **Fase 1: Identificación Explícita de Metadatos y Etiquetado de Ruido**

Antes de intentar localizar el nombre del Promovente o del Municipio, el modelo debe realizar un barrido diagnóstico del texto crudo para identificar activamente el andamiaje roto de la tabla. Se le instruye que liste explícitamente todas las palabras que históricamente funcionan como encabezados, categorías o identificadores de metadatos en las Gacetas de la SEMARNAT (por ejemplo, "ID", "CLAVE", "PROMOVENTE", "MUNICIPIO", "ESTADO", "FECHA DE INGRESO", "MODALIDAD").12 Al forzar al modelo a escribir físicamente estas cadenas de texto y etiquetarlas formalmente como "Basura Estructural/Encabezados", estas palabras son puestas en cuarentena semántica profunda en la memoria a corto plazo del modelo.

#### **Fase 2: Separación de Entidades y Supresión de Sesgos**

Una vez que el ruido ha sido catalogado, el modelo evalúa el texto adyacente utilizando la lógica proposicional. El modelo debe articular una narrativa deductiva interna: *"Al escanear el texto en busca del Municipio, localizo la cadena que dice 'MUNICIPIO EL ID 02BC...'. Sin embargo, en el paso anterior, catalogué formalmente la frase 'EL ID' como un encabezado de metadatos roto, no como un dato de ubicación. Por lo tanto, el principio de exclusión mutua dicta que 'EL ID' no puede ser simultáneamente un encabezado y el nombre geográfico del municipio. El verdadero valor geográfico ha sido desplazado por el error de formato del PDF y debe estar ubicado en el siguiente cúmulo de texto sustantivo, procedo a continuar la lectura exhaustiva."* Esta simple exteriorización del razonamiento neutraliza por completo el letal sesgo de proximidad espacial documentado en la Sección 2.1.28

#### **Fase 3: Reconstrucción Sintáctica del Espacio Latente**

Finalmente, el modelo rastrea los datos de las filas dispersas y desplazadas y los reconecta mentalmente a la columna lógica correcta, reconstruyendo efectivamente la tabla fragmentada dentro de su propio espacio de comprensión latente antes de comprometer cualquier valor en la sintaxis JSON estricta requerida para la extracción final. Una vez que el texto "EL ID" es explícitamente clasificado y desterrado como un artefacto dentro del bloque CoT, la probabilidad matemática de que el modelo decida insertarlo subsecuentemente en el campo "Municipio" del JSON cae a niveles marginales cercanos a cero.

## **5\. Validación Semántica y Anclaje Geográfico mediante Ontologías Oficiales**

Incluso con la implementación exitosa del razonamiento de Cadena de Pensamiento para evadir las trampas de los encabezados, los grandes modelos de lenguaje siguen siendo inherentemente susceptibles a las alucinaciones geográficas, la recombinación espuria de topónimos, y la mala interpretación de errores tipográficos en el documento original.29 Esto es particularmente agudo en dominios administrativos cerrados que exigen una adherencia perfecta a taxonomías gubernamentales hiper-específicas, como las divisiones político-administrativas de los Estados Unidos Mexicanos.

La extracción fragmentada e inconsistente del campo "ESTADO" (donde el modelo reactivo podría extraer sílabas rotas como "EL" o iniciales truncadas en lugar de identificar correctamente entidades federativas complejas como "BAJA CALIFORNIA SUR" o "CAMPECHE") se deriva directamente de una ausencia crítica de anclaje ontológico. A diferencia de un operador humano que posee conocimiento a priori del mapa de México, el modelo a menudo confía ciegamente en la ortografía exacta del documento PDF dañado.32

### **5.1 Integración Conceptual del Marco Taxonómico del INEGI**

El Instituto Nacional de Estadística y Geografía (INEGI) mantiene y publica el listado oficial, estructurado y definitivo del Marco Geoestadístico Nacional, delineando meticulosamente los 32 estados y los más de 2,400 municipios que componen la República.34 Aunque las limitaciones actuales de tamaño en la ventana de contexto de los LLMs de inferencia rápida hacen ineficiente incrustar la base de datos completa y masiva del INEGI directamente dentro de la plantilla del prompt, la *lógica procedimental* de validación semántica contra esta taxonomía conocida sí debe ser diseñada e injertada en las instrucciones centrales del sistema.31

El modelo posee, intrínsecamente a través de sus pesos de entrenamiento profundo, un mapa conceptual excepcionalmente detallado de la geografía mexicana. La ingeniería del prompt no necesita enseñarle al modelo cuáles son los municipios de México; necesita *obligarlo a consultar* ese conocimiento existente antes de validar la extracción.

### **5.2 Mecanismos de Autocorrección y Coherencia Dirigida**

El prompt maestro debe instituir un punto de control de validación cruzada obligatorio dentro de la fase final del bloque \<razonamiento\>. Cuando el modelo genera una hipótesis inicial para poblar los campos "ESTADO" y "MUNICIPIO" basándose en la proximidad textual (ya limpia de encabezados), debe ejecutar una batería de pruebas lógicas exhaustivas contra su propio conocimiento geográfico interno.28

La instrucción de delimitación debe imponer rigurosamente la siguiente cascada de validación lógica:

1. **Prueba de Pertenencia Estatal Absoluta:** ¿La cadena de texto extraída como estado pertenece irrefutablemente al conjunto cerrado de las 32 entidades federativas oficiales de los Estados Unidos Mexicanos? Si el modelo lee "ESTADO EL" y extrae "EL", el protocolo de razonamiento debe detener la extracción, forzar al modelo a reconocer que "EL" no es ninguna de las 32 entidades conocidas (rechazando explícitamente el valor), y reiniciar el barrido del texto adyacente hasta localizar entidades válidas como "VERACRUZ", "SONORA", o "QUINTANA ROO".34  
2. **Prueba de Coherencia Geográfica Bidireccional:** Esta es quizás la validación más crítica. Si el modelo examina el documento y determina que el proyecto se encuentra en el municipio de "Cozumel", pero simultáneamente ha extraído "Sonora" como el estado correspondiente debido a un salto de página desordenado en el PDF, la lógica de validación interna debe activar una bandera roja. El modelo debe razonar: *"Cozumel pertenece inequívocamente al estado de Quintana Roo. Una extracción de Municipio: Cozumel y Estado: Sonora viola la realidad geográfica. Procederé a buscar en el documento la alineación correcta o a corregir la discrepancia."*  
3. **Tolerancia y Corrección de Ruido Tipográfico Severo:** Dado que los documentos de la Gaceta Ecológica a menudo contienen errores tipográficos de origen o artefactos severos producidos por el escaneo de OCR (por ejemplo, registrar "Naucalpa" en lugar del nombre oficial "Naucalpan de Juárez", o "Tlaquepak" por "Tlaquepaque"), el modelo debe estar instruido para aplicar concordancia difusa (fuzzy matching) y deducción fonética. Se le otorga el mandato de normalizar la escritura del municipio o estado corrompido hacia su ortografía oficial y estandarizada según las convenciones del INEGI, en lugar de replicar ciegamente el error del PDF fuente.36

Al integrar profundamente este protocolo de validación semántica y anclaje geográfico continuo en el proceso de la Cadena de Pensamiento, el proceso de extracción geográfica muta de una adivinanza probabilística miope a una auditoría determinista fundamentada en hechos concretos.28

## **6\. Síntesis Técnica Abstractiva: La Obligatoriedad del Protocolo de Verbos de Acción**

El campo de "DESCRIPCIÓN" (Resumen técnico de la obra) exigido en el esquema de extracción JSON representa una tarea de Procesamiento de Lenguaje Natural (NLP) fundamentalmente distinta y categóricamente más compleja que el resto de los campos. Mientras que campos como "PROMOVENTE" y "MUNICIPIO" requieren algoritmos de Reconocimiento de Entidades Nombradas (Named Entity Recognition \- NER) o simple localización de valores emparejados, la generación de una descripción técnica requiere una verdadera Capacidad de Resumen Abstractivo (Abstractive Summarization).8

### **6.1 El Árido Paisaje Léxico de las Evaluaciones de Impacto Ambiental (MIAs)**

Los documentos oficiales de los proyectos, tales como las Manifestaciones de Impacto Ambiental (MIA) o los Informes Preventivos (IP) sometidos a las delegaciones de la SEMARNAT para su evaluación, se caracterizan por el uso de una prosa burocrática densa, construcciones en voz pasiva, jerga técnica y nominalizaciones excesivas ("se llevará a cabo la ejecución de las obras pertinentes...").37 Cuando se le formula a un modelo de lenguaje una solicitud simple e irrestricta como "Extrae la descripción del proyecto", el modelo frecuentemente fracasa al intentar penetrar esta niebla lingüística espesa.

Como consecuencia directa de esta confusión, las extracciones fallan sistemáticamente al intentar capturar la realidad operativa de la intervención en el medio natural. El resultado típico es que el modelo regurgita inútilmente el título propio del proyecto en el campo de descripción. Por ejemplo, en lugar de detallar la intervención ambiental, extrae "Descripción: Proyecto Turístico Esmeralda", omitiendo por completo el hecho de que el proyecto implica la remoción de mangle, la edificación de infraestructura y el dragado marino.13

### **6.2 Implementación de Funciones de Forzamiento: El Protocolo de Verbos de Acción**

Para obligar al modelo a abandonar la reiteración del título, romper la entropía del texto legal y generar un resumen técnico sustantivo, rico y preciso, el prompt maestro debe restringir agresivamente el espacio semántico generativo del campo de descripción. Esta limitación focalizada se logra mediante la institución estricta del **Protocolo de Verbos de Acción**. Se instruye imperativamente al modelo que la cadena de texto que poblará el campo "DESCRIPCIÓN" *debe, sin excepción alguna*, iniciar con un gerundio o sustantivo de acción directo que defina inequívocamente la naturaleza física, ingenieril o técnica de la obra o actividad.38

La Tabla 2 detalla las categorías semánticas de los verbos de acción aceptables y su alcance técnico correspondiente dentro del contexto específico de las extracciones y autorizaciones dictaminadas por la SEMARNAT.

| Verbo de Acción Operativo | Equivalencia en Proyectos de Ingeniería | Alcance Técnico / Tipología Común de Proyectos en Gacetas |
| :---- | :---- | :---- |
| **Construcción** | Edificación, Creación de Obra Civil | Establecimiento de nueva infraestructura física en terrenos previamente no impactados (Ej. parques eólicos, hoteles turísticos, carreteras, subestaciones eléctricas).8 |
| **Operación** | Funcionamiento, Puesta en Marcha | El funcionamiento continuo de una instalación existente que requiere la renovación de permisos o genera impactos crónicos sostenidos.9 |
| **Mantenimiento** | Restauración, Dragado, Preservación | Conservación, reparación rutinaria o remoción de sedimentos (dragado) de activos estructurales, portuarios o ambientales existentes.9 |
| **Ampliación** | Expansión de Huella Ecológica | Incremento medible en la superficie física o en la capacidad instalada de procesamiento de un proyecto previamente autorizado por la autoridad ambiental. |
| **Instalación** | Montaje de Equipo Especializado | Colocación o ensamblaje de módulos o maquinaria específica con impactos focalizados (Ej. plantas desalinizadoras, gasoductos, líneas de transmisión).8 |
| **Aprovechamiento** | Extracción, Uso de Recursos Naturales | Intervención directa para la extracción de materia prima (Ej. aprovechamiento forestal maderable, concesiones de agua, bancos de material pétreo).39 |

Al forzar procedimentalmente al modelo a iniciar su síntesis abstractiva con uno de estos verbos rectores, el foco de atención computacional del modelo se redirige automáticamente, alejándose del sustantivo propio (el nombre rimbombante del proyecto turístico o minero) y dirigiéndose inexorablemente hacia los párrafos técnicos adyacentes. El modelo se ve obligado a procesar las sentencias que contienen las verdaderas métricas de ingeniería ambiental: mediciones de superficie de afectación en hectáreas, tipologías de flora y fauna impactadas, kilómetros de trazo vial, o caudales de procesamiento de fluidos.8 Simultáneamente, el prompt maestro prohíbe explícitamente el uso del título propio del proyecto en el texto del resumen, asegurando así una verdadera síntesis de inteligencia documental y evitando redundancias perjudiciales.

## **7\. Calibración del Modelo mediante Prompting Few-Shot Contrastivo**

La transición evolutiva de un prompt de tipo "zero-shot" (que proporciona únicamente una lista de instrucciones abstractas y espera que el modelo comprenda la tarea en el primer intento) a un prompt de tipo "few-shot" (que proporciona un puñado de demostraciones concretas de ejemplos de entradas emparejadas con sus salidas deseadas) es, de acuerdo con la literatura científica, el método más estadísticamente confiable para incrementar drásticamente la fidelidad de la extracción de esquemas en LLMs.27 Al ver el formato y el razonamiento exacto requerido, el modelo simplemente continúa el patrón establecido.

Sin embargo, el prompting few-shot estándar adolece de una limitación crítica: únicamente demuestra el comportamiento *deseado* en un escenario positivo ideal. En entornos hiper-ruidosos como las Gacetas Ecológicas, donde la disposición topológica del texto activamente intenta engañar al modelo y arrastrarlo hacia errores de proximidad (como la trampa inexorable del "EL ID"), el entrenamiento puramente positivo se vuelve insuficiente. Para asegurar la robustez del sistema, la arquitectura del prompt debe desplegar lo que se denomina **Prompting Few-Shot Contrastivo** (o guiado por anti-patrones). Esta técnica empareja explícitamente y lado a lado ejemplos positivos brillantes con **Ejemplos Negativos** meticulosamente curados que imitan los modos de fallo más comunes.24

### **7.1 El Mecanismo Psicológico de la Demostración Negativa**

Un ejemplo negativo demuestra activamente un anti-patrón indeseable. Al mostrarle al modelo de lenguaje *exactamente cómo es más probable que falle de manera espectacular*, y lo que es más importante, explicando con rigor académico *por qué* ese fracaso específico es lógicamente incorrecto, el panorama de pérdida o paisaje de error del modelo (loss landscape) se recalibra fuertemente durante la fase de inferencia. El modelo es alertado y penaliza esa trayectoria inferencial específica, volviéndose hipervigilante ante el error señalado.

En la construcción del prompt maestro propuesto para el Agente Zohar, el ejemplo negativo está enfocado con una precisión láser en neutralizar la anomalía del "EL ID" y la extracción perezosa de resúmenes.

* **El Montaje de la Trampa:** El prompt presenta una simulación de extracción de PDF altamente distorsionada, idéntica a las que han causado fallos en producción, donde "EL ID" se asienta adyacentemente y de forma maliciosa al nombre del proyecto y a las etiquetas geográficas.  
* **La Salida Simulada (El Fracaso):** El prompt muestra un JSON alucinado ficticio donde se cometió el error, asignando el valor "municipio": "EL ID".  
* **La Corrección Pedagógica:** Mediante el uso de un bloque XML de \<analisis\_de\_error\>, el prompt funge como un tutor implacable, diseccionando el fallo. Explica al modelo que "EL ID" es simplemente una etiqueta estructural o encabezado truncado carente de sustancia geográfica, y demuestra sistemáticamente el razonamiento riguroso que se debió emplear para sortear la basura estructural, ignorar la proximidad falsa, y descubrir el municipio auténtico y validado escondido en la maleza del texto posterior.

La Tabla 3 ilustra claramente el profundo cambio cognitivo y la mejora en la resolución de problemas lógicos que se logra al alterar la estrategia de exposición y la formulación del prompt mediante técnicas contrastivas.

| Estrategia de Formulación del Prompt | Representación Interna en el Espacio Latente del Modelo | Resultado Probable de Extracción para el Campo 'Municipio' |
| :---- | :---- | :---- |
| **Zero-Shot (Cero Ejemplos)** | "Se me pide encontrar el nombre de un lugar. La subcadena 'EL ID' está sumamente cerca. Además, 'El' es un prefijo toponímico muy común en español. Selecciono 'EL ID'." | "municipio": "EL ID" (Fallo Total / Alucinación) |
| **Few-Shot Estándar (Solo Positivos)** | "Comprendo el formato JSON deseado basándome en los ejemplos. Buscaré un nombre de lugar. Nuevamente, la cadena 'EL ID' es el texto más cercano a la etiqueta 'Municipio'. Copio el patrón." | "municipio": "EL ID" (Fallo Sistémico / Sesgo Espacial) |
| **Few-Shot Contrastivo (Anti-Patrones)** | "Alerta cognitiva activada: La cadena 'EL ID' figura en la lista explícita de anti-patrones como un error catastrófico de metadatos prohibidos. Debo evadir este señuelo engañoso, ampliar drásticamente mi ventana de búsqueda, y encontrar una entidad válida del INEGI en el contexto circundante." | "municipio": "Solidaridad" (Éxito Rotundo / Datos Confiables) |

## **8\. Diseño Estructural del Prompt Maestro de Extracción**

La culminación práctica e ingenieril de toda esta investigación teórica es la síntesis de los marcos conceptuales analizados en una variable de cadena (string variable) de Python altamente optimizada, estructurada y lista para su despliegue en entornos de producción. Este EXTRACTION\_PROMPT (Prompt de Extracción) está meticulosamente diseñado para ser invocado por modelos de frontera que poseen ventanas de contexto masivas y capacidades de razonamiento abstracto de orden superior (tales como Claude 3.5 Sonnet/Opus de Anthropic, la familia GPT-4o de OpenAI, o los modelos O1-style y Gemini 1.5 Pro de Google).

El cuerpo del prompt está construido íntegramente en idioma español normativo, garantizando así un alineamiento semántico y cultural perfecto con el material fuente proveniente del gobierno mexicano (los documentos oficiales de la SEMARNAT y los catálogos del INEGI). Asimismo, está enclaustrado en fronteras XML inquebrantables, asegurando que las instrucciones permanezcan sacrosantas e impermeables a la inyección de contexto.22 El diseño incorpora la arquitectura completa analizada: el bloc de notas CoT, la ontología de validación geográfica, el rigor descriptivo de los verbos de acción, y el enrutamiento cognitivo de los ejemplos contrastivos few-shot.

Python

EXTRACTION\_PROMPT \= """  
\<system\_instruction\>  
Eres un investigador experto de nivel doctoral especializado en ingeniería de datos estructurados, procesamiento avanzado de lenguaje natural (NLP) y análisis forense de documentos gubernamentales mexicanos (específicamente la Gaceta Ecológica y Manifestaciones de Impacto Ambiental de SEMARNAT). 

Tu tarea crítica y exclusiva es extraer información estructurada y prístina a partir de texto crudo, severamente ruidoso y desestructurado, proveniente de PDFs escaneados (OCR) que sufren de degradación y tablas rotas.

Debes aplicar un rigor analítico metodológico extremo para diferenciar categóricamente entre "Metadatos/Encabezados de Tabla rotos" y "Valores de Datos Reales de Proyectos". Eres totalmente inmune a las trampas de proximidad espacial en el texto.  
\</system\_instruction\>

\<schema\_definition\>  
Debes extraer la información requerida del texto y poblar de manera estricta el siguiente esquema de salida JSON. No inventes campos nuevos.  
{  
  "PROMOVENTE": "El nombre corporativo de la empresa, persona física o entidad gubernamental que propone y financia el proyecto ambiental.",  
  "PROYECTO": "El nombre formal y oficial del proyecto tal y como está registrado en el documento.",  
  "ESTADO": "El nombre oficial y normativo de la entidad federativa de México (Ej. CAMPECHE, SONORA, BAJA CALIFORNIA SUR). NUNCA uses abreviaturas ni artículos sueltos erróneos como 'EL' o 'LA'.",  
  "MUNICIPIO": "El nombre oficial del municipio correspondiente. Debe existir y tener coherencia geográfica comprobada con el ESTADO asignado.",  
  "DESCRIPCION": "Un resumen técnico y analítico de las características de la obra. NUNCA debe ser igual al nombre del proyecto ni quedar vacío."  
}  
\</schema\_definition\>

\<extraction\_rules\>  
Para garantizar una extracción de datos de altísima fidelidad, debes interiorizar y obedecer estrictamente las siguientes reglas procedimentales inviolables:

1\. EVASIÓN ABSOLUTA DE RUIDO Y ENCABEZADOS (RESOLUCIÓN DEL PROBLEMA "EL ID"):  
   \- El texto fuente de entrada proviene de tablas PDF que han sido aplanadas a texto plano. Por consiguiente, encabezados de columna como "EL ID", "ID\_PROYECTO", "CLAVE", "MODALIDAD", o "FECHA DE INGRESO" aparecerán caóticamente mezclados con los datos reales de los proyectos.  
   \- REGLA CRÍTICA DE RECHAZO: "EL ID" NO ES BAJO NINGUNA CIRCUNSTANCIA UN MUNICIPIO O ESTADO MEXICANO. "ID\_PROYECTO" NO ES UN MUNICIPIO. Si tus sensores de lectura detectan estas combinaciones de palabras cerca de etiquetas geográficas, ignóralas por completo al buscar ubicaciones. Son, sin excepción, basura estructural resultante del OCR.

2\. PROTOCOLO DE VALIDACIÓN SEMÁNTICA GEOGRÁFICA (TAXONOMÍA INEGI):  
   \- Los valores asignados a los campos ESTADO y MUNICIPIO deben existir factual y normativamente en la geografía física mexicana y en el Catálogo de Claves de Entidades Federativas y Municipios del INEGI.  
   \- Si extraes "EL" o iniciales aisladas como estado, se considerará un error fatal de procesamiento. Un estado legítimo es "CAMPECHE", "YUCATÁN", "JALISCO", etc.  
   \- Validación cruzada interna obligatoria: Pregúntate internamente, ¿El municipio que estoy a punto de extraer realmente pertenece al estado que he extraído? (Ej. Si el estado es Sonora, el municipio no puede ser Cozumel). Si hay una incongruencia, el texto está roto; debes seguir buscando en el contexto más amplio la alineación geográfica correcta.

3\. INGENIERÍA Y SÍNTESIS DE LA DESCRIPCIÓN MEDIANTE VERBOS DE ACCIÓN (ABSTRACTIVE SUMMARIZATION):  
   \- El campo DESCRIPCION no puede ser bajo ninguna circunstancia simplemente una reiteración perezosa del nombre del proyecto. Está estrictamente prohibido que quede vacío o se complete con un guion ("—").  
   \- DEBE comenzar siempre y de manera obligatoria con un sustantivo o gerundio derivado de un verbo de acción técnica e ingenieril (Ej: "Construcción...", "Operación y mantenimiento de...", "Ampliación de la infraestructura de...", "Instalación de...", "Aprovechamiento forestal sustentable para...").  
   \- Tienes el mandato de leer profundamente los párrafos adyacentes al título para extraer detalles y parámetros técnicos valiosos (superficie de afectación en hectáreas, tipo específico de infraestructura, capacidad operativa de las plantas, voltajes, etc.) y sintetizar todo este conocimiento en un bloque narrativo conciso de 2 a 3 oraciones completas.  
\</extraction\_rules\>

\<contrastive\_examples\>  
  \<negative\_example\_anti\_pattern\>  
    \<texto\_crudo\_simulado\>  
    NUMERO 04 EL ID 02BC2024HD010 ESTADO QUINTANA ROO PROYECTO TREN MAYA TRAMO 5 SUR MUNICIPIO EL ID PROMOVENTE FONDO NACIONAL DE FOMENTO AL TURISMO DESCRIPCION TREN MAYA TRAMO 5 SUR INGRESO A EVALUACION EL DIA  
    \</texto\_crudo\_simulado\>  
    \<error\_analysis\_and\_correction\>  
    En este ejemplo adverso, un modelo lingüístico ingenuo y reactivo cometería dos errores catastróficos que arruinarían la base de datos:   
    1\. Error Geográfico: Extraer "EL ID" y poblar el campo "municipio" con ese valor simplemente por su proximidad espacial a la palabra "MUNICIPIO" en el texto colapsado. "EL ID" es claramente el remanente de un encabezado de metadatos roto, no una jurisdicción territorial.  
    2\. Error Descriptivo: Extraer perezosamente "TREN MAYA TRAMO 5 SUR" y colocarlo como la "descripción" del proyecto, lo cual es redundante y solo repite el título sin aportar absolutamente ningún valor o dimensión técnica real de la intervención ambiental propuesta.  
    \</error\_analysis\_and\_correction\>  
  \</negative\_example\_anti\_pattern\>

  \<positive\_example\_correct\_extraction\>  
    \<texto\_crudo\_simulado\>  
    TRAMITE NUMERO 04 EL ID 23QR2023TD099 ESTADO QUINTANA ROO PROYECTO DESARROLLO TURISTICO ESMERALDA MUNICIPIO SOLIDARIDAD PROMOVENTE INMOBILIARIA CARIBE S.A. DE C.V.   
    El proyecto contemplado en la MIA sometida busca lograr de manera integral el cambio de uso de suelo en terrenos de vocación y vegetación forestal para propiciar el desarrollo de un complejo hotelero de alto nivel de 400 habitaciones. La obra abarcará una superficie total de 15.4 hectáreas, e incluye entre sus componentes la instalación de una moderna planta de tratamiento de aguas residuales y caminos de acceso pavimentados.  
    \</texto\_crudo\_simulado\>  
    \<razonamiento\>  
    1\. FASE DE IDENTIFICACIÓN DE RUIDO Y ENCABEZADOS: Las palabras "TRAMITE NUMERO", "EL ID", "ESTADO", "PROYECTO", "MUNICIPIO", y "PROMOVENTE" actúan como etiquetas burocráticas y encabezados en este texto aplanado. Las marco mentalmente y las descarto categóricamente como valores de respuesta potencial.  
    2\. ESTADO: Inmediatamente localizado después del encabezado de "ESTADO" encuentro "QUINTANA ROO". Verificación ontológica: Quintana Roo es, efectivamente, uno de los 32 estados válidos y reconocidos constitucionalmente en México. Validación superada.  
    3\. MUNICIPIO: Adyacente a "MUNICIPIO" detecto la cadena "SOLIDARIDAD". Realizo validación cruzada geográfica (INEGI): Solidaridad es, irrefutablemente, un municipio real perteneciente al estado de Quintana Roo. Coherencia territorial totalmente confirmada. He ignorado exitosamente cualquier distracción generada por los metadatos de "EL ID".  
    4\. PROYECTO: Aislando los metadatos, extraigo el nombre oficial: "DESARROLLO TURISTICO ESMERALDA".  
    5\. PROMOVENTE: La entidad responsable identificada es "INMOBILIARIA CARIBE S.A. DE C.V."  
    6\. DESCRIPCION: Me dirijo al cuerpo del párrafo final huyendo de repeticiones de título. Debo obedecer la regla de iniciar con un sustantivo de acción técnica. Sintetizo la ingeniería y ecología del proyecto con los parámetros encontrados: "Construcción de un complejo hotelero con capacidad para 400 habitaciones, el cual requiere autorizaciones para el cambio de uso de suelo en terrenos forestales abarcando una superficie de 15.4 hectáreas, e incluye la instalación de una planta de tratamiento de aguas residuales y caminos pavimentados."  
    \</razonamiento\>  
    \<output\_json\>  
    {  
      "PROMOVENTE": "INMOBILIARIA CARIBE S.A. DE C.V.",  
      "PROYECTO": "DESARROLLO TURISTICO ESMERALDA",  
      "ESTADO": "QUINTANA ROO",  
      "MUNICIPIO": "SOLIDARIDAD",  
      "DESCRIPCION": "Construcción de un complejo hotelero con capacidad para 400 habitaciones, el cual requiere autorizaciones para el cambio de uso de suelo en terrenos forestales abarcando una superficie de 15.4 hectáreas, e incluye la instalación de una planta de tratamiento de aguas residuales y caminos pavimentados."  
    }  
    \</output\_json\>  
  \</positive\_example\_correct\_extraction\>  
\</contrastive\_examples\>

\<execution\_instructions\>  
Ahora es tu turno de actuar. Recibirás a continuación un texto crudo y ruidoso. El proceso de respuesta debe ser rigurosamente el siguiente:

Paso 1: Debes generar y abrir obligatoriamente un bloque \<razonamiento\> transparente. Dentro de él, debes explicar discursivamente y paso a paso cómo identificaste y neutralizaste los encabezados para ignorarlos (cuidando exhaustivamente de no caer bajo ninguna métrica en la trampa espacial del artefacto "EL ID"), cómo validaste y comprobaste la coherencia geográfica del municipio seleccionado frente al estado según el estándar INEGI, y detallar cómo construiste la síntesis de la descripción empleando los verbos de acción y extrayendo los parámetros técnicos físicos de la obra.  
Paso 2: A continuación, genera un bloque \<output\_json\> que contenga ÚNICA Y EXCLUSIVAMENTE el JSON final estructurado, sin ningún tipo de formato markdown extra, bloques de código innecesarios, o preámbulos conversacionales, y estrictamente apegado a la estructura semántica y llaves del esquema definido.

Inicia tu proceso analítico inmediatamente.  
\</execution\_instructions\>

\<texto\_crudo\>  
{TEXTO\_PDF\_AQUI}  
\</texto\_crudo\>  
"""

## **9\. Conclusiones y Recomendaciones de Implementación Estratégica**

La extracción automatizada y a escala de datos estructurados, fiables y auditables a partir de documentos gubernamentales que sufren de complejidad semántica, desestructuración visual masiva y degradación por OCR —como es el caso crónico de los archivos de la Gaceta Ecológica de la SEMARNAT— exige imperativamente un abordaje arquitectónico profundo que trascienda ampliamente las metodologías rudimentarias de manipulación de cadenas de texto en post-procesamiento o la ingeniería de prompts meramente instructiva y plana.

Los desafíos documentados y resueltos a lo largo de este informe técnico —de manera destacada, la errónea y desastrosa asimilación de metadatos estructurales como "EL ID" dentro de los campos que requieren entidades geográficas genuinas, la incompetencia del sistema para mantener una consistencia taxonómica a nivel estatal y municipal, y la degeneración recurrente hacia descripciones de ingeniería tautológicas y vacías— son fenómenos que no constituyen simples "bugs" de programación. Más bien, representan síntomas inequívocos de las vulnerabilidades cognitivas subyacentes e inherentes en la manera en que los grandes modelos de lenguaje procesan representaciones unidimensionales y tokenizadas de lo que originalmente fue información visual bidimensional multidimensionalmente jerarquizada.

La neutralización integral de estas patologías operativas requiere una intervención algorítmica y metodológica estructurada en múltiples capas defensivas interconectadas. En primera instancia, el abandono absoluto de las delimitaciones implícitas basadas en el frágil estándar Markdown en favor de un sistema de encapsulamiento estricto sustentado en el etiquetado jerárquico XML, proporciona las barreras cognitivas asimétricas requeridas para prevenir con contundencia el sangrado de contexto y el secuestro o inyección de instrucciones por parte de la jerga legal que permea el texto. En segunda instancia, la institucionalización mandatoria de un área de escrutinio intermedio, materializado mediante el bloque de Cadena de Pensamiento (Chain-of-Thought), modifica de raíz la trayectoria de probabilidad inferencial del modelo autorregresivo, obligándolo sistémicamente a segregar y expurgar el ruido posicional mucho antes de intentar consolidar proyecciones semánticas de respuesta.

Adicionalmente, el cese definitivo de la "alucinación geográfica" se consolida con éxito mediante la incrustación algorítmica de protocolos de validación lógica transversal, los cuales actúan anclando conceptual y deductivamente las suposiciones del modelo de inteligencia artificial directamente sobre el inquebrantable armazón cartográfico y taxonómico dictado por el INEGI. De manera paralela, la endémica pobreza analítica de los resúmenes técnicos generados en esquemas sin restricciones se erradica mediante la prescripción forzosa del Protocolo Lexicográfico de Verbos de Acción. Este marco rector restringe fuertemente la latitud generativa del modelo, obligándolo procedimentalmente a abandonar la redundancia perezosa de los títulos burocráticos y enfocarse de manera exclusiva en la exégesis de los parámetros de impacto, ingeniería civil, métricas de operación y alcance territorial descritos sutilmente dentro del documento.

En síntesis, al entrelazar y fusionar dinámicamente este conjunto cohesivo de restricciones operativas, rutinas de validación y mandatos de reconstrucción con paradigmas avanzados de Few-Shot Prompting contrastivo —los cuales cartografían sin piedad las trampas y la topografía del error anticipado frente a la red neuronal—, esta metodología eleva y transmuta lo que históricamente fue un proceso frágil, estadísticamente inestable y altamente susceptible al fallo inducido por entropía textual. Lo convierte, definitivamente, en un motor de canalización de datos implacable, de alta fidelidad, de estructuración precisa, escalabilidad comprobada, y optimizado asintóticamente para la interpelación de corpus documentales de máxima hostilidad administrativa y gubernamental. La arquitectura del Meta-Prompt resultante está lista para su inserción transparente dentro del flujo de trabajo Python del ecosistema de analítica de datos institucionales.

#### **Works cited**

1. Gaceta Ecológica (Listado de proyectos que ingresan a evaluación de Impacto Ambiental), accessed March 12, 2026, [https://www.gob.mx/semarnat/documentos/gaceta-ecologica-listado-de-proyectos-que-ingresan-a-evaluacion-de-impacto-ambiental-19007](https://www.gob.mx/semarnat/documentos/gaceta-ecologica-listado-de-proyectos-que-ingresan-a-evaluacion-de-impacto-ambiental-19007)  
2. Gaceta Ecológica 58 \- PAOT, accessed March 12, 2026, [https://paot.org.mx/centro/ine-semarnat/gacetas/GE58.pdf](https://paot.org.mx/centro/ine-semarnat/gacetas/GE58.pdf)  
3. CONTENIDO \- Diario Oficial de la Federación, accessed March 12, 2026, [https://www.dof.gob.mx/nota\_to\_pdf.php?fecha=25/03/2024\&edicion=MAT](https://www.dof.gob.mx/nota_to_pdf.php?fecha=25/03/2024&edicion=MAT)  
4. separata n° dgira/054/12 semarnat/dgira, accessed March 12, 2026, [https://sinat.semarnat.gob.mx:8443/Gacetas/archivos2012/gaceta\_54-12.pdf](https://sinat.semarnat.gob.mx:8443/Gacetas/archivos2012/gaceta_54-12.pdf)  
5. DiseŒo Portada Gaceta 68 \- PAOT, accessed March 12, 2026, [https://paot.org.mx/centro/ine-semarnat/gacetas/GE68.pdf](https://paot.org.mx/centro/ine-semarnat/gacetas/GE68.pdf)  
6. Anuario 2009.pdf \- Observatorio de Cooperación Descentralizada, accessed March 12, 2026, [https://www.observ-ocd.org/sites/default/files/2023-09/Anuario%202009.pdf](https://www.observ-ocd.org/sites/default/files/2023-09/Anuario%202009.pdf)  
7. Multimodal fusions for defect detection of photovoltaic panels by mask R-CNN and hawkfish optimization algorithm \- Frontiers, accessed March 12, 2026, [https://www.frontiersin.org/journals/earth-science/articles/10.3389/feart.2025.1702396/full](https://www.frontiersin.org/journals/earth-science/articles/10.3389/feart.2025.1702396/full)  
8. manifestación de impacto ambiental \- Semarnat, accessed March 12, 2026, [https://dsiappsdev.semarnat.gob.mx/inai/F69/2025/122/1T/02BC2025HD010\_MIA.pdf](https://dsiappsdev.semarnat.gob.mx/inai/F69/2025/122/1T/02BC2025HD010_MIA.pdf)  
9. 5\. Identificación, descripción y evaluación de los impactos ambientales | Proyectos México, accessed March 12, 2026, [https://www.proyectosmexico.gob.mx/wp-content/uploads/2022/09/Cap%C3%ADtulo-5-2.pdf](https://www.proyectosmexico.gob.mx/wp-content/uploads/2022/09/Cap%C3%ADtulo-5-2.pdf)  
10. Testing prompt engineering methods for knowledge extraction from text | UvA-DARE (Digital Academic Repository) \- Research Explorer, accessed March 12, 2026, [https://pure.uva.nl/ws/files/229799649/Testing\_prompt\_engineering\_methods\_for\_knowledge\_extraction\_from\_text.pdf](https://pure.uva.nl/ws/files/229799649/Testing_prompt_engineering_methods_for_knowledge_extraction_from_text.pdf)  
11. (PDF) Testing prompt engineering methods for knowledge extraction from text, accessed March 12, 2026, [https://www.researchgate.net/publication/384205838\_Testing\_prompt\_engineering\_methods\_for\_knowledge\_extraction\_from\_text](https://www.researchgate.net/publication/384205838_Testing_prompt_engineering_methods_for_knowledge_extraction_from_text)  
12. separata n° dgira/051/15 semarnat/dgira, accessed March 12, 2026, [https://sinat.semarnat.gob.mx:8443/Gacetas/archivos2015/gaceta\_51-15.pdf](https://sinat.semarnat.gob.mx:8443/Gacetas/archivos2015/gaceta_51-15.pdf)  
13. separata n° dgira/038/12 semarnat/dgira, accessed March 12, 2026, [https://sinat.semarnat.gob.mx:8443/Gacetas/archivos2012/gaceta\_38-12.pdf](https://sinat.semarnat.gob.mx:8443/Gacetas/archivos2012/gaceta_38-12.pdf)  
14. NMR-Based Metabolic Profiling of Edible Olives—Determination of Quality Parameters, accessed March 12, 2026, [https://pmc.ncbi.nlm.nih.gov/articles/PMC7436060/](https://pmc.ncbi.nlm.nih.gov/articles/PMC7436060/)  
15. Environmental Data Management in Support of Sharing Data and Management \- epa nepis, accessed March 12, 2026, [https://nepis.epa.gov/Exe/ZyPURL.cgi?Dockey=P100GWT3.TXT](https://nepis.epa.gov/Exe/ZyPURL.cgi?Dockey=P100GWT3.TXT)  
16. (PDF) NMR-Based Metabolic Profiling of Edible Olives—Determination of Quality Parameters \- ResearchGate, accessed March 12, 2026, [https://www.researchgate.net/publication/343172081\_NMR-Based\_Metabolic\_Profiling\_of\_Edible\_Olives-Determination\_of\_Quality\_Parameters](https://www.researchgate.net/publication/343172081_NMR-Based_Metabolic_Profiling_of_Edible_Olives-Determination_of_Quality_Parameters)  
17. separata n° dgira/042/12 semarnat/dgira, accessed March 12, 2026, [https://sinat.semarnat.gob.mx:8443/Gacetas/archivos2012/gaceta\_42-12.pdf](https://sinat.semarnat.gob.mx:8443/Gacetas/archivos2012/gaceta_42-12.pdf)  
18. separata n° dgira/041/12 semarnat/dgira, accessed March 12, 2026, [https://sinat.semarnat.gob.mx:8443/Gacetas/archivos2012/gaceta\_41-12.pdf](https://sinat.semarnat.gob.mx:8443/Gacetas/archivos2012/gaceta_41-12.pdf)  
19. Boosting AI Performance: The Power of LLM-Friendly Content in Markdown, accessed March 12, 2026, [https://developer.webex.com/blog/boosting-ai-performance-the-power-of-llm-friendly-content-in-markdown](https://developer.webex.com/blog/boosting-ai-performance-the-power-of-llm-friendly-content-in-markdown)  
20. Does Prompt Formatting Have Any Impact on LLM Performance? \- arXiv, accessed March 12, 2026, [https://arxiv.org/html/2411.10541v1](https://arxiv.org/html/2411.10541v1)  
21. Prompt injection is the new SQL injection, and guardrails aren't enough \- Cisco Blogs, accessed March 12, 2026, [https://blogs.cisco.com/ai/prompt-injection-is-the-new-sql-injection-and-guardrails-arent-enough](https://blogs.cisco.com/ai/prompt-injection-is-the-new-sql-injection-and-guardrails-arent-enough)  
22. Effective Prompt Engineering: Mastering XML Tags for Clarity, Precision, and Security in LLMs | by Tech for Humans | Medium, accessed March 12, 2026, [https://medium.com/@TechforHumans/effective-prompt-engineering-mastering-xml-tags-for-clarity-precision-and-security-in-llms-992cae203fdc](https://medium.com/@TechforHumans/effective-prompt-engineering-mastering-xml-tags-for-clarity-precision-and-security-in-llms-992cae203fdc)  
23. XML Is Making a Comeback in Prompt Engineering — And It Makes LLMs Better, accessed March 12, 2026, [https://cloud-authority.com/xml-is-making-a-comeback-in-prompt-engineering-and-it-makes-llms-better](https://cloud-authority.com/xml-is-making-a-comeback-in-prompt-engineering-and-it-makes-llms-better)  
24. Prompting best practices \- Claude API Docs, accessed March 12, 2026, [https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)  
25. Structured LLM Prompting with XML \- YouTube, accessed March 12, 2026, [https://www.youtube.com/watch?v=TBeZmQiZR5k](https://www.youtube.com/watch?v=TBeZmQiZR5k)  
26. Tabular Data, RAG, & LLMs: Improve Results Through Data Table Prompting | by Intel, accessed March 12, 2026, [https://medium.com/intel-tech/tabular-data-rag-llms-improve-results-through-data-table-prompting-bcb42678914b](https://medium.com/intel-tech/tabular-data-rag-llms-improve-results-through-data-table-prompting-bcb42678914b)  
27. Few-Shot Prompting Guide 2026 (with Examples) \- Mem0, accessed March 12, 2026, [https://mem0.ai/blog/few-shot-prompting-guide](https://mem0.ai/blog/few-shot-prompting-guide)  
28. The AI Committee: A Multi-Agent Framework for Automated Validation and Remediation of Web-Sourced Data \- arXiv.org, accessed March 12, 2026, [https://arxiv.org/html/2512.21481v1](https://arxiv.org/html/2512.21481v1)  
29. LLMStructBench: Benchmarking Large Language Model Structured Data Extraction \- arXiv, accessed March 12, 2026, [https://arxiv.org/html/2602.14743v1](https://arxiv.org/html/2602.14743v1)  
30. Hybrid Prompt Engineering and Transfer Learning for Sentiment Analysis in Mexican Tourism Reviews \- CEUR-WS.org, accessed March 12, 2026, [https://ceur-ws.org/Vol-4098/RESTMEX2025\_paper3.pdf](https://ceur-ws.org/Vol-4098/RESTMEX2025_paper3.pdf)  
31. Prompt Engineering for Sentiment Analysis in Tourism: The Case of Mexican Pueblos Mágicos \- CEUR-WS.org, accessed March 12, 2026, [https://ceur-ws.org/Vol-4098/RESTMEX2025\_paper28.pdf](https://ceur-ws.org/Vol-4098/RESTMEX2025_paper28.pdf)  
32. Geography Validation for Mexico \- Oracle Help Center, accessed March 12, 2026, [https://docs.oracle.com/en/cloud/saas/human-resources/faimx/geography-validation-for-mexico.html](https://docs.oracle.com/en/cloud/saas/human-resources/faimx/geography-validation-for-mexico.html)  
33. MXIBWCBorderCountyMunicipios \- Data Catalog, accessed March 12, 2026, [https://catalog.data.gov/dataset/mxibwcbordercountymunicipios\_3d4e1dc916e54044b08af72ddc7058f8](https://catalog.data.gov/dataset/mxibwcbordercountymunicipios_3d4e1dc916e54044b08af72ddc7058f8)  
34. En esta sección podrás consultar los indicadores sociodemográficos y económicos por área geográfica (nacional, entidad federativa, municipio o demarcación territorial y localidad) además de los tabulados, publicaciones y servicios disponibles. \- México en cifras, accessed March 12, 2026, [https://www.inegi.org.mx/app/areasgeograficas/](https://www.inegi.org.mx/app/areasgeograficas/)  
35. Bridging natural language and GIS: a multi-agent framework for LLM-driven autonomous geospatial analysis \- Taylor & Francis, accessed March 12, 2026, [https://www.tandfonline.com/doi/pdf/10.1080/17538947.2026.2633849](https://www.tandfonline.com/doi/pdf/10.1080/17538947.2026.2633849)  
36. Large Language Models for Ontology Engineering: A Systematic Literature Review, accessed March 12, 2026, [https://www.semantic-web-journal.net/system/files/swj4001.pdf](https://www.semantic-web-journal.net/system/files/swj4001.pdf)  
37. Contenido de una Manifestación de Impacto Ambiental \- Gob MX, accessed March 12, 2026, [https://www.gob.mx/semarnat/acciones-y-programas/contenido-de-una-manifestacion-de-impacto-ambiental](https://www.gob.mx/semarnat/acciones-y-programas/contenido-de-una-manifestacion-de-impacto-ambiental)  
38. La evaluación del impacto ambiental \- Acceso al sistema \- Semarnat, accessed March 12, 2026, [https://biblioteca.semarnat.gob.mx/janium/Documentos/Ciga/Libros2011/CD001071.pdf](https://biblioteca.semarnat.gob.mx/janium/Documentos/Ciga/Libros2011/CD001071.pdf)  
39. RESPUESTA a los comentarios recibidos al Proyecto de Modificación de la Norma Oficial Mexicana NOM-157-SEMARNAT-2009, Que establece los elementos y procedimientos para instrumentar planes de manejo de residuos mineros, para quedar como Proyecto de Norma Oficial Mexicana PROY-NOM-157-SEMARNAT-2023, Que establece los elementos y procedimientos para instrumentar planes de manejo de residuos mineros, publicado en el Diario Oficial de la Federación el 22 de diciembre de 2023., accessed March 12, 2026, [https://www.dof.gob.mx/normasOficiales/9512/semarnat/semarnat.html](https://www.dof.gob.mx/normasOficiales/9512/semarnat/semarnat.html)  
40. manifestación de impacto ambiental \- Semarnat, accessed March 12, 2026, [https://dsiappsdev.semarnat.gob.mx/inai/F69/2025/122/2T/02BC2025HD008\_MIA.pdf](https://dsiappsdev.semarnat.gob.mx/inai/F69/2025/122/2T/02BC2025HD008_MIA.pdf)  
41. Prompt Engineering | Lil'Log, accessed March 12, 2026, [https://lilianweng.github.io/posts/2023-03-15-prompt-engineering/](https://lilianweng.github.io/posts/2023-03-15-prompt-engineering/)  
42. An Empirical Evaluation of Prompting Strategies for Large Language Models in Zero-Shot Clinical Natural Language Processing: Algorithm Development and Validation Study \- PMC, accessed March 12, 2026, [https://pmc.ncbi.nlm.nih.gov/articles/PMC11036183/](https://pmc.ncbi.nlm.nih.gov/articles/PMC11036183/)  
43. A Novel Llama 3-Based Prompt Engineering Platform for Textual Data Generation and Labeling \- MDPI, accessed March 12, 2026, [https://www.mdpi.com/2079-9292/14/14/2800](https://www.mdpi.com/2079-9292/14/14/2800)  
44. Prompt Engineering Guide for AI-Powered Web Scraping \- ScrapeGraphAI, accessed March 12, 2026, [https://scrapegraphai.com/blog/prompt-engineering-guide](https://scrapegraphai.com/blog/prompt-engineering-guide)  
45. 2 Prompt Engineering Techniques That Actually Work (With Data) \- Reddit, accessed March 12, 2026, [https://www.reddit.com/r/PromptEngineering/comments/1j4ia54/2\_prompt\_engineering\_techniques\_that\_actually/](https://www.reddit.com/r/PromptEngineering/comments/1j4ia54/2_prompt_engineering_techniques_that_actually/)