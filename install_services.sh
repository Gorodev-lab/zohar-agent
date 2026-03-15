#!/bin/bash
# ══════════════════════════════════════════════
#  ZOHAR v2.2 — SERVICE INSTALLER (SRE PROTOCOL)
# ══════════════════════════════════════════════

BASE_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SYSTEMD_DIR="/etc/systemd/system"

echo "🛡️  Iniciando despliegue de Servicios de Alta Disponibilidad..."

# Copiar servicios
sudo cp "$BASE_DIR/systemd/zohar-llama.service" "$SYSTEMD_DIR/"
sudo cp "$BASE_DIR/systemd/zohar-agent.service" "$SYSTEMD_DIR/"
sudo cp "$BASE_DIR/systemd/zohar-api.service" "$SYSTEMD_DIR/"

# Recargar systemd
sudo systemctl daemon-reload

# Habilitar servicios para arranque automático
echo "✅ Habilitando zohar-llama..."
sudo systemctl enable zohar-llama
echo "✅ Habilitando zohar-api..."
sudo systemctl enable zohar-api
echo "✅ Habilitando zohar-agent..."
sudo systemctl enable zohar-agent

# Iniciar servicios
echo "🚀 Arrancando servicios..."
sudo systemctl start zohar-llama
sudo systemctl start zohar-api
sudo systemctl start zohar-agent

echo "✨ Despliegue completado y servicios activos."
