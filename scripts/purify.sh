#!/usr/bin/env bash
# scripts/purify.sh — Zohar Refactor & Purify — Fase 6
# Limpia archivos obsoletos, logs acumulados y SQLs ya importados a Supabase.
# USO: bash scripts/purify.sh [--dry-run]
set -euo pipefail

cd "$(dirname "$0")/.."
BASE="$(pwd)"

DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

RED='\033[0;31m'; YLW='\033[1;33m'; GRN='\033[0;32m'; RST='\033[0m'

banner() { echo -e "\n${YLW}=== $* ===${RST}"; }
ok()     { echo -e "  ${GRN}✓${RST} $*"; }
skip()   { echo -e "  ${YLW}↷${RST} $* [no existe, se omite]"; }
dry()    { echo -e "  ${RED}[DRY-RUN]${RST} rm $*"; }

remove_file() {
    local f="$1"
    if [[ -f "$f" ]]; then
        if $DRY_RUN; then dry "$f"; else rm -f "$f"; ok "Eliminado: $f"; fi
    else
        skip "$f"
    fi
}

truncate_file() {
    local f="$1"
    if [[ -f "$f" ]]; then
        if $DRY_RUN; then echo -e "  ${RED}[DRY-RUN]${RST} truncate $f"; else : > "$f"; ok "Truncado: $f"; fi
    else
        skip "$f"
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
banner "ZOHAR PURIFY — $(date '+%Y-%m-%d %H:%M:%S')"
$DRY_RUN && echo -e "  ${RED}Modo DRY-RUN: no se elimina nada${RST}"

# ── 1. Backups innecesarios ───────────────────────────────────────────────────
banner "1/5 · Backups obsoletos"
remove_file "$BASE/agent/zohar_agent_bak.jsonl"
remove_file "$BASE/agent/zohar_queue_bak.json"
remove_file "$BASE/agent/zohar_seen_gacetas_bak.json"
remove_file "$BASE/.env.tmp"

# ── 2. Logs acumulados (truncar, mantener presencia del archivo) ──────────────
banner "2/5 · Logs acumulados"
truncate_file "$BASE/agent/watchdog.log"
truncate_file "$BASE/agent/zohar_agent.jsonl"
truncate_file "$BASE/agent/wget-log"
remove_file   "$BASE/agent/wget-log.1"
truncate_file "$BASE/api_access.log"
truncate_file "$BASE/api_log.txt"
truncate_file "$BASE/api_server.log"
truncate_file "$BASE/llama.log"
truncate_file "$BASE/qwen.log"
truncate_file "$BASE/agent_log.txt"
truncate_file "$BASE/probe.log"
truncate_file "$BASE/api/api_log.txt"

# ── 3. SQLs y CSVs ya importados a Supabase ──────────────────────────────────
banner "3/5 · SQL/CSV importados"
remove_file "$BASE/batch1.sql"
remove_file "$BASE/batch2.sql"
remove_file "$BASE/batch3.sql"
remove_file "$BASE/income_data.sql"
remove_file "$BASE/zoning_data.sql"
remove_file "$BASE/ingresos_2024.csv"
remove_file "$BASE/csv_to_sql.py"

# ── 4. Archivos de primera versión ───────────────────────────────────────────
banner "4/5 · Archivos legacy v1"
remove_file "$BASE/Esoteria_Organizational_Restructure_Doctrine_v1.md"
remove_file "$BASE/PROTOTYPE_ALT_AGENTS.md"
remove_file "$BASE/mock_llama_server.py"
remove_file "$BASE/current_temp_url.txt"
remove_file "$BASE/tunnel_url.txt"
remove_file "$BASE/tunnel_log.txt"

# ── 5. DuckDB duplicado en HOME ───────────────────────────────────────────────
banner "5/5 · DuckDB duplicado"
DUCK_DUP="$HOME/zohar_warehouse.duckdb"
if [[ -f "$DUCK_DUP" ]]; then
    if $DRY_RUN; then
        dry "$DUCK_DUP"
    else
        rm -f "$DUCK_DUP"
        ok "Eliminado: $DUCK_DUP"
    fi
else
    skip "$DUCK_DUP"
fi

# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GRN}┌─────────────────────────────────────────┐${RST}"
echo -e "${GRN}│  ✅  PURIFY COMPLETO                    │${RST}"
$DRY_RUN && echo -e "${RED}│  (DRY-RUN: ningún archivo fue tocado)  │${RST}"
echo -e "${GRN}└─────────────────────────────────────────┘${RST}"
echo ""
echo "  SIGUIENTE PASO: ejecutar purificación de datos en Supabase"
echo "  Ver SKILL.md → Fase 5 para el SQL de purificación."
