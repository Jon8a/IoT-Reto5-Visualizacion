"""
Fleet IoT - Configuración del índice en Elasticsearch
======================================================
Crea el index template con el mapping correcto,
especialmente el campo 'location' como geo_point
para que funcione el mapa de Kibana.

Uso:
    pip install elasticsearch python-dotenv
    python scripts/setup_index.py
"""

import os
from elasticsearch import Elasticsearch
from dotenv import load_dotenv

load_dotenv()

ES_HOST = os.getenv("ES_HOST", "http://localhost:9200")
ES_USER = "elastic"
ES_PASS = os.getenv("ELASTIC_PASSWORD", "ElasticPass2024!")


def main():
    print(f"Conectando a Elasticsearch en {ES_HOST}...")
    
    es = Elasticsearch(
        ES_HOST,
        basic_auth=(ES_USER, ES_PASS),
        verify_certs=False,
    )

    # Comprueba conexión
    info = es.info()
    print(f"✅ Conectado. Versión: {info['version']['number']}")

    # ─────────────────────────────────────────
    # INDEX TEMPLATE con mapping
    # ─────────────────────────────────────────
    template = {
        "index_patterns": ["fleet-vehicles-*"],
        "template": {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
            },
            "mappings": {
                "properties": {
                    "@timestamp":       {"type": "date"},
                    "vehicle_id":       {"type": "keyword"},
                    "driver":           {"type": "keyword"},
                    "route_name":       {"type": "keyword"},
                    "location":         {"type": "geo_point"},   # ← clave para el mapa
                    "speed_kmh":        {"type": "float"},
                    "engine_temp_c":    {"type": "float"},
                    "fuel_level_pct":   {"type": "float"},
                    "status":           {"type": "keyword"},
                    "temp_status":      {"type": "keyword"},
                    "processed_by":     {"type": "keyword"},
                }
            }
        }
    }

    es.indices.put_index_template(name="fleet-template", **template)
    print("✅ Index template 'fleet-template' creado correctamente.")
    print("   El índice se creará automáticamente cuando lleguen los primeros datos.")


if __name__ == "__main__":
    main()
