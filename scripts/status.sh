#!/bin/bash
# ==============================================================================
# ZOHAR UNIFIED DEPLOYMENT 
# Script de Diagnóstico (Fase 3)
# ==============================================================================

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$DIR"

echo "=== Zohar Status Chequeo ==="

# 1. Verificar Puerto 8000
PORT=8000
PID=$(lsof -t -i:$PORT 2>/dev/null || ss -lptn 'sport = :8000' 2>/dev/null | grep -oP 'pid=\K\d+')

if [ -z "$PID" ]; then
    echo "🔴 Servidor OFFLINE (Puerto $PORT inactivo)"
    echo "  > Revisa los logs en logs/server.log o inicia con ./scripts/start.sh"
    exit 1
else
    echo "🟢 Servidor ONLINE (PID: $PID en Puerto $PORT)"
fi

# 2. Ping a la API de recursos
echo "---"
echo "📡 Llamando a /api/resources..."
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$PORT/api/resources)

if [ "$RESPONSE" == "200" ]; then
    echo "✅ API responde correctamente (HTTP 200)"
else
    echo "⚠️ API responde con error o no responde (HTTP $RESPONSE)"
fi

# 3. Mostrar últimos logs
echo "---"
echo "📄 Últimos logs de ejecución (logs/server.log):"
if [ -f "logs/server.log" ]; then
    tail -n 5 logs/server.log
else
    echo "⚠️ Archivo logs/server.log no encontrado."
fi
