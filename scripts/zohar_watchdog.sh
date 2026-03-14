#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
#  ZOHAR WATCHDOG QA - TUNNEL & RESILIENCE v1.0
#  Mantiene el Dashboard de Vercel conectado al Backend local.
# ═══════════════════════════════════════════════════════════════════

BASE_DIR="/home/gorops/proyectos antigravity/zohar-agent"
TUNNEL_FILE="$BASE_DIR/tunnel_url.txt"
VERCEL_JSON="$BASE_DIR/vercel.json"
VENV_PYTHON="$BASE_DIR/zohar_venv/bin/python3"
LOG_FILE="$BASE_DIR/agent/watchdog.log"

echo "[$(date)] --- INICIANDO QA WATCHDOG ---" >> "$LOG_FILE"

# 1. EJECUTAR PRUEBAS DE CALIDAD (TDD Green Check)
cd "$BASE_DIR"
if ! "$VENV_PYTHON" -m pytest test_quality_assurance.py >> "$LOG_FILE" 2>&1; then
    echo "[$(date)] ⚠️  QA FAILED: Detectada inconsistencia o caída de red." >> "$LOG_FILE"
    
    # Intentar recuperar Túnel
    echo "[$(date)] 🔄 Reiniciando túnel..." >> "$LOG_FILE"
    pkill -f localtunnel
    sleep 2
    
    # Lanzar nuevo túnel (subdominio aleatorio o persistente si se desea)
    # Usamos npx para asegurar disponibilidad
    nohup npx -y localtunnel --port 8081 > "/tmp/new_tunnel.log" 2>&1 &
    sleep 10
    
    # Extraer nueva URL
    NEW_URL=$(grep -oE "https://[a-zA-Z0-9.-]+\.loca\.lt" "/tmp/new_tunnel.log" | head -n 1)
    
    if [ -n "$NEW_URL" ]; then
        echo "[$(date)] ✅ Nuevo túnel: $NEW_URL" >> "$LOG_FILE"
        echo "your url is: $NEW_URL" > "$TUNNEL_FILE"
        
        # Actualizar vercel.json
        sed -i "s|https://.*\.loca\.lt/api/|${NEW_URL}/api/|g" "$VERCEL_JSON"
        
        # Sincronizar con Vercel vía Git (Despliegue automático)
        git add "$VERCEL_JSON" "$TUNNEL_FILE"
        git commit -m "fix(qa): watchdog auto-recovery of tunnel $NEW_URL"
        git push origin master >> "$LOG_FILE" 2>&1
        
        echo "[$(date)] 🚀 Dashboard actualizado y desplegado en Vercel." >> "$LOG_FILE"
    else
        echo "[$(date)] ❌ ERROR: No se pudo obtener nueva URL del túnel." >> "$LOG_FILE"
    fi
else
    echo "[$(date)] 🟢 QA OK: Sistema íntegro." >> "$LOG_FILE"
fi

# El servicio systemd se encargará de re-ejecutarlo cada 60s (RestartSec=60)
echo "[$(date)] --- CICLO QA COMPLETADO ---" >> "$LOG_FILE"
