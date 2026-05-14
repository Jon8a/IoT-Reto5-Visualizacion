FROM python:3.9-slim

WORKDIR /app

# Instalar dependencias
COPY scripts/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todos los scripts
COPY scripts/ ./scripts/
