#!/bin/bash
# ==============================================================================
# ZOHAR UNIFIED DEPLOYMENT 
# Script de Arranque Maestro (Fase 2)
# ==============================================================================

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$DIR"

echo "=== Arrancando Zohar Unified Pipeline ==="

# 1. Asegurar entorno virtual
if [ ! -d "venv" ]; then
    echo "❌ Error: Entorno virtual 'venv' no encontrado. Ejecuta Fase 1 primero."
    exit 1
fi

source venv/bin/activate

# 2. Cargar variables de entorno
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
    echo "✅ Entorno cargado (.env)"
else
    echo "⚠️ Advertencia: No se encontró .env"
fi

# 3. Limpiar procesos zombies en puerto 8000
PORT=8000
PID=$(lsof -t -i:$PORT 2>/dev/null || ss -lptn 'sport = :8000' 2>/dev/null | grep -oP 'pid=\K\d+')
if [ ! -z "$PID" ]; then
    echo "⚠️ Detectado proceso zombie ($PID) en puerto $PORT. Deteniendo..."
    kill -9 $PID
    sleep 1
fi

# 4. Iniciar Servidor (FastAPI sirve el Dashboard+API)
echo "🚀 Iniciando Uvicorn en 0.0.0.0:$PORT..."
mkdir -p logs
uvicorn api.main:app --host 0.0.0.0 --port $PORT &> logs/server.log &
MAIN_PID=$!

echo "✅ Servidor iniciado con PID: $MAIN_PID"
echo "📜 Logs disponibles en: logs/server.log"
echo "🌐 URL: http://localhost:$PORT/"
echo "---"
echo "Para verificar el estado, usa: ./scripts/status.sh"
