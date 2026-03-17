---
description: Zohar Agent - Operaciones, arranque, diagnóstico y gestión de datos
---

## Contexto del Proyecto

- **Agente:** Zohar Agent v2.2 — extracción de inteligencia ambiental SEMARNAT
- **Script de control:** `./agent/zohar_ctl.sh`
- **Python env:** `zohar_venv/` (usar `zohar_venv/bin/python`)
- **DB local:** `~/zohar_intelligence.db` (SQLite)
- **DB cloud:** Supabase `monitor_gaceta_eco` (gmrnujwviunegvyuslrs)
- **Dashboard:** `localhost:8081`

## Comandos de Control

// turbo
1. **Arrancar en modo daemon:**
```bash
./agent/zohar_ctl.sh start-daemon
```

// turbo
2. **Ver estado y queue:**
```bash
./agent/zohar_ctl.sh status
```

// turbo
3. **Stream de logs en tiempo real:**
```bash
./agent/zohar_ctl.sh logs
```

// turbo
4. **Reiniciar limpiamente:**
```bash
./agent/zohar_ctl.sh stop && ./agent/zohar_ctl.sh start-daemon
```

// turbo
5. **Retry proyectos fallidos:**
```bash
./agent/zohar_ctl.sh retry-failed
```

// turbo
6. **Resetear y re-escanear todas las Gacetas:**
```bash
./agent/zohar_ctl.sh reset-seen
```

## Sincronización a Supabase

// turbo
7. **Sync incremental solo 2026:**
```bash
zohar_venv/bin/python scripts/sync_to_supabase.py --year 2026
```

// turbo
8. **Sync completo (todos los años):**
```bash
zohar_venv/bin/python scripts/sync_to_supabase.py --full
```

> Nota: El sync en tiempo real ya está integrado en `store_project()`.
> El script manual es para sincronizaciones históricas o de recuperación.

## Diagnóstico Rápido

// turbo
9. **Ver últimos 20 logs del agente:**
```bash
curl -s -H 'bypass-tunnel-reminder: true' http://localhost:8081/api/logs | python3 -c "import json,sys; [print(r['ts'][-8:], r['level'], r['msg']) for r in json.load(sys.stdin)[-20:]]"
```

// turbo
10. **Conteo de proyectos en DB local:**
```bash
zohar_venv/bin/python -c "import sqlite3; from pathlib import Path; c=sqlite3.connect(Path.home()/'zohar_intelligence.db'); print(dict(c.execute('SELECT year, COUNT(*) FROM projects GROUP BY year').fetchall()))"
```

// turbo
11. **Ver proyectos 2026 con coordenadas:**
```bash
zohar_venv/bin/python -c "
import sqlite3; from pathlib import Path
c=sqlite3.connect(Path.home()/'zohar_intelligence.db')
rows=c.execute('SELECT pid, promovente, coordenadas FROM projects WHERE year=2026 AND coordenadas IS NOT NULL LIMIT 10').fetchall()
for r in rows: print(r)
"
```

## Variables de Entorno Requeridas

| Variable | Descripción |
|----------|-------------|
| `GEMINI_API_KEY` | Gemini 2.5-flash + Vision + Search Grounding |
| `SUPABASE_URL` | `https://gmrnujwviunegvyuslrs.supabase.co` |
| `SUPABASE_KEY` | Service role key para escritura |
| `LLAMA_URL` | Endpoint LLM local (fallback) |

## Modelos en Uso

| Rol | Modelo |
|-----|--------|
| Extracción élite + Grounding | `gemini-2.5-flash` |
| OCR de mapas/croquis | `gemini-2.5-flash` (Vision) |
| Fallback local | Mistral/DeepSeek vía Llama.cpp |

## Tabla Supabase — Vista intel_2026

```sql
SELECT * FROM intel_2026
WHERE riesgo_civil = 'ALTO'
ORDER BY confidence_score DESC;
```
