from fastapi import FastAPI, Request
import uvicorn
import re
import json

app = FastAPI()

def heuristic_extract(text, pid):
    """
    Mejorado para extraer datos reales de la Gaceta SEMARNAT.
    """
    res = {
        "proyecto": "EXTRACCIÓN AUTOMÁTICA",
        "promovente": "DESCONOCIDO",
        "estado": "MÉXICO",
        "municipio": "GENÉRICO",
        "riesgo": "bajo"
    }

    # Limpiar el texto de múltiples espacios para facilitar regex
    clean_text = re.sub(r'\s+', ' ', text)
    
    # 1. Buscar el promovente
    # En la tabla: ID | PROMOVENTE | PROYECTO
    # El promovente suele venir justo después del ID.
    # Ejemplo: 31YU2025TD175 DAVID ANTONIO GONZALEZ SALAS CASA WYD
    match_prom = re.search(rf'{pid}\s+([A-Z\s,]{{10,150}}?)\s{{2,}}', text)
    if not match_prom:
        # Intento 2: si no hay 2 espacios, buscamos hasta que veamos una palabra descriptiva como "MIA", "PROYECTO", "REHABILITACION"
        match_prom = re.search(rf'{pid}\s+([A-Z\s,]{{5,100}})', clean_text)
    
    if match_prom:
        res["promovente"] = match_prom.group(1).strip()

    # 2. Proyecto
    # Suele estar después del promovente.
    # O podemos buscar "PROYECTO DENOMINADO..." en el párrafo descriptivo
    proj_patterns = [
        r'DENOMINADO\s+“?([^”"]{10,100})”?',
        r'PROYECTO\s+“?([^”"]{10,100})”?',
        r'CONSISTE EN\s+([A-Z][a-z\s,]{10,150})'
    ]
    for p in proj_patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            res["proyecto"] = m.group(1).strip().upper()
            break

    # 3. Estado y Municipio
    # Buscamos patrones de ubicación
    loc_match = re.search(r'MUNICIPIO DE\s+([A-Z\s]+),\s+ESTADO DE\s+([A-Z\s]+)', text, re.IGNORECASE)
    if loc_match:
        res["municipio"] = loc_match.group(1).strip().upper()
        res["estado"] = loc_match.group(2).strip().upper()
    else:
        # Fallback: intentar pescar palabras en mayúsculas antes del PID si estamos en modo tabla
        words = text.split()
        try:
            pid_idx = words.index(pid)
            if pid_idx > 2:
                # Evitar pescar ruidos de tabla (EL ID antes del PID)
                cand_mun = words[pid_idx-1]
                if cand_mun.upper() in ["ID", "EL", "MUNICIPIO"]:
                    res["municipio"] = "GENÉRICO"
                else:
                    res["municipio"] = cand_mun
                res["estado"] = words[pid_idx-2]
        except:
            pass

    # 4. Riesgo
    t = text.lower()
    if any(k in t for k in ["minería", "tóxico", "residuo", "química", "eléctrica", "asfalto"]):
        res["riesgo"] = "alto"
    elif any(k in t for k in ["hotel", "casa", "fraccionamiento", "puente", "carretera", "turístico"]):
        res["riesgo"] = "medio"
    
    return res

@app.get("/health")
def health(): return {"status": "ok"}

@app.post("/v1/chat/completions")
async def completions(request: Request):
    body = await request.json()
    prompt = body["messages"][0]["content"]
    
    # Nuevo regex para el prompt XML
    pid_m = re.search(r'proyecto\s+([\w\d]+)', prompt)
    pid = pid_m.group(1) if pid_m else "UNK"
    
    context_m = re.search(r'<texto_gaceta_crudo>(.*?)</texto_gaceta_crudo>', prompt, re.DOTALL)
    context = context_m.group(1).strip() if context_m else ""
    
    data = heuristic_extract(context, pid)
    
    # Simular razonamiento doctoral
    razonamiento = f"Analizando el ID {pid}. Se detecta contexto geográfico y técnico. Procediendo a la síntesis abstractiva."
    
    response_content = f"<razonamiento>{razonamiento}</razonamiento>\n<output_json>\n{json.dumps(data, indent=2)}\n</output_json>"
    
    return {
        "choices": [{"message": {"content": response_content}}]
    }

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
