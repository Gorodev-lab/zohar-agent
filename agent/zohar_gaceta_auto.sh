#!/bin/bash
# 🦾 ZOHAR TOTAL RECALL v4.5 - ULTRA-STABLE SRE
# Optimizado para AMD A8 | Inferencia Controlada

YEAR=${1:-2026}
URL="http://sinat.semarnat.gob.mx/Gaceta/gacetapublicacion/?ai=$YEAR"
WORK_DIR="$HOME/gaceta_work/$YEAR"
CSV_FILE="$HOME/zohar_historico_proyectos.csv"
STATE_FILE="$HOME/zohar_agent_state.json"
MOTOR_URL="http://127.0.0.1:8001/v1/chat/completions"
MODEL="qwen2.5-1.5b-instruct-q4_k_m.gguf"

mkdir -p "$WORK_DIR"

report_state() {
    echo "{\"pdf\": \"$1\", \"action\": \"$2\", \"target\": \"$3\", \"time\": \"$(date +'%H:%M:%S')\"}" > "$STATE_FILE"
}

echo "🔎 Iniciando Scraper Nacional Ultra-Estable ($YEAR)..."

PDF_LINKS=$(curl -sL -m 60 -A "Mozilla/5.0" "$URL" | grep -oE "https?://[^\"]+\.pdf" | sort -u)

for PDF_URL in $PDF_LINKS; do
    FILENAME=$(basename "$PDF_URL")
    report_state "$FILENAME" "Descargando" "Crawler"
    [ ! -f "$WORK_DIR/$FILENAME" ] && curl -sL "$PDF_URL" -o "$WORK_DIR/$FILENAME"
    
    TXT_FILE="$WORK_DIR/${FILENAME%.pdf}.txt"
    [ ! -f "$TXT_FILE" ] && pdftotext -layout "$WORK_DIR/$FILENAME" "$TXT_FILE"
    
    IDS=$(grep -oE "[0-9]{2}[A-Z]{2}[0-9]{4}[A-Z0-9]{2,5}" "$TXT_FILE" | sort -u)
    
    for PID in $IDS; do
        if grep -q "$PID" "$CSV_FILE"; then continue; fi
        
        # VENTANA MÍNIMA (800 chars) para máxima estabilidad
        CONTEXT=$(grep -C 8 "$PID" "$TXT_FILE" | tr -s '[:space:]' ' ' | cut -c1-800)
        
        report_state "$FILENAME" "IA_EXTRACTING" "$PID"
        echo "  🇲🇽 ID: $PID..."

        PROMPT="TEXT: '$CONTEXT'
ID: $PID
EXTRACT: {proyecto, promovente, estado, municipio, riesgo}
OUTPUT JSON ONLY:"

        JSON_PAYLOAD=$(jq -n --arg model "$MODEL" --arg prompt "$PROMPT" \
            '{model: $model, messages: [{role: "user", content: $prompt}], 
              temperature: 0.0, max_tokens: 200, 
              repeat_penalty: 1.1}')
        
        RAW_RESPONSE=$(curl -s --connect-timeout 25 -X POST "$MOTOR_URL" -H "Content-Type: application/json" -d "$JSON_PAYLOAD")
        
        AI_DATA=$(echo "$RAW_RESPONSE" | jq -r '.choices[0].message.content' 2>/dev/null | tr -d '\n\r' | grep -oP '\{.*?\}' | head -n 1)

        if [ ! -z "$AI_DATA" ]; then
            P_NAME=$(echo "$AI_DATA" | jq -r '.proyecto // .ProjectName // .name' 2>/dev/null | tr -d ',')
            PROPONENT=$(echo "$AI_DATA" | jq -r '.promovente // .proponente // .Proponent' 2>/dev/null | tr -d ',')
            ST=$(echo "$AI_DATA" | jq -r '.estado // .State // .state' 2>/dev/null)
            MUN=$(echo "$AI_DATA" | jq -r '.municipio // .Municipality // .city' 2>/dev/null)
            RIESGO=$(echo "$AI_DATA" | jq -r '.riesgo // .Risk // .risk' 2>/dev/null)

            if [ ! -z "$PROPONENT" ] && [ "$PROPONENT" != "null" ]; then
                echo "$YEAR,$PID,$ST,$MUN,$P_NAME,$PROPONENT,$RIESGO" >> "$CSV_FILE"
                echo "  ✅ EXTRAÍDO: $PROPONENT"
                echo -e "[$(date +'%Y-%m-%d %H:%M')] SUCCESS: $PID" >> "$HOME/zohar_updates.log"
            fi
        else
            echo "  ⚠️ Falló extracción para $PID. Respuesta inestable."
        fi
        sleep 5
    done
done
echo "--- ✅ Ciclo Terminado ---"
