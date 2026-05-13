"""
Fleet IoT - Simulador de vehículos industriales
================================================
Simula una flota de camiones moviéndose por el País Vasco.
Envía datos a Logstash via TCP (JSON Lines).

Instalación:
    pip install python-dotenv

Uso:
    python scripts/simulate_fleet.py
"""

import json
import math
import os
import random
import socket
import time
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────
LOGSTASH_HOST = os.getenv("LOGSTASH_HOST", "localhost")
LOGSTASH_PORT = int(os.getenv("LOGSTASH_PORT", 5044))
SEND_INTERVAL_SECONDS = 3   # cada cuántos segundos se envían datos
NUM_VEHICLES = 5             # número de camiones a simular

# ─────────────────────────────────────────
# RUTAS SIMULADAS (coordenadas GPS reales del País Vasco)
# Cada ruta es una lista de waypoints (lat, lon)
# ─────────────────────────────────────────
ROUTES = {
    "CAM-001": {
        "name": "Bilbao → Vitoria-Gasteiz (AP-68)",
        "waypoints": [
            (43.2630, -2.9350), # Bilbao
            (43.2050, -2.8930), # Arrigorriaga
            (43.1360, -2.9550), # Llodio
            (43.0530, -2.9960), # Amurrio / AP-68
            (42.9460, -2.8430), # Altube
            (42.8900, -2.7600), # Letona
            (42.8469, -2.6726), # Vitoria-Gasteiz
        ]
    },
    "CAM-002": {
        "name": "San Sebastián → Bilbao (AP-8)",
        "waypoints": [
            (43.3183, -1.9812), # San Sebastián
            (43.2660, -2.0190), # Lasarte
            (43.2800, -2.1700), # Zarautz
            (43.2800, -2.2560), # Zumaia
            (43.2150, -2.4160), # Elgoibar
            (43.1840, -2.4730), # Eibar
            (43.1690, -2.6320), # Durango
            (43.2180, -2.7300), # Amorebieta
            (43.2320, -2.8450), # Galdakao
            (43.2630, -2.9350), # Bilbao
        ]
    },
    "CAM-003": {
        "name": "Bilbao → Santander (A-8)",
        "waypoints": [
            (43.2630, -2.9350), # Bilbao
            (43.2970, -2.9920), # Barakaldo
            (43.3220, -3.1160), # Muskiz
            (43.3760, -3.2200), # Castro Urdiales
            (43.3980, -3.4210), # Laredo
            (43.3850, -3.7380), # Solares
            (43.4200, -3.8000), # Astillero
            (43.4623, -3.8099), # Santander
        ]
    },
    "CAM-004": {
        "name": "Vitoria → Logroño (A-12 / N-232)",
        "waypoints": [
            (42.8469, -2.6726), # Vitoria
            (42.7480, -2.6950), # Treviño
            (42.6700, -2.7080), # Zambrana
            (42.6000, -2.5500), # Haro
            (42.5000, -2.5000), # Briones
            (42.4500, -2.4600), # Cenicero
            (42.4650, -2.4456), # Logroño
        ]
    },
    "CAM-005": {
        "name": "Pamplona → San Sebastián (A-15)",
        "waypoints": [
            (42.8125, -1.6458), # Pamplona
            (42.9150, -1.8000), # Irurtzun
            (43.0100, -1.8900), # Lekunberri
            (43.1400, -1.9800), # Andoain
            (43.2100, -1.9700), # Hernani
            (43.2660, -2.0190), # Lasarte
            (43.3183, -1.9812), # San Sebastián
        ]
    },
}

# ─────────────────────────────────────────
# ESTADO INICIAL DE CADA VEHÍCULO
# ─────────────────────────────────────────
vehicle_states = {}
for vid, route_data in ROUTES.items():
    vehicle_states[vid] = {
        "route": route_data,
        "waypoint_index": 0,
        "progress": 0.0,        # 0.0 → 1.0 entre waypoints
        "fuel_level": random.uniform(60, 100),
        "engine_temp": random.uniform(70, 85),
        "status": "active",
        "driver": f"Conductor-{vid[-1]}",
    }


def interpolate(p1, p2, t):
    """Interpola linealmente entre dos puntos GPS."""
    lat = p1[0] + (p2[0] - p1[0]) * t
    lon = p1[1] + (p2[1] - p1[1]) * t
    return lat, lon


def update_vehicle(vid):
    """Actualiza el estado del vehículo y devuelve el documento a indexar."""
    state = vehicle_states[vid]
    waypoints = state["route"]["waypoints"]

    # Avanza por la ruta (mucho más rápido para que se vea el movimiento)
    state["progress"] += random.uniform(0.25, 0.45)
    if state["progress"] >= 1.0:
        state["progress"] = 0.0
        state["waypoint_index"] = (state["waypoint_index"] + 1) % (len(waypoints) - 1)
        
        # El repostaje ahora se hace solo si queda muy poco combustible, no en cada vuelta
        if state["fuel_level"] < 5:
            state["fuel_level"] = random.uniform(90, 100)

    wp_idx = state["waypoint_index"]
    p1 = waypoints[wp_idx]
    p2 = waypoints[(wp_idx + 1) % len(waypoints)]
    lat, lon = interpolate(p1, p2, state["progress"])

    # Pequeño ruido GPS para que parezca real
    lat += random.uniform(-0.001, 0.001)
    lon += random.uniform(-0.001, 0.001)

    # Simula velocidad con variación (menos agresiva para no hacer spam, pero con picos)
    speed = random.gauss(95, 18)
    speed = max(0, min(speed, 140))

    # Temperatura del motor sube más rápido si va por encima de 100, y baja más lento
    state["engine_temp"] += (speed - 100) * 0.15 + random.uniform(-0.5, 0.5)
    state["engine_temp"] += (85 - state["engine_temp"]) * 0.05  # Retorno a la media suave
    state["engine_temp"] = max(60, min(state["engine_temp"], 115))

    # Combustible baja rápido para poder ver la alerta en la demo
    state["fuel_level"] -= random.uniform(0.5, 2.5)
    state["fuel_level"] = max(0, state["fuel_level"])

    # Determina estado del vehículo
    if state["fuel_level"] < 10:
        status = "fuel_critical"
    elif state["engine_temp"] > 100:
        status = "overheating"
    elif speed > 120:
        status = "speeding"
    else:
        status = "active"
    state["status"] = status

    return {
        "vehicle_id": vid,
        "driver": state["driver"],
        "route_name": state["route"]["name"],
        "location": {
            "lat": round(lat, 6),
            "lon": round(lon, 6),
        },
        "speed_kmh": round(speed, 1),
        "engine_temp_c": round(state["engine_temp"], 1),
        "fuel_level_pct": round(state["fuel_level"], 1),
        "status": status,
        "@timestamp": datetime.now(timezone.utc).isoformat(),
    }


def send_to_logstash(sock, document):
    """Envía un documento JSON a Logstash via TCP."""
    message = json.dumps(document) + "\n"
    sock.sendall(message.encode("utf-8"))


def main():
    print(f"Conectando a Logstash en {LOGSTASH_HOST}:{LOGSTASH_PORT}...")
    
    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect((LOGSTASH_HOST, LOGSTASH_PORT))
                print(f"✅ Conectado a Logstash. Enviando datos de {NUM_VEHICLES} vehículos...")
                
                while True:
                    for vid in list(ROUTES.keys())[:NUM_VEHICLES]:
                        doc = update_vehicle(vid)
                        send_to_logstash(sock, doc)
                        print(f"  → {doc['vehicle_id']} | {doc['status']:15s} | "
                              f"{doc['speed_kmh']:5.1f} km/h | "
                              f"Temp: {doc['engine_temp_c']:5.1f}°C | "
                              f"Fuel: {doc['fuel_level_pct']:5.1f}%")
                    
                    print(f"  [{datetime.now().strftime('%H:%M:%S')}] Batch enviado. "
                          f"Esperando {SEND_INTERVAL_SECONDS}s...")
                    time.sleep(SEND_INTERVAL_SECONDS)

        except ConnectionRefusedError:
            print(f"⚠️  Logstash no disponible, reintentando en 5s...")
            time.sleep(5)
        except BrokenPipeError:
            print("⚠️  Conexión perdida, reconectando...")
            time.sleep(2)
        except KeyboardInterrupt:
            print("\n🛑 Simulación detenida.")
            break


if __name__ == "__main__":
    main()
