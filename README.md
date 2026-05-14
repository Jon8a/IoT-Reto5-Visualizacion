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
│ Contenedor      │ ───────────────► │   Logstash    │ ────────────► │ Elasticsearch 8 │
│ Simulador       │                  │ (filtros y    │               │ (almacena y     │
│ (5 vehículos)   │                  │  validación)  │               │  indexa datos)  │
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
- **Python (Dockerizado)** — Simulador de flota y automatización del despliegue

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

Cuando el proceso termine y el contenedor `kibana-setup` muestre éxito, toda la simulación estará enviando datos automáticamente a Elasticsearch.

### 3. Acceder a Kibana

Abre el navegador en: **http://localhost:5601**

| Usuario    | Contraseña          | Permisos                         |
|------------|---------------------|----------------------------------|
| `elastic`  | `ElasticPass2024!`  | Administrador total              |
| `operador` | `OperatorPass2024!` | Solo lectura de dashboards       |
| `conductor`| `DriverPass2024!`   | Solo lectura de su vehículo (DLS)|

> ⚠️ Si cambiaste las contraseñas en `.env`, usa las que hayas configurado.

### 4. Configurar el dashboard

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
| ⛽ Barras            | Nivel de combustible actual (en tiempo real)     |
| 📋 Tabla             | Estado actual de toda la flota                   |
| 🔢 Métricas          | Nº de vehículos activos / en alerta              |

---

## 🔒 Seguridad implementada

- **Autenticación activada** en Elasticsearch 8 (por defecto en v8)
- **3 roles diferenciados**: admin, operador, conductor
- **Document Level Security (DLS)**: El rol de conductor utiliza seguridad a nivel de documento dinámico (`_user.full_name`) para ver única y exclusivamente la telemetría de su vehículo asignado. Se habilita automáticamente una licencia Trial de 30 días en el setup para esta función.
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
4. Desarrollo y contenerización del simulador Python con rutas GPS reales del País Vasco
5. Creación del index template con `geo_point` para el mapa
6. Configuración de roles y usuarios en Elasticsearch (con licencia Trial automatizada)
7. Creación del dashboard en Kibana con 6 tipos de gráficos
8. Configuración de alertas automáticas
9. Automatización de despliegue "Zero-touch" integrando el setup de Kibana y el simulador en Docker Compose

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

- **Seguridad nativa**: Elasticsearch 8 tiene seguridad activada por defecto, requirió configurar el servicio `setup` para crear usuarios y roles de forma automatizada antes de arrancar Kibana.
- **Mapeos dinámicos y Race Conditions**: El campo `geo_point` de localización debe definirse antes de insertar datos. Si el simulador envía datos antes de crear el template, Elasticsearch infería tipos erróneos (`text` en lugar de `keyword` para IDs, rompiendo agregaciones de Kibana). Esto se solucionó moviendo la inyección del Index Template al contenedor de setup en Docker Compose, garantizando el orden correcto de inicialización.
- **Sincronización de contenedores**: Logstash tarda más en arrancar que Elasticsearch; los healthchecks de Docker Compose fueron clave para gestionar el orden de arranque de toda la pila.
- **Limitaciones de visualizaciones Kibana**: Ordenar buckets de "Terms" por métricas de "Top Hits" (para mostrar valores actuales de combustible) no está permitido directamente. Se resolvió ordenando alfabéticamente por la clave (`_key`).

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

