#!/bin/bash
# ══════════════════════════════════════════════
#  ZOHAR AGENT v2.1 — CONTROL SCRIPT
#  Uso: ./zohar_ctl.sh [start|start-daemon|stop|status|logs|inspect|retry-failed|dry-run|reset-seen]
# ══════════════════════════════════════════════

# Determinar el directorio base dinámicamente
BASE_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"

AGENT_SCRIPT="$BASE_DIR/agent/zohar_agent_v2.py"
INSPECTOR="$BASE_DIR/agent/zohar_queue_inspector.py"
LOG_FILE="$BASE_DIR/agent/zohar_agent.jsonl"
QUEUE_FILE="$BASE_DIR/agent/zohar_queue.json"
SEEN_FILE="$BASE_DIR/agent/zohar_seen_gacetas.json"
PID_FILE="/tmp/zohar_agent_v2.pid"
VENV="$BASE_DIR/zohar_venv"
SENTINEL="$BASE_DIR/agent/zohar_sentinel.py"

CMD=${1:-status}

_activate() {
    source "$VENV/bin/activate" 2>/dev/null || true
}

_is_running() {
    [ -f "$PID_FILE" ] && kill -0 "$(cat $PID_FILE)" 2>/dev/null
}

case "$CMD" in

  start)
    _is_running && echo "⚠️  El agente ya está corriendo (PID $(cat $PID_FILE))" && exit 1
    _activate
    echo "🚀 Iniciando Zohar Agent v2.1 (ciclo único)..."
    nohup python3 "$AGENT_SCRIPT" >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    echo "✅ PID $! — Monitor: ./zohar_ctl.sh inspect"
    ;;

  start-daemon)
    # Modo daemon: monitorea indefinidamente cada N minutos
    _is_running && echo "⚠️  El agente ya está corriendo (PID $(cat $PID_FILE))" && exit 1
    _activate
    
    echo "🔴 Ejecutando limpieza RED..."
    python3 "$SENTINEL" --cleanup
    
    echo "🟢 Validando salud GREEN..."
    if ! python3 "$SENTINEL"; then
        echo "❌ Fallo crítico de salud LLM. Abortando arranque."
        exit 1
    fi

    echo "🚀 Iniciando Zohar Agent v2.2 (modo daemon)..."
    nohup python3 "$AGENT_SCRIPT" --daemon >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    echo "✅ Daemon PID $! — polling cada ${POLL_INTERVAL_MIN:-30} min"
    echo "   Monitor: ./zohar_ctl.sh inspect"
    ;;

  dry-run)
    # Prueba completa sin escribir al CSV ni al grafo
    _is_running && echo "⚠️  Detén el agente antes: ./zohar_ctl.sh stop" && exit 1
    _activate
    echo "🧪 DRY RUN — no se escribirá al CSV ni al grafo"
    python3 "$AGENT_SCRIPT" --dry-run
    ;;

  sweep)
    # Barrido completo de todos los años configurados
    _is_running && echo "⚠️  Detén el agente antes: ./zohar_ctl.sh stop" && exit 1
    _activate
    echo "🧹 Iniciando barrido histórico (2005-2026)..."
    nohup python3 "$AGENT_SCRIPT" >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    echo "✅ PID $! — Monitor: ./zohar_ctl.sh logs"
    ;;

  stop)
    if _is_running; then
        PID=$(cat "$PID_FILE")
        echo "🛑 Deteniendo agente (SIGTERM → PID $PID)..."
        kill -TERM "$PID" 2>/dev/null
        sleep 3
        kill -0 "$PID" 2>/dev/null && kill -KILL "$PID" && echo "   Forzado (SIGKILL)"
        rm -f "$PID_FILE"
        echo "✅ Agente detenido"
    else
        echo "ℹ️  Sin PID activo. Buscando proceso..."
        pkill -f "zohar_agent_v2" && echo "✅ Terminado" || echo "No hay proceso activo"
        rm -f "$PID_FILE"
    fi
    ;;

  status)
    echo "══ ZOHAR AGENT v2.1 STATUS ══"
    _is_running && echo "  🟢 RUNNING (PID $(cat $PID_FILE))" || echo "  🔴 STOPPED"
    [ -f "$HOME/zohar_agent_state.json" ] && echo "  Estado: $(cat $HOME/zohar_agent_state.json)"
    [ -f "$QUEUE_FILE" ] && python3 -c "
import json
q = json.load(open('$QUEUE_FILE'))
s=sum(1 for v in q.values() if v['status']=='success')
f=sum(1 for v in q.values() if v['status']=='failed')
p=sum(1 for v in q.values() if v['status']=='pending')
print(f'  Queue  : Total={len(q)} OK={s} Pending={p} Failed={f}')
"
    [ -f "$SEEN_FILE" ] && python3 -c "
import json
d = json.load(open('$SEEN_FILE'))
print(f'  Gacetas vistas: {list(d.keys())}')
"
    [ -f "$HOME/zohar_historico_proyectos.csv" ] && \
        echo "  CSV rows: $(($(wc -l < $HOME/zohar_historico_proyectos.csv) - 1))"
    ;;

  logs)
    [ ! -f "$LOG_FILE" ] && echo "Sin log: $LOG_FILE" && exit 1
    tail -f "$LOG_FILE" | python3 -u -c "
import sys, json
for line in sys.stdin:
    try:
        e = json.loads(line)
        ts  = e.get('ts','')[-8:]
        lvl = e.get('level','INFO')
        msg = e.get('msg','')
        icons = {'INFO':'ℹ️ ','WARNING':'⚠️ ','ERROR':'❌ ','DEBUG':'·  '}
        print(f\"{ts} {icons.get(lvl,'   ')}{msg}\")
        sys.stdout.flush()
    except:
        print(line.rstrip()); sys.stdout.flush()
"
    ;;

  inspect)
    _activate
    python3 "$INSPECTOR" --watch
    ;;

  retry-failed)
    [ ! -f "$QUEUE_FILE" ] && echo "No hay queue." && exit 1
    python3 -c "
import json
from pathlib import Path
p = Path('$QUEUE_FILE')
q = json.load(open(p))
count = sum(1 for v in q.values() if v['status']=='failed')
for v in q.values():
    if v['status']=='failed':
        v['status']='pending'; v['attempts']=0; v['last_error']=''
json.dump(q, open(p,'w'), indent=2)
print(f'✅ {count} IDs reseteados a pending')
"
    ;;

  reset-seen)
    # Forzar re-procesamiento de todas las gacetas (borra hashes)
    rm -f "$SEEN_FILE"
    echo "✅ Hashes de gacetas borrados — próximo ciclo procesará todo desde cero"
    ;;

  *)
    echo "Uso: $0 [comando]"
    echo ""
    echo "  start         — Ciclo único (descubrir + extraer)"
    echo "  start-daemon  — Monitoreo continuo (polling cada N min)"
    echo "  dry-run       — Prueba sin escribir al CSV"
    echo "  stop          — Detener agente limpiamente"
    echo "  status        — Estado, queue, CSV, gacetas vistas"
    echo "  logs          — Stream de logs en tiempo real"
    echo "  inspect       — Dashboard TUI de la queue"
    echo "  retry-failed  — Resetear IDs fallidos a pendiente"
    echo "  reset-seen    — Forzar re-escaneo de todas las gacetas"
    ;;
esac
