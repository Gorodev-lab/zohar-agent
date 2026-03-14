#!/usr/bin/env python3
"""
ZOHAR QUEUE INSPECTOR
Muestra el estado de la queue persistente en tiempo real.
Uso: python3 zohar_queue_inspector.py [--watch]
"""
import json
import sys
import os
import time
from pathlib import Path
from datetime import datetime

# Configuración de Rutas Reales (Zohar SRE Production)
BASE_PROJECT = Path("/home/gorops/proyectos antigravity/zohar-agent")
QUEUE_FILE   = BASE_PROJECT / "agent" / "zohar_queue.json"
LOG_FILE     = BASE_PROJECT / "agent" / "zohar_agent.jsonl"
STATE_FILE   = Path.home() / "zohar_agent_state.json"

COLORS = {
    "success": "\033[92m",  # verde
    "failed":  "\033[91m",  # rojo
    "pending": "\033[93m",  # amarillo
    "reset":   "\033[0m",
    "bold":    "\033[1m",
    "blue":    "\033[94m",
    "gray":    "\033[90m",
}

def c(color: str, text: str) -> str:
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"

def load_queue() -> dict:
    if not QUEUE_FILE.exists():
        return {}
    with open(QUEUE_FILE) as f:
        return json.load(f)

def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    with open(STATE_FILE) as f:
        return json.load(f)

def last_log_lines(n: int = 8) -> list[str]:
    if not LOG_FILE.exists():
        return []
    lines = LOG_FILE.read_text().strip().split("\n")
    result = []
    for line in lines[-n:]:
        try:
            entry = json.loads(line)
            ts  = entry.get("ts", "")[-8:]  # solo HH:MM:SS
            lvl = entry.get("level", "")
            msg = entry.get("msg", "")
            color = "gray" if lvl == "DEBUG" else ("red" if lvl in ("ERROR", "WARNING") else "reset")
            result.append(f"  {c('gray', ts)} {c(color, msg[:80])}")
        except Exception:
            result.append(f"  {line[:80]}")
    return result

def print_dashboard():
    os.system("clear")
    queue = load_queue()
    state = load_state()
    now   = datetime.now().strftime("%H:%M:%S")

    # Stats
    total   = len(queue)
    success = sum(1 for v in queue.values() if v["status"] == "success")
    failed  = sum(1 for v in queue.values() if v["status"] == "failed")
    pending = sum(1 for v in queue.values() if v["status"] == "pending")

    print(c("bold", "╔═══════════════════════════════════════════════╗"))
    print(c("bold", "║  ZOHAR QUEUE INSPECTOR v2.0          ") + c("gray", f"{now}") + c("bold", "  ║"))
    print(c("bold", "╚═══════════════════════════════════════════════╝"))
    print()

    # Estado del agente
    action = state.get("action", "?")
    pdf    = state.get("pdf", "?")
    target = state.get("target", "?")
    atime  = state.get("time", "?")
    print(c("bold", "AGENTE ACTUAL"))
    print(f"  Acción  : {c('blue', action)}")
    print(f"  PDF     : {pdf}")
    print(f"  Objetivo: {c('bold', target)}")
    print(f"  Hora    : {atime}")
    print()

    # Queue stats
    print(c("bold", "QUEUE"))
    bar_total = max(total, 1)
    ok_bar  = "█" * int(success / bar_total * 30)
    fa_bar  = "█" * int(failed  / bar_total * 30)
    pe_bar  = "░" * int(pending / bar_total * 30)
    print(f"  {c('success', ok_bar)}{c('failed', fa_bar)}{pe_bar}")
    print(f"  Total:{total}  {c('success','OK:'+str(success))}  "
          f"{c('failed','Fail:'+str(failed))}  "
          f"{c('pending','Pend:'+str(pending))}")
    print()

    # Items fallidos (para debug)
    failed_items = [v for v in queue.values() if v["status"] == "failed"]
    if failed_items:
        print(c("bold", f"FALLIDOS ({len(failed_items)})"))
        for item in failed_items[:5]:
            print(f"  {c('failed', item['pid'])} · err: {item['last_error']} · intentos: {item['attempts']}")
        if len(failed_items) > 5:
            print(f"  ... y {len(failed_items) - 5} más")
        print()

    # Últimas líneas del log
    print(c("bold", "LOG RECIENTE"))
    for line in last_log_lines(8):
        print(line)
    print()
    print(c("gray", "  [Ctrl+C para salir · actualiza cada 3s en --watch]"))

def main():
    watch = "--watch" in sys.argv or "-w" in sys.argv

    if watch:
        try:
            while True:
                print_dashboard()
                time.sleep(3)
        except KeyboardInterrupt:
            print("\nInspector detenido.")
    else:
        print_dashboard()

if __name__ == "__main__":
    main()
