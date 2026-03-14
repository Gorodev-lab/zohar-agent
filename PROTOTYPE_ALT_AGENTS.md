# Prototype: Alternative Agents (Mistral & Granite)

Este prototipo explora el uso de modelos de mayor capacidad (7B-8B) para mejorar la precisión de la extracción y el razonamiento técnico.

## Rama Git
`prototype-mistral`

## Modelos Incluidos
1.  **DeepSeek-R1 (Qwen 1.5B)**: El modelo base actual. Excelente para razonamiento (CoT) pero con limitaciones por su tamaño en extracciones complejas.
2.  **Mistral-7B-Instruct-v0.3**: ✅ Configurado en esta rama. Un estándar en la industria. Muy robusto y mejor capacidad de síntesis para los "Insights".
3.  **Granite-3.0-8B-Instruct**: Especializado en tareas empresariales y de datos estructurados. Excelente para cumplimiento de esquemas JSON.

## Cómo cambiar de Agente
Se ha incluido un script `switch_agent.sh` en el directorio raíz.

```bash
./switch_agent.sh
```

El script actualizará el archivo `.env` y reiniciará el servidor de inferencia (`zohar-llama`) con el modelo seleccionado.

## Requerimientos de Hardware
Estos modelos (7B-8B) en cuantización Q4_K_M requieren aproximadamente **5GB de RAM**. Se recomienda monitorear el uso de memoria en el dashboard de Zohar.

## Estado de Descarga
- Mistral: ✅ Completado (Mistral-7B-Instruct-v0.3-Q4_K_M.gguf)
- Granite: ✅ Completado (granite-3.0-8b-instruct-Q4_K_M.gguf)
