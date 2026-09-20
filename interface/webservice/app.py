"""
Servicio Web — parte de la entrega de Oriana en el proyecto Telemática.

Consulta al servidor central real (server/, en C) por TCP usando el
protocolo de operador (LIST_NODES, GET_MEASUREMENTS, GET_ALERTS,
GET_SYSTEM_STATUS) y muestra el resultado en un dashboard: estado del
servidor, cantidad de nodos, nodos activos, últimas mediciones y
alertas recientes.

Uso:
    python app.py

Variables de entorno (mismo patrón que simulators/main.py):
    SERVER_HOST, SERVER_PORT   -> dónde está el servidor (default localhost:5000)
    WEB_PORT                   -> puerto del dashboard (default 8080)
"""

import os

from flask import Flask, jsonify, render_template

import tcp_client

SERVER_HOST = os.getenv("SERVER_HOST", "localhost")
SERVER_PORT = int(os.getenv("SERVER_PORT", "5000"))
WEB_PORT = int(os.getenv("WEB_PORT", "8080"))

COMMANDS = ["LIST_NODES", "GET_MEASUREMENTS", "GET_ALERTS", "GET_SYSTEM_STATUS"]

app = Flask(__name__)


def fetch_snapshot():
    try:
        responses = tcp_client.query(SERVER_HOST, SERVER_PORT, COMMANDS)
    except tcp_client.ServerUnavailable as exc:
        return {
            "server_status": "offline",
            "error": str(exc),
            "nodes_registered": 0,
            "nodes_active": 0,
            "uptime_seconds": 0,
            "nodes": {},
            "recent_alerts": [],
            "counters": {"alerts_total": 0, "data_received": 0, "data_lost": 0},
        }

    nodes_status = tcp_client.parse_nodes_resp(responses[0])
    measurements = tcp_client.parse_measurements_resp(responses[1])
    alerts = tcp_client.parse_alerts_resp(responses[2])
    system = tcp_client.parse_system_status_resp(responses[3])

    nodes = {}
    for node_id, active in nodes_status.items():
        info = measurements.get(node_id, {})
        nodes[node_id] = {
            "active": active,
            "timestamp": info.get("timestamp"),
            "readings": info.get("readings", {}),
        }

    return {
        "server_status": "online",
        "uptime_seconds": system.get("UPTIME", 0),
        "nodes_registered": system.get("NODES_REGISTERED", len(nodes_status)),
        "nodes_active": system.get("NODES_ACTIVE", sum(nodes_status.values())),
        "nodes": nodes,
        "recent_alerts": alerts,
        "counters": {
            "alerts_total": system.get("ALERTS", len(alerts)),
            "data_received": system.get("DATA_RECEIVED", 0),
            "data_lost": system.get("DATA_LOST", 0),
        },
    }


@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/status")
def api_status():
    return jsonify(fetch_snapshot())


if __name__ == "__main__":
    print(f"[webservice] Consultando servidor en {SERVER_HOST}:{SERVER_PORT}")
    print(f"[webservice] Dashboard en http://0.0.0.0:{WEB_PORT}")
    app.run(host="0.0.0.0", port=WEB_PORT, debug=False)
