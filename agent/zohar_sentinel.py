#!/usr/bin/env python3
import urllib.request
import subprocess
import time
import sys
import logging
import os

logging.basicConfig(level=logging.INFO, format='[SENTINEL] %(levelname)s: %(message)s')
log = logging.getLogger("sentinel")

SERVICES = {
    "llama": "http://127.0.0.1:8001/v1/models",
    "ocr":   "http://127.0.0.1:8002/v1/models",
    "api":   "http://127.0.0.1:8081/api/status"
}

def check_service(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status == 200
    except:
        return False

def cleanup_zombies():
    log.warning("🔴 RED PHASE: Iniciando purga de procesos...")
    # Matar procesos por puerto
    for port in [8001, 8002, 8081]:
        try:
            subprocess.run(["fuser", "-k", f"{port}/tcp"], check=False, stderr=subprocess.DEVNULL)
            log.info(f"   Puerto {port} liberado.")
        except: pass
    
    # Matar procesos por nombre
    patterns = ["llama_cpp.server", "qwen2-vl", "zohar_agent_v2"]
    for p in patterns:
        subprocess.run(["pkill", "-f", p], check=False)
    
    log.info("   ✅ RED PHASE completa.")

def validate_health():
    log.info("🟢 GREEN PHASE: Validando salud de los servicios...")
    # Esperar a Llama (Servicio Core)
    max_retries = 15
    for i in range(max_retries):
        if check_service(SERVICES["llama"]):
            log.info("   ✅ Puerto 8001 (Llama) abierto.")
            return True
        log.info(f"   ⏳ Esperando que Llama levante... ({i}/{max_retries})")
        time.sleep(2)
    return False

def main():
    if "--cleanup" in sys.argv:
        cleanup_zombies()
        return

    if not validate_health():
        log.error("❌ Fallo crítico de salud. Inferencia no disponible.")
        sys.exit(1)
    
    log.info("🚀 SISTEMA LISTO PARA PRODUCCIÓN.")

if __name__ == "__main__":
    main()
