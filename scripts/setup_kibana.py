"""
Fleet IoT - Setup automático de Kibana
=======================================
Crea via API:
  1. Index pattern  → fleet-vehicles-*
  2. Visualizaciones → velocidad, temperatura, combustible, estado, métricas
  3. Mapa           → posición GPS de los vehículos
  4. Dashboard      → todos los paneles juntos
  5. Alertas        → velocidad, temperatura, combustible

Uso:
    python scripts/setup_kibana.py

Nota: ejecutar DESPUÉS de que haya datos en Elasticsearch
(espera unos segundos tras iniciar simulate_fleet.py)
"""

import os
import time
import json
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

KIBANA_HOST = os.getenv("KIBANA_HOST", "localhost")
ES_HOST     = os.getenv("ES_HOST", "localhost")
KIBANA_URL  = f"http://{KIBANA_HOST}:{os.getenv('KIBANA_PORT', 5601)}"
ES_URL      = f"http://{ES_HOST}:{os.getenv('ES_PORT', 9200)}"
ELASTIC_USER = "elastic"
ELASTIC_PASS = os.getenv("ELASTIC_PASSWORD", "ElasticPass2024!")

AUTH    = HTTPBasicAuth(ELASTIC_USER, ELASTIC_PASS)
HEADERS = {"kbn-xsrf": "true", "Content-Type": "application/json"}


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def kibana_post(path, body):
    r = requests.post(f"{KIBANA_URL}{path}", headers=HEADERS, auth=AUTH,
                      json=body, timeout=30)
    if r.status_code not in (200, 201):
        print(f"  ⚠️  POST {path} → {r.status_code}: {r.text[:200]}")
    return r

def kibana_upsert(path, body):
    """POST con overwrite=true → crea o sobreescribe el objeto (Kibana 8.x)."""
    r = requests.post(f"{KIBANA_URL}{path}?overwrite=true", headers=HEADERS, auth=AUTH,
                      json=body, timeout=30)
    if r.status_code not in (200, 201):
        print(f"  ⚠️  POST {path} → {r.status_code}: {r.text[:200]}")
    return r

def wait_for_kibana():
    print("⏳ Esperando a que Kibana esté disponible...")
    for i in range(30):
        try:
            r = requests.get(f"{KIBANA_URL}/api/status", auth=AUTH, timeout=5)
            if r.status_code == 200:
                data = r.json()
                if data.get("status", {}).get("overall", {}).get("level") == "available":
                    print("✅ Kibana disponible!\n")
                    return True
        except Exception:
            pass
        print(f"   ... intento {i+1}/30")
        time.sleep(10)
    raise RuntimeError("Kibana no respondió a tiempo.")


# ─────────────────────────────────────────────────────────────
# 1. INDEX PATTERN
# ─────────────────────────────────────────────────────────────

INDEX_PATTERN_ID = "fleet-vehicles-pattern"

def create_index_pattern():
    print("📋 Creando index pattern...")
    body = {
        "attributes": {
            "title":         "fleet-vehicles-*",
            "timeFieldName": "@timestamp",
        }
    }
    r = kibana_upsert(f"/api/saved_objects/index-pattern/{INDEX_PATTERN_ID}", body)
    if r.status_code in (200, 201):
        print("   ✅ Index pattern creado.\n")
    return INDEX_PATTERN_ID


# ─────────────────────────────────────────────────────────────
# 2. VISUALIZACIONES
# ─────────────────────────────────────────────────────────────

def create_visualization(vis_id, title, vis_state, search_source=None):
    if search_source is None:
        search_source = {
            "index": INDEX_PATTERN_ID,
            "query": {"language": "kuery", "query": ""},
            "filter": []
        }
    body = {
        "attributes": {
            "title":             title,
            "visState":          json.dumps(vis_state),
            "uiStateJSON":       "{}",
            "description":       "",
            "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps(search_source)}
        }
    }
    r = kibana_upsert(f"/api/saved_objects/visualization/{vis_id}", body)
    ok = r.status_code in (200, 201)
    print(f"   {'✅' if ok else '❌'} {title}")
    return vis_id


def create_all_visualizations():
    print("📊 Creando visualizaciones...")

    # ── Métrica: total vehículos activos ──────────────────────
    create_visualization(
        "fleet-metric-active", "Vehículos Activos",
        {
            "title": "Vehículos Activos",
            "type": "metric",
            "params": {
                "addTooltip": True, "addLegend": False, "type": "metric",
                "metric": {"percentageMode": False, "useRanges": False,
                           "colorSchema": "Green to Red", "metricColorMode": "None",
                           "colorsRange": [{"from": 0, "to": 10000}],
                           "labels": {"show": True}, "invertColors": False,
                           "style": {"bgFill": "#000", "bgColor": False,
                                     "labelColor": False, "subText": "",
                                     "fontSize": 60}}
            },
            "aggs": [
                {"id": "1", "enabled": True, "type": "cardinality", "schema": "metric",
                 "params": {"field": "vehicle_id", "customLabel": "Vehículos activos"}}
            ]
        }
    )

    # ── Tabla: Alertas por Tipo ──────────────────────────
    create_visualization(
        "fleet-metric-alerts", "Alertas por Tipo",
        {
            "title": "Alertas por Tipo",
            "type": "table",
            "params": {
                "perPage": 10, "showPartialRows": False, "showMetricsAtAllLevels": False, 
                "sort": {"columnIndex": 1, "direction": "desc"}, "showTotal": False, "totalFunc": "sum"
            },
            "aggs": [
                {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {"customLabel": "Total de Eventos"}},
                {"id": "2", "enabled": True, "type": "filters", "schema": "bucket",
                 "params": {"filters": [
                     {"input": {"query": "status:speeding", "language": "kuery"}, "label": "⚡ Exceso Velocidad"},
                     {"input": {"query": "status:overheating", "language": "kuery"}, "label": "🌡️ Motor Recalentado"},
                     {"input": {"query": "status:fuel_critical", "language": "kuery"}, "label": "⛽ Combustible Crítico"}
                 ]}}
            ]
        }
    )

    # ── Time series: velocidad media por vehículo ─────────────
    create_visualization(
        "fleet-timeseries-speed", "Velocidad por Vehículo (tiempo real)",
        {
            "title": "Velocidad por Vehículo (tiempo real)",
            "type": "line",
            "params": {
                "type": "line", "grid": {"categoryLines": False},
                "categoryAxes": [{"id": "CategoryAxis-1", "type": "category",
                                  "position": "bottom", "show": True,
                                  "style": {}, "scale": {"type": "linear"},
                                  "labels": {"show": True, "truncate": 100},
                                  "title": {}}],
                "valueAxes": [{"id": "ValueAxis-1", "name": "LeftAxis-1",
                               "type": "value", "position": "left", "show": True,
                               "style": {}, "scale": {"type": "linear", "mode": "normal"},
                               "labels": {"show": True, "rotate": 0, "filter": False,
                                          "truncate": 100},
                               "title": {"text": "km/h"}}],
                "seriesParams": [{"show": True, "type": "line", "mode": "normal",
                                  "data": {"label": "Velocidad media", "id": "1"},
                                  "valueAxis": "ValueAxis-1", "drawLinesBetweenPoints": True,
                                  "lineWidth": 2, "showCircles": True}],
                "addTooltip": True, "addLegend": True, "legendPosition": "right",
                "times": [], "addTimeMarker": False
            },
            "aggs": [
                {"id": "1", "enabled": True, "type": "avg", "schema": "metric",
                 "params": {"field": "speed_kmh", "customLabel": "Velocidad media (km/h)"}},
                {"id": "2", "enabled": True, "type": "date_histogram", "schema": "segment",
                 "params": {"field": "@timestamp", "useNormalizedEsInterval": True,
                            "interval": "auto", "drop_partials": False,
                            "min_doc_count": 1, "extended_bounds": {}}},
                {"id": "3", "enabled": True, "type": "terms", "schema": "group",
                 "params": {"field": "vehicle_id", "orderBy": "1", "order": "desc",
                            "size": 5, "otherBucket": False, "otherBucketLabel": "Other",
                            "missingBucket": False, "missingBucketLabel": "Missing",
                            "customLabel": "Vehículo"}}
            ]
        }
    )

    # ── Gauge: temperatura media del motor ────────────────────
    create_visualization(
        "fleet-gauge-temp", "Temperatura del Motor",
        {
            "title": "Temperatura del Motor",
            "type": "gauge",
            "params": {
                "type": "gauge", "addTooltip": True, "addLegend": False,
                "isDisplayWarning": False,
                "gauge": {
                    "verticalSplit": False, "extendRange": True,
                    "percentageMode": False,
                    "gaugeType": "Arc",
                    "gaugeStyle": "Full",
                    "backStyle": "Full",
                    "orientation": "vertical",
                    "colorSchema": "Green to Red",
                    "gaugeColorMode": "Labels",
                    "colorsRange": [
                        {"from": 0,   "to": 85},
                        {"from": 85,  "to": 100},
                        {"from": 100, "to": 120}
                    ],
                    "invertColors": False,
                    "labels": {"show": True, "color": "black"},
                    "scale": {"show": True, "labels": False, "color": "#333"},
                    "type": "meter",
                    "style": {"bgWidth": 0.9, "width": 0.9, "mask": False,
                              "bgMask": False, "maskBars": 50, "bgFill": "#eee",
                              "bgColor": False, "subText": "°C", "fontSize": 60,
                              "labelColor": True}
                }
            },
            "aggs": [
                {"id": "1", "enabled": True, "type": "avg", "schema": "metric",
                 "params": {"field": "engine_temp_c", "customLabel": "Temp. media motor (°C)"}},
                {"id": "2", "enabled": True, "type": "terms", "schema": "group",
                 "params": {"field": "vehicle_id", "orderBy": "1", "order": "desc",
                            "size": 5, "customLabel": "Vehículo"}}
            ]
        }
    )

    # ── Barras: nivel de combustible por vehículo ─────────────
    create_visualization(
        "fleet-bar-fuel", "Nivel de Combustible por Vehículo",
        {
            "title": "Nivel de Combustible por Vehículo",
            "type": "histogram",
            "params": {
                "type": "histogram", "grid": {"categoryLines": False},
                "categoryAxes": [{"id": "CategoryAxis-1", "type": "category",
                                  "position": "bottom", "show": True,
                                  "style": {}, "scale": {"type": "linear"},
                                  "labels": {"show": True, "truncate": 100},
                                  "title": {}}],
                "valueAxes": [{"id": "ValueAxis-1", "name": "LeftAxis-1",
                               "type": "value", "position": "left", "show": True,
                               "style": {}, "scale": {"type": "linear", "mode": "normal"},
                               "labels": {"show": True, "rotate": 0, "filter": False,
                                          "truncate": 100},
                               "title": {"text": "%"}}],
                "seriesParams": [{"show": True, "type": "histogram", "mode": "stacked",
                                  "data": {"label": "Combustible %", "id": "1"},
                                  "valueAxis": "ValueAxis-1",
                                  "drawLinesBetweenPoints": True,
                                  "lineWidth": 2, "showCircles": True}],
                "addTooltip": True, "addLegend": True, "legendPosition": "right",
                "times": [], "addTimeMarker": False
            },
            "aggs": [
                {"id": "1", "enabled": True, "type": "top_hits", "schema": "metric",
                 "params": {"field": "fuel_level_pct", "aggregate": "min", "size": 1, "sortField": "@timestamp", "sortOrder": "desc", "customLabel": "Nivel Actual (%)"}},
                {"id": "2", "enabled": True, "type": "terms", "schema": "segment",
                 "params": {"field": "vehicle_id", "orderBy": "_key", "order": "desc",
                            "size": 5, "customLabel": "Vehículo"}}
            ]
        }
    )

    # ── Tabla: estado actual de la flota ──────────────────────
    create_visualization(
        "fleet-table-status", "Estado Actual de la Flota",
        {
            "title": "Estado Actual de la Flota",
            "type": "table",
            "params": {
                "perPage": 10, "showPartialRows": False,
                "showMetricsAtAllLevels": False, "sort": {"columnIndex": None,
                                                          "direction": None},
                "showTotal": False, "totalFunc": "sum",
                "percentageCol": ""
            },
            "aggs": [
                {"id": "1", "enabled": True, "type": "top_hits", "schema": "metric",
                 "params": {"field": "status", "aggregate": "concat", "size": 1, "sortField": "@timestamp", "sortOrder": "desc", "customLabel": "Estado Actual"}},
                {"id": "3", "enabled": True, "type": "top_hits", "schema": "metric",
                 "params": {"field": "route_name", "aggregate": "concat", "size": 1, "sortField": "@timestamp", "sortOrder": "desc", "customLabel": "Ruta"}},
                {"id": "4", "enabled": True, "type": "top_hits", "schema": "metric",
                 "params": {"field": "speed_kmh", "aggregate": "concat", "size": 1, "sortField": "@timestamp", "sortOrder": "desc", "customLabel": "Velocidad (km/h)"}},
                {"id": "2", "enabled": True, "type": "terms", "schema": "bucket",
                 "params": {"field": "vehicle_id", "orderBy": "_key", "order": "asc", "size": 10, "customLabel": "Vehículo"}}
            ]
        }
    )

    print()


# ─────────────────────────────────────────────────────────────
# 3. MAPA
# ─────────────────────────────────────────────────────────────

MAP_ID = "fleet-map-vehicles"

def create_map():
    print("🗺️  Creando mapa...")
    body = {
        "attributes": {
            "title": "Mapa - Posición de la Flota en Tiempo Real",
            "description": "Posición GPS en tiempo real de todos los vehículos",
            "mapStateJSON": json.dumps({
                "zoom": 8,
                "center": {"lon": -2.5, "lat": 43.1},
                "timeFilters": {"from": "now-15m", "to": "now"},
                "refreshConfig": {"isPaused": False, "interval": 5000},
                "query": {"language": "kuery", "query": ""},
                "filters": [],
                "settings": {
                    "autoFitToDataBounds": True,
                    "backgroundColor": "#ffffff",
                    "disableInteractive": False,
                    "disableTooltipControl": False,
                    "hideToolbarOverlay": False,
                    "hideLayerControl": False,
                    "hideViewControl": False,
                    "initialLocation": "LAST_SAVED_LOCATION",
                    "fixedLocation": {"lat": 0, "lon": 0, "zoom": 2},
                    "browserLocation": {"zoom": 2},
                    "maxZoom": 24,
                    "minZoom": 0,
                    "showScaleControl": False,
                    "showSpatialFilters": True,
                    "showTimesliderToggleButton": True,
                    "spatialFiltersAlpa": 0.3,
                    "spatialFiltersFillColor": "#DA8B45",
                    "spatialFiltersLineColor": "#DA8B45"
                }
            }),
            "layerListJSON": json.dumps([
                # Capa base: mapa de calles
                {
                    "id": "base-layer",
                    "label": "Mapa base",
                    "minZoom": 0, "maxZoom": 24,
                    "alpha": 1,
                    "visible": True,
                    "style": {"type": "TILE", "properties": {}},
                    "type": "EMS_VECTOR_TILE",
                    "sourceDescriptor": {
                        "type": "EMS_TMS",
                        "id": "road_map",
                        "isAutoSelect": True
                    }
                },
                # Capa de vehículos
                {
                    "id": "vehicles-layer",
                    "label": "Vehículos",
                    "minZoom": 0, "maxZoom": 24,
                    "alpha": 1,
                    "visible": True,
                    "style": {
                        "type": "VECTOR",
                        "properties": {
                            "fillColor": {
                                "type": "DYNAMIC",
                                "options": {
                                    "field": {"name": "status", "origin": "source"},
                                    "color": "status",
                                    "fieldMetaOptions": {"isEnabled": True,
                                                        "sigma": 3},
                                    "type": "CATEGORICAL",
                                    "useCustomColorPalette": False,
                                    "colorCategory": "palette_0",
                                    "customColorPalette": [
                                        {"stop": "active",        "color": "#54B399"},
                                        {"stop": "speeding",      "color": "#F1D86F"},
                                        {"stop": "overheating",   "color": "#D36086"},
                                        {"stop": "fuel_critical", "color": "#E7664C"}
                                    ]
                                }
                            },
                            "lineColor": {"type": "STATIC",
                                          "options": {"color": "#fff"}},
                            "lineWidth": {"type": "STATIC", "options": {"size": 1}},
                            "iconSize": {"type": "STATIC", "options": {"size": 14}},
                            "icon": {"type": "STATIC",
                                     "options": {"value": "vehicle"}},
                            "labelText": {
                                "type": "DYNAMIC",
                                "options": {
                                    "field": {"name": "vehicle_id", "origin": "source"}
                                }
                            },
                            "labelSize": {"type": "STATIC", "options": {"size": 12}},
                            "labelColor": {"type": "STATIC",
                                           "options": {"color": "#000000"}},
                            "labelBorderColor": {"type": "STATIC",
                                                 "options": {"color": "#FFFFFF"}},
                            "labelBorderSize": {"options": {"position": "OUTSIDE"}}
                        }
                    },
                    "type": "GEOJSON_VECTOR",
                    "sourceDescriptor": {
                        "id": "vehicles-source",
                        "type": "ES_SEARCH",
                        "geoField": "location",
                        "limit": 10000,
                        "filterByMapBounds": False,
                        "tooltipProperties": [
                            "vehicle_id", "driver", "route_name",
                            "speed_kmh", "engine_temp_c",
                            "fuel_level_pct", "status"
                        ],
                        "sortField": "@timestamp",
                        "sortOrder": "desc",
                        "scalingType": "TOP_HITS",
                        "topHitsSize": 1,
                        "topHitsSplitField": "vehicle_id",
                        "indexPatternId": INDEX_PATTERN_ID,
                        "applyGlobalQuery": True,
                        "applyGlobalTime": True,
                        "applyForceRefresh": True
                    },
                    "joins": []
                }
            ]),
            "uiStateJSON": "{}"
        },
        "references": []
    }

    r = kibana_upsert(f"/api/saved_objects/map/{MAP_ID}", body)
    ok = r.status_code in (200, 201)
    print(f"   {'✅' if ok else '❌'} Mapa creado\n")
    return MAP_ID


# ─────────────────────────────────────────────────────────────
# 4. DASHBOARD
# ─────────────────────────────────────────────────────────────

DASHBOARD_ID = "fleet-main-dashboard"

def create_dashboard():
    print("📺 Creando dashboard...")

    panels = [
        # Fila 1: métricas resumen
        {"panelIndex": "1", "gridData": {"x": 0,  "y": 0,  "w": 8,  "h": 6,  "i": "1"},
         "type": "visualization", "id": "fleet-metric-active",
         "title": "Vehículos Activos"},
        {"panelIndex": "2", "gridData": {"x": 8,  "y": 0,  "w": 8,  "h": 6,  "i": "2"},
         "type": "visualization", "id": "fleet-metric-alerts",
         "title": "Alertas Activas"},

        # Fila 1: mapa (ocupa el resto)
        {"panelIndex": "3", "gridData": {"x": 16, "y": 0,  "w": 32, "h": 20, "i": "3"},
         "type": "map", "id": MAP_ID,
         "title": "Posición de la Flota"},

        # Fila 2: velocidad y temperatura
        {"panelIndex": "4", "gridData": {"x": 0,  "y": 6,  "w": 24, "h": 14, "i": "4"},
         "type": "visualization", "id": "fleet-timeseries-speed",
         "title": "Velocidad por Vehículo"},
        {"panelIndex": "5", "gridData": {"x": 0,  "y": 20, "w": 16, "h": 12, "i": "5"},
         "type": "visualization", "id": "fleet-gauge-temp",
         "title": "Temperatura del Motor"},

        # Fila 3: combustible y tabla
        {"panelIndex": "6", "gridData": {"x": 16, "y": 20, "w": 32, "h": 12, "i": "6"},
         "type": "visualization", "id": "fleet-bar-fuel",
         "title": "Combustible por Vehículo"},
        {"panelIndex": "7", "gridData": {"x": 0,  "y": 32, "w": 48, "h": 12, "i": "7"},
         "type": "visualization", "id": "fleet-table-status",
         "title": "Estado de la Flota"},
    ]

    references = [
        {"name": "1:panel_1", "type": "visualization", "id": "fleet-metric-active"},
        {"name": "2:panel_2", "type": "visualization", "id": "fleet-metric-alerts"},
        {"name": "3:panel_3", "type": "map",            "id": MAP_ID},
        {"name": "4:panel_4", "type": "visualization", "id": "fleet-timeseries-speed"},
        {"name": "5:panel_5", "type": "visualization", "id": "fleet-gauge-temp"},
        {"name": "6:panel_6", "type": "visualization", "id": "fleet-bar-fuel"},
        {"name": "7:panel_7", "type": "visualization", "id": "fleet-table-status"},
    ]

    body = {
        "attributes": {
            "title":       "Fleet IoT - Dashboard Principal",
            "description": "Monitorización en tiempo real de la flota de vehículos industriales",
            "panelsJSON":  json.dumps(panels),
            "optionsJSON": json.dumps({
                "useMargins": True,
                "syncColors": False,
                "hidePanelTitles": False
            }),
            "timeRestore": True,
            "timeTo":      "now",
            "timeFrom":    "now-15m",
            "refreshInterval": {"pause": False, "value": 5000},
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"language": "kuery", "query": ""},
                    "filter": []
                })
            }
        },
        "references": references
    }

    r = kibana_upsert(f"/api/saved_objects/dashboard/{DASHBOARD_ID}", body)
    ok = r.status_code in (200, 201)
    print(f"   {'✅' if ok else '❌'} Dashboard creado\n")
    return DASHBOARD_ID


# ─────────────────────────────────────────────────────────────
# 5. ALERTAS
# ─────────────────────────────────────────────────────────────

def create_alert(alert_id, name, condition_query, threshold, threshold_comparator,
                 field, message):
    # En Kibana 8.x, .es-query con searchType="esQuery" evalúa cuántos docs
    # cumplen la query en la ventana de tiempo. El threshold se compara con ese count.
    # La esQuery debe ser solo el objeto de query de ES (sin wrapper).
    comparator_es = "gt" if threshold_comparator == ">" else "lt"
    body = {
        "name":         name,
        "rule_type_id": ".es-query",
        "consumer":     "stackAlerts",
        "schedule":     {"interval": "30s"},
        "actions":      [],
        "params": {
            "size":                100,
            "timeField":           "@timestamp",
            "searchType":          "esQuery",
            "timeWindowSize":      1,
            "timeWindowUnit":      "m",
            "threshold":           [0],
            "thresholdComparator": ">",
            "aggType":             "count",
            "groupBy":             "all",
            "index":               ["fleet-vehicles-*"],
            "esQuery": json.dumps({
                "query": {
                    "bool": {
                        "filter": [
                            {"range": {field: {comparator_es: threshold}}}
                        ]
                    }
                }
            }),
        },
        "notify_when": "onActiveAlert",
    }

    r = requests.post(
        f"{KIBANA_URL}/api/alerting/rule",
        headers=HEADERS, auth=AUTH, json=body, timeout=30
    )
    ok = r.status_code in (200, 201)
    if not ok:
        print(f"     Error detalle: {r.text[:300]}")
    print(f"   {'✅' if ok else '❌'} {name}")
    return ok


def create_all_alerts():
    print("🚨 Creando alertas...")
    create_alert(
        "fleet-alert-speed", "⚡ Velocidad excesiva (>120 km/h)",
        None, 120, ">", "speed_kmh",
        "Vehículo superando 120 km/h"
    )
    create_alert(
        "fleet-alert-temp", "🌡️ Motor recalentado (>100°C)",
        None, 100, ">", "engine_temp_c",
        "Temperatura del motor crítica"
    )
    create_alert(
        "fleet-alert-fuel", "⛽ Combustible crítico (<10%)",
        None, 10, "<", "fuel_level_pct",
        "Nivel de combustible muy bajo"
    )
    print()


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  Fleet IoT — Setup automático de Kibana")
    print("=" * 55)
    print()

    wait_for_kibana()

    create_index_pattern()
    create_all_visualizations()
    create_map()
    create_dashboard()
    create_all_alerts()

    print("=" * 55)
    print("  ✅ Setup completado!")
    print(f"  🌐 Abre: http://localhost:{os.getenv('KIBANA_PORT', 5601)}")
    print(f"  📺 Dashboard: Analytics → Dashboards → Fleet IoT")
    print(f"  🗺️  Mapa:      Analytics → Maps → Mapa - Posición")
    print(f"  🚨 Alertas:   Stack Management → Rules")
    print("=" * 55)


if __name__ == "__main__":
    main()
