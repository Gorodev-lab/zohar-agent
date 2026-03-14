#!/bin/bash
# Zohar Agent - Switch AI Engine
# Prototype: prototype-alt-agents

ENV_FILE="/home/gorops/proyectos antigravity/zohar-agent/.env"
MODEL_DIR="/home/gorops/models"

echo "╔══════════════════════════════════════════════╗"
echo "║      ZOHAR AGENT - SWITCH AI ENGINE          ║"
echo "╚══════════════════════════════════════════════╝"

echo "Selecciona el modelo de IA para extracción:"
echo "1) DeepSeek-R1 (Qwen 1.5B) - Ligero / Rápido"
echo "2) Mistral 7B v0.3 - Potente / Balanceado"
echo "3) Granite 3.0 8B - Especializado en RAG y Extracción"
echo "q) Salir"

read -p "Opción [1-3]: " opt

case $opt in
    1)
        MODEL="deepseek-r1-qwen-1.5b-q4_k_m.gguf"
        ;;
    2)
        MODEL="Mistral-7B-Instruct-v0.3-Q4_K_M.gguf"
        ;;
    3)
        MODEL="granite-3.0-8b-instruct-Q4_K_M.gguf"
        ;;
    q)
        exit 0
        ;;
    *)
        echo "Opción inválida."
        exit 1
        ;;
esac

# Verificar si el modelo existe
if [ ! -f "$MODEL_DIR/$MODEL" ]; then
    echo "⚠️ El modelo $MODEL no se encuentra en $MODEL_DIR"
    echo "Descargándolo primero..."
    # Intento de descarga rápida si no existe
    exit 1
fi

# Actualizar .env
sed -i "s/^ZOHAR_MODEL=.*/ZOHAR_MODEL=$MODEL/" "$ENV_FILE"

echo "✅ .env actualizado: ZOHAR_MODEL=$MODEL"

# Actualizar servicio systemd
echo "🔄 Recargando y reiniciando servicios..."
cp "/home/gorops/proyectos antigravity/zohar-agent/systemd/zohar-llama.service" "/home/gorops/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user restart zohar-llama
systemctl --user restart zohar-agent

echo "🚀 ¡Zohar Agent ahora usa $MODEL!"
echo "Revisa el dashboard para ver el cambio en tiempo real."
