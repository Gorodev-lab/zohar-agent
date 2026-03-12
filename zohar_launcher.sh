#!/bin/bash
# Zohar Agent App Launcher

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# 1. Asegurar que los servicios estén instalados
if [ ! -f "$HOME/.config/systemd/user/zohar-agent.service" ]; then
    echo "Instalando servicios..."
    bash "$DIR/install_services.sh"
fi

# 2. Iniciar servicios
echo "Iniciando servicios de Zohar..."
systemctl --user start zohar-llama zohar-api zohar-agent

# 3. Esperar a que la API esté lista (máximo 10s)
for i in {1..10}; do
    if curl -s http://localhost:8081 > /dev/null; then
        break
    fi
    sleep 1
done

# 4. Abrir el Dashboard en el navegador
xdg-open http://localhost:8081

# 5. Notificar al sistema
if command -v notify-send > /dev/null; then
    notify-send "Zohar Agent" "Pipeline iniciado y Dashboard desplegado correctamente." --icon="$DIR/zohar_icon.png"
fi
