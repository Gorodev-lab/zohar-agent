# Product Requirements Document (PRD)
**ZOHAR SRE LEAN AGENT v2.1**
*National Monitoring Pipeline - Local Deployment Guide*

---

## 1. Resumen Ejecutivo
Zohar Agent es un pipeline agéntico local diseñado para monitorear, descargar y extraer automáticamente información estructurada (via IA) de los proyectos sometidos al Procedimiento de Evaluación de Impacto Ambiental (PEIA) publicados en la Gaceta Ecológica de la SEMARNAT (México).

Este documento detalla los requerimientos y el proceso para instalar y replicar este sistema de manera autónoma en cualquier otra PC local o servidor, priorizando hardware de bajos recursos.

---

## 2. Requerimientos del Sistema

### 2.1 Requerimientos de Hardware (Mínimos / Target)
El sistema fue diseñado originalmente para un entorno restringido (AMD A8-7410, 4GB RAM), por lo que es ultra-ligero.
- **CPU:** Dual-core 2.0 GHz o superior (Soporte AVX2 recomendado para inferencia rápida).
- **RAM:** 4 GB mínimo (8 GB recomendados).
- **Almacenamiento:** Al menos 20 GB de espacio libre (para modelos LLM, PDFs descargados y DB).
- **GPU:** Opcional. Si existe, acelera significativamente la inferencia de Llama.cpp.

### 2.2 Requerimientos de Software (OS & Paquetes)
- **Sistema Operativo:** Linux (Probado exhaustivamente en Arch Linux / Ubuntu).
- **Dependencias Base:**
  - `git`, `curl`, `jq`, `lm_sensors` (para monitoreo térmico).
  - `poppler-utils` (proporciona `pdftotext` para lectura de PDFs).
  - Herramientas de compilación: `build-essential`, `cmake` (necesarios para compilar llama.cpp).
- **Entorno Python:**
  - Python 3.10+
  - `pip`, `venv`

---

## 3. Preparación del Entorno (Guía de Instalación Paso a Paso)

### Paso 1: Dependencias del Sistema (Ejemplo Ubuntu/Debian)
```bash
sudo apt update
sudo apt install -y git curl wget jq lm-sensors poppler-utils build-essential cmake python3 python3-venv python3-pip
```
*(Si usas Arch Linux: `sudo pacman -S git curl wget jq lm_sensors poppler base-devel cmake python python-pip`)*

### Paso 2: Clonar el Repositorio Base
```bash
cd ~
git clone https://github.com/Gorodev-lab/zohar-agent.git
cd zohar-agent
```

### Paso 3: Entorno Virtual Python y Dependencias
Zohar está construido utilizando librerías nativas (`stdlib`) para la extracción y `fastapi` para el panel de control.
```bash
cd ~/zohar-agent
python3 -m venv zohar_venv
source zohar_venv/bin/activate

# Instalar dependencias para el servidor del dashboard
pip install fastapi uvicorn
```

---

## 4. Instalación del Motor de Inferencia (Llama.cpp)

El cerebro de Zohar es un modelo local (Qwen 2.5 1.5B) corriendo sobre `llama-server`.

### 4.1 Compilar llama.cpp
```bash
cd ~
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
mkdir build && cd build
cmake ..  # Si tienes GPU NVIDIA: cmake .. -DGGML_CUDA=ON
cmake --build . --config Release
```

### 4.2 Descargar el Modelo IA
Es imprescindible usar un modelo estructurado y eficiente. Se recomienda **Qwen 2.5 1.5B Instruct** (cuantizado).
```bash
mkdir -p ~/models
cd ~/models
wget https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf
```

---

## 5. Configuración y Estructura de Datos

El agente crea directorios en `~` (HOME) para operar, asegurando la separación entre la lógica del programa y los datos recolectados.

1. **Directorio de Trabajo:** `~/gaceta_work/` (Aquí se descargan PDFs temporales y TXTs).
2. **Directorio de Documentos:** `~/gaceta_work/documentos/` (Almacena Resolutivos y Estudios finales).
3. **Base de Datos:** `~/zohar_historico_proyectos.csv`.
4. **Grafo de Relaciones:** `~/zohar_grafo.triples`.

*(Opcional: Si deseas cambiar estos directorios, edita el diccionario `CONFIG` en `zohar-agent/agent/zohar_agent_v2.py`).*

---

## 6. Despliegue de los Servicios

El sistema requiere dos servicios corriendo en paralelo: El **Motor LLM** y el **Dashboard API**, además del propio ciclo del Agente.

### 6.1 Levantar llama-server (En terminal separada o tmux)
```bash
~/llama.cpp/build/bin/llama-server \
  -m ~/models/qwen2.5-1.5b-instruct-q4_k_m.gguf \
  --host 127.0.0.1 \
  --port 8001 \
  --threads 4 \
  --ctx-size 4096 \
  --batch-size 64
```
*(Asegúrate de que este proceso esté siempre corriendo, ya que el agente lo consume).*

### 6.2 Levantar la API del Dashboard (En terminal separada o tmux)
```bash
cd ~/zohar-agent/api
source ~/zohar-agent/zohar_venv/bin/activate
python zohar_api.py
```
El panel estará disponible en: **http://localhost:8081**

### 6.3 Ejecutar el Agente Extractor
Con el LLM y el servidor listos, inicia el agente. El script `zohar_ctl.sh` administra el ciclo de vida del agente.

```bash
cd ~/zohar-agent/agent

# Arrancar el agente en modo continuo (monitorea indefinidamente)
bash zohar_ctl.sh start-daemon

# Ver el monitor en tiempo real de la extracción (TUI)
bash zohar_ctl.sh inspect
```

---

## 7. Troubleshooting Básico

- **Error: llama-server no responde.**
  Revisar que llama-server esté corriendo en el puerto `8001`. El agente tiene un watchdog y esperará (hasta 60s), pero si no levanta, fallará.
  
- **Error: pdftotext falló.**
  Asegurarse de que el paquete `poppler-utils` (o `poppler`) esté instalado correctamente en el SO.

- **Temperatura Crítica / Pausas Largas.**
  El script `zohar_agent_v2.py` monitorea los sensores térmicos. Si la temperatura pasa de 75°C, el agente bajará el ritmo de inyección de prompts para proteger la placa base. Para desactivarlo, modificar el umbral en `CONFIG["TEMP_WARN"]`.

- **Permisos del script:**
  Si tienes problemas al ejecutar los archivos `.sh`, aplica permisos recursivos: `chmod +x ~/zohar-agent/agent/*.sh`

## 8. Arquitectura Deseada (Estado Target)
El PC de destino debe quedar con 3 puertos operativos locales:
- `:8001` (llama-server / Motor RAG interno)
- `:8081` (Zohar Dashboard Web UI)
- `:18789` (OpenClaw / Opcional para comunicación de múltiples APIs)
