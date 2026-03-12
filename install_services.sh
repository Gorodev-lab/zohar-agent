#!/bin/bash
# Script para instalar los servicios de Zohar Agent de manera automática para el usuario actual.
# Se adaptará automáticamente al directorio actual.

echo "🚀 Iniciando configuración de automatización de Zohar Agent..."

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
USER_SYSTEMD_DIR="$HOME/.config/systemd/user"
mkdir -p "$USER_SYSTEMD_DIR"
mkdir -p "$DIR/systemd"

# Llama server (Check if real or mock)
LLAMA_BIN="$HOME/llama.cpp/build/bin/llama-server"
if [ ! -f "$LLAMA_BIN" ]; then
    echo "⚠️ llama-server no encontrado. Usando mock_llama_server.py para el dashboard."
    LLAMA_EXEC="\"$DIR/zohar_venv/bin/python\" \"$DIR/mock_llama_server.py\""
else
    LLAMA_EXEC="\"$LLAMA_BIN\" -m \"$HOME/models/qwen2.5-1.5b-instruct-q4_k_m.gguf\" --host 127.0.0.1 --port 8001 --threads 4 --ctx-size 4096 --batch-size 64"
fi

cat <<EOF > "$DIR/systemd/zohar-llama.service"
[Unit]
Description=Zohar Llama Server (Qwen 1.5B or Mock)
After=network.target

[Service]
Type=simple
ExecStart=$LLAMA_EXEC
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
EOF

# FastAPI API Dashboard
cat <<EOF > "$DIR/systemd/zohar-api.service"
[Unit]
Description=Zohar API Dashboard (FastAPI)
After=network.target zohar-llama.service

[Service]
Type=simple
WorkingDirectory=$DIR/api
Environment="PATH=$DIR/zohar_venv/bin:/usr/bin:/bin"
ExecStart="$DIR/zohar_venv/bin/python" zohar_api.py
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF

# Zohar Agent Daemon
cat <<EOF > "$DIR/systemd/zohar-agent.service"
[Unit]
Description=Zohar Monitoring Agent
After=network.target zohar-api.service

[Service]
Type=simple
WorkingDirectory=$DIR/agent
Environment="PATH=$DIR/zohar_venv/bin:/usr/bin:/bin"
ExecStart="$DIR/zohar_venv/bin/python" -c "import zohar_agent_v2 as z; z.CONFIG['DAEMON_MODE'] = True; z.main()"
Restart=always
RestartSec=15
RestartPreventExitStatus=255

[Install]
WantedBy=default.target
EOF

echo "Copiando archivos .service a ~/.config/systemd/user/"
cp "$DIR/systemd/zohar-llama.service" "$USER_SYSTEMD_DIR/"
cp "$DIR/systemd/zohar-api.service" "$USER_SYSTEMD_DIR/"
cp "$DIR/systemd/zohar-agent.service" "$USER_SYSTEMD_DIR/"

echo "Recargando daemon systemd..."
systemctl --user daemon-reload

echo "Habilitando servicios para inicio automático..."
systemctl --user enable zohar-llama.service
systemctl --user enable zohar-api.service
systemctl --user enable zohar-agent.service

loginctl enable-linger "$USER" 2>/dev/null || true

echo "✅ ¡Configuración automática completada!"
echo ""
echo "COMANDOS ÚTILES:"
echo "- Iniciar todo ahora:   systemctl --user start zohar-llama zohar-api zohar-agent"
echo "- Ver estado llama:     systemctl --user status zohar-llama"
echo "- Ver estado API:       systemctl --user status zohar-api"
echo "- Ver estado Agente:    systemctl --user status zohar-agent"
echo "- Ver logs del Agente:  journalctl --user -fu zohar-agent"
