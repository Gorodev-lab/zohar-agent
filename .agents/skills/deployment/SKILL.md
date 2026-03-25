---
name: Zohar Unified Deployment Pipeline
description: Skill para alinear, simplificar y consolidar la tubería de despliegue del Zohar Agent y su Dashboard. Estandariza el entorno virtual, elimina la ambigüedad de servidores y provee un único punto de entrada robusto.
---

# Zohar Unified Deployment Pipeline

## Contexto y Diagnóstico
Actualmente el proyecto sufre de "desorden de servidores" debido a su evolución:
- Dependencias faltantes en el entorno virtual (`uvicorn: command not found` a pesar de estar en `requirements.txt`).
- Múltiples formas de iniciar el agente y la API interactuando entre sí.
- Restos del dashboard antiguo (Next.js) vs el dashboard actual (Legacy estático servido por FastAPI).

## Objetivo
Crear una tubería de despliegue simple, determinista y de **un solo comando** (`./scripts/start.sh`) que:
1. Sincronice el entorno Python (`venv`) estrictamente con `requirements.txt`.
2. Verifique y mate procesos huérfanos (evitar puertos 8000 ocupados).
3. Inicie el servidor unificado (FastAPI + Dashboard estático + Agente).

## Checklist de Ejecución

### Fase 1: Sincronización Estricta del Entorno (`venv`)
- [ ] Verificar la existencia del entorno virtual `venv/`.
- [ ] Ejecutar `pip install -r requirements.txt` para asegurar que dependencias clave (FastAPI, Uvicorn, Supabase, etc.) están instaladas.
- [ ] Validar importaciones críticas (ej. `python3 -c "import uvicorn, fastapi"`).

### Fase 2: Script de Arranque Maestro (`scripts/start.sh`)
- [ ] Crear el script `./scripts/start.sh` con permisos de ejecución (`chmod +x`).
- [ ] Lógica del script:
    1. Buscar y detener procesos de `uvicorn` zombies en el puerto 8000.
    2. Activar `venv/`.
    3. Cargar `.env`.
    4. Iniciar `uvicorn api.main:app --host 0.0.0.0 --port 8000` con manejo correcto de logs (`logs/server.log`).
- [ ] Validar que el servidor arranca y sirve el `dashboard_legacy`.

### Fase 3: Script de Diagnóstico (`scripts/status.sh`)
- [ ] Crear un script `./scripts/status.sh` para comprobar la salud del despliegue:
    - Estado del puerto 8000.
    - Ping al endpoint `/api/resources` para validar que el servidor está vivo.
    - Revisión rápida de errores en `logs/server.log`.

### Fase 4: Limpieza de Despliegues Anteriores
- [ ] Documentar en `README.md` el nuevo método de arranque.
- [ ] Marcar explícitamente el directorio `dashboard/` (Next.js) como "Deprecado/Archivado" en la documentación de despliegue para evitar confusiones de Vercel/Node.js frente al único servidor FastAPI.

---

> **Nota para el Agente:** Sigue este documento paso a paso para estabilizar la infraestructura. Si encuentras errores de dependencias al compilar, asegúrate de documentarlo. Al arrancar `uvicorn`, hazlo de manera que los logs sean fáciles de leer en vivo.
