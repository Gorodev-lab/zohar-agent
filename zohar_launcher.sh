#!/bin/bash
# Zohar Agent App Launcher

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# 1. Ejecutar suite TDD (Red/Green) antes de desplegar
echo "Ejecutando suite de calidad (pytest)..."

cd "$DIR" || exit 1

if [ ! -d "zohar_venv" ]; then
    python -m venv zohar_venv
fi

source zohar_venv/bin/activate
pip install -r requirements.txt >/dev/null 2>&1

if ! pytest test_zohar_agent.py test_zohar_api.py; then
    echo "❌ Tests fallaron — no se desplegará el dashboard."
    exit 1
fi

echo "✅ Tests en verde — continuando con el despliegue..."

# 2. Asegurar que los servicios estén instalados
if [ ! -f "/etc/systemd/system/zohar-agent.service" ]; then
    echo "Instalando servicios..."
    bash "$DIR/install_services.sh"
fi

# 3. Iniciar servicios
echo "Iniciando servicios de Zohar..."
sudo systemctl start zohar-llama zohar-api zohar-agent

# 4. Esperar a que la API esté lista (máximo 10s)
for i in {1..10}; do
    if curl -s http://localhost:8081 > /dev/null; then
        break
    fi
    sleep 1
done

# 5. Abrir el Dashboard en el navegador
xdg-open http://localhost:8081

# 6. Notificar al sistema
if command -v notify-send > /dev/null; then
    notify-send "Zohar Agent" "Pipeline iniciado y Dashboard desplegado correctamente." --icon="$DIR/zohar_icon.png"
fi
