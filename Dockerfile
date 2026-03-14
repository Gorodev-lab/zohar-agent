# Zohar Agent & API - Docker Infrastructure v1.0
FROM python:3.11-slim

# Evitar prompts de debconf
ENV DEBIAN_FRONTEND=noninteractive

# Instalar dependencias de sistema (Poppler para PDF, Chrome para Selenium)
RUN apt-get update && apt-get install -y \
    poppler-utils \
    wget \
    gnupg \
    unzip \
    curl \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y \
    google-chrome-stable \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Copiar requerimientos e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código
COPY . .

# Exponer el puerto de la API
EXPOSE 8081

# Script de entrada para manejar doble servicio (opcional, o usar compose)
# Para este Dockerfile, ejecutaremos la API por defecto
CMD ["uvicorn", "api.zohar_api:app", "--host", "0.0.0.0", "--port", "8081"]
