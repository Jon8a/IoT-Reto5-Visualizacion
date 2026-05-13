# 🚛 Fleet IoT - Monitorización de Flota Industrial

Sistema de monitorización en tiempo real de vehículos industriales usando el stack **ELK (Elasticsearch + Logstash + Kibana)**.

---

## 👥 Miembros del equipo

- Jon Ochoa
- Oier Martinez

---

## 🏗️ Arquitectura

```
┌─────────────────┐     TCP/JSON     ┌───────────────┐     HTTP      ┌─────────────────┐
│  Script Python  │ ───────────────► │   Logstash    │ ────────────► │ Elasticsearch 8 │
│ (5 vehículos    │                  │ (filtros y    │               │ (almacena y     │
│  simulados)     │                  │  validación)  │               │  indexa datos)  │
└─────────────────┘                  └───────────────┘               └────────┬────────┘
                                                                              │
                                                                              │ HTTP
                                                                              ▼
                                                                     ┌─────────────────┐
                                                                     │     Kibana      │
                                                                     │  (dashboards,   │
                                                                     │   mapas y       │
                                                                     │   alertas)      │
                                                                     └─────────────────┘
```

---

## 📦 Tecnologías utilizadas

- **Elasticsearch 8** — Almacenamiento y búsqueda de datos IoT
- **Logstash** — Pipeline de ingestión con filtros y validación
- **Kibana** — Visualización, dashboards, mapas y alertas
- **Docker Compose** — Orquestación de servicios
- **Python** — Simulador de flota de vehículos

---

## 🚀 Instrucciones de uso

### Prerrequisitos

- Docker Desktop instalado y en ejecución
- Python 3.9+
- Al menos 4GB de RAM disponible para Docker


### 1. Configurar variables de entorno

```bash
# Copia el archivo de ejemplo (nunca subas .env a GitHub)
cp .env.example .env

# Edita las contraseñas si lo deseas
nano .env
```

### 2. Levantar el stack

```bash
docker compose up -d
```

El proceso tarda ~2 minutos. Puedes ver los logs con:

```bash
docker compose logs -f
```

Cuando veas que el setup ha terminado (`Setup completado!`), continúa.

### 3. Configurar el índice en Elasticsearch

```bash
cd scripts
pip install -r requirements.txt
python setup_index.py
```

### 4. Iniciar el simulador de flota

```bash
python simulate_fleet.py
```

Verás los datos de los 5 camiones en la consola cada 3 segundos. Déjalo corriendo.

### 5. Montar el dashboard y el mapa automáticamente

Abre **otra terminal** y ejecuta:

```bash
python setup_kibana.py
```

Esto crea automáticamente:
- ✅ Index pattern
- ✅ 5 visualizaciones (métricas, velocidad, temperatura, combustible, tabla)
- ✅ Mapa con posición GPS en tiempo real
- ✅ Dashboard principal con todo integrado
- ✅ 3 alertas (velocidad, temperatura, combustible)

### 6. Acceder a Kibana

Abre el navegador en: **http://localhost:5601**

| Usuario    | Contraseña          | Permisos                         |
|------------|---------------------|----------------------------------|
| `elastic`  | `ElasticPass2024!`  | Administrador total              |
| `operador` | `OperatorPass2024!` | Solo lectura de dashboards       |
| `conductor`| `DriverPass2024!`   | Solo lectura de datos de flota   |

> ⚠️ Si cambiaste las contraseñas en `.env`, usa las que hayas configurado.

### 7. Configurar el dashboard

1. Ve a **Analytics → Maps** para ver los vehículos en el mapa
2. Ve a **Analytics → Dashboards** para ver los gráficos
3. Activa el **auto-refresh** en la esquina superior derecha (recomendado: 5s)

---

## 📊 Dashboard incluido

| Gráfico              | Descripción                                     |
|---------------------|-------------------------------------------------|
| 🗺️ Mapa             | Posición en tiempo real de cada vehículo         |
| 📈 Time series       | Evolución de velocidad por vehículo              |
| 🌡️ Gauge             | Temperatura del motor en tiempo real             |
| ⛽ Barras            | Nivel de combustible comparado entre vehículos   |
| 📋 Tabla             | Estado actual de toda la flota                   |
| 🔢 Métricas          | Nº de vehículos activos / en alerta              |

---

## 🔒 Seguridad implementada

- **Autenticación activada** en Elasticsearch 8 (por defecto en v8)
- **3 roles diferenciados**: admin, operador, conductor
- **Contraseñas en variables de entorno** (fichero `.env` excluido de Git)
- **`.gitignore`** configurado para no exponer credenciales

---

## 🚨 Alertas configuradas en Kibana

| Alerta              | Condición                        | Acción          |
|--------------------|----------------------------------|-----------------|
| Velocidad excesiva | `speed_kmh > 120`                | Notificación UI |
| Motor recalentado  | `engine_temp_c > 100`            | Notificación UI |
| Combustible crítico| `fuel_level_pct < 10`            | Notificación UI |

Para configurarlas: **Stack Management → Rules → Create rule → Elasticsearch query**

---

## 🔧 Pasos seguidos

1. Diseño de la arquitectura ELK con Docker Compose
2. Configuración de Elasticsearch 8 con seguridad activada
3. Diseño del pipeline de Logstash con filtros de validación
4. Desarrollo del simulador Python con rutas GPS reales del País Vasco
5. Creación del index template con `geo_point` para el mapa
6. Configuración de roles y usuarios en Elasticsearch
7. Creación del dashboard en Kibana con 6 tipos de gráficos
8. Configuración de alertas automáticas

---

## 🛣️ Posibles vías de mejora

- Conectar con sensores reales via MQTT (broker Mosquitto)
- Añadir Filebeat para captura de logs del sistema
- Implementar ML Anomaly Detection de Kibana
- Despliegue en la nube (Elastic Cloud o AWS)
- Dashboard de Canvas para vista ejecutiva
- Integrar con API de HERE Maps para rutas reales
- Añadir geofencing (alertas cuando un vehículo sale de zona permitida)

---

## ⚠️ Problemas / Retos encontrados

- Elasticsearch 8 tiene seguridad activada por defecto, requirió configurar el servicio `setup` para crear usuarios antes de arrancar Kibana
- El campo `geo_point` debe definirse en el mapping antes de insertar datos, de lo contrario Kibana no reconoce el campo para el mapa
- Logstash tarda más en arrancar que Elasticsearch; los healthchecks de Docker Compose fueron clave para gestionar el orden de arranque

---

## 🔄 Alternativas posibles

| Componente     | Alternativa                        |
|---------------|-------------------------------------|
| Elasticsearch | InfluxDB, TimescaleDB               |
| Kibana        | Grafana, Metabase                   |
| Logstash      | Filebeat, Fluentd, Apache Kafka     |
| Simulador     | Dataset real de Kaggle (GPS tracks) |

---

## 🛑 Parar el stack

```bash
docker compose down

# Para borrar también los datos almacenados:
docker compose down -v
```

---

*Proyecto desarrollado para la asignatura IoT Industrial — Universidad de Deusto, 2026*
*Profesor: Gorka Zárate*
