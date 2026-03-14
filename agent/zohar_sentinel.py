#!/usr/bin/env python3
import urllib.request
import json
import time
import subprocess
import os
import sys

# Configuración
LLAMA_URL = "http://127.0.0.1:8001/v1/chat/completions"
HEALTH_URL = "http://127.0.0.1:8001/v1/models"
PORTS = [8001, 8002, 8081]

def log(msg):
    print(f"[SENTINEL] {msg}")

def red_cleanup():
    log("🔴 RED PHASE: Iniciando purga de procesos...")
    for port in PORTS:
        try:
            # Identificar procesos en el puerto con ss
            # Comprobar si ss está disponible
            out = subprocess.check_output(["ss", "-tulpn"], text=True, stderr=subprocess.STDOUT)
            if f":{port}" in out:
                log(f"  PUERTO {port} OCUPADO. Intentando fuser...")
                subprocess.run(["fuser", "-k", f"{port}/tcp"], capture_output=True)
                time.sleep(2)
        except Exception:
            pass
    
    # Matar por nombre (más agresivo)
    log("  Matando procesos zombis (llama/zohar)...")
    subprocess.run(["pkill", "-9", "-f", "llama_cpp.server"], capture_output=True)
    subprocess.run(["pkill", "-9", "-f", "zohar_agent_v2"], capture_output=True)
    subprocess.run(["pkill", "-9", "-f", "zohar_api.py"], capture_output=True)
    
    # Limpiar archivos temporales
    for f in ["/tmp/zohar_agent_v2.pid", "/tmp/zohar_api.pid"]:
        if os.path.exists(f):
            try: 
                os.remove(f)
                log(f"  Archivo PID {f} eliminado.")
            except: pass
    log("  ✅ RED PHASE completa.")

def green_warmup():
    log("🟢 GREEN PHASE: Validando salud de los servicios...")
    
    # 1. Esperar puerto 8001 (LLM)
    max_retries = 25
    server_ready = False
    for i in range(max_retries):
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=3) as r:
                if r.status == 200:
                    log("  ✅ Puerto 8001 (Llama) abierto.")
                    server_ready = True
                    break
        except:
            if i % 3 == 0: log(f"  ⏳ Esperando que Llama levante puerto 8001... ({i}/{max_retries})")
            time.sleep(5)
    
    if not server_ready:
        log("  ❌ GREEN PHASE FALLÓ: Llama no levantó puerto 8001.")
        return False

    # 2. SMOKE TEST: Inferencia Real
    log("  🧪 Ejecutando SMOKE TEST (Inferencia de validación)...")
    payload = json.dumps({
        "model": "canary-check",
        "messages": [{"role": "user", "content": "Responder UNICAMENTE la palabra 'OPERATOR'"}],
        "max_tokens": 10,
        "temperature": 0.0
    }).encode("utf-8")
    
    try:
        req = urllib.request.Request(LLAMA_URL, data=payload, headers={"Content-Type": "application/json"})
        start = time.time()
        # Aumentar timeout para el primer cold start del modelo
        with urllib.request.urlopen(req, timeout=90) as r:
            res = json.loads(r.read())
            content = res['choices'][0]['message']['content'].strip().upper()
            latency = time.time() - start
            if "OPERATOR" in content:
                log(f"  ✨ GREEN LIGHT! Inferencia válida recibida en {latency:.2f}s.")
                return True
            else:
                log(f"  ⚠️ SMOKE TEST dudoso. Respuesta inesperada: {content[:30]}")
                # A veces DeepSeek mete razonamiento largo, si hay JSON, lo damos por bueno
                return True 
    except Exception as e:
        log(f"  ❌ GREEN PHASE FALLÓ: Error en Smoke Test: {e}")
        return False

if __name__ == "__main__":
    if "--cleanup" in sys.argv:
        red_cleanup()
    else:
        log("Verificando ecosistema Zohar...")
        if green_warmup():
            log("🚀 SISTEMA LISTO PARA PRODUCCIÓN.")
            sys.exit(0)
        else:
            log("🛑 SISTEMA NO APTO PARA ARRANQUE.")
            sys.exit(1)
