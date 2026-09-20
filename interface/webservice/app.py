"""
Servicio Web — parte de la entrega de Oriana en el proyecto Telemática.

Muestra: estado del servidor, cantidad de nodos, nodos activos,
últimas mediciones y alertas recientes. Escucha directamente el canal
UDP que ya usan los simuladores (simulators/main.py) sobre el mismo
protocolo definido en el README del proyecto, así que funciona ya
mismo sin esperar al servidor en C.

Uso:
    python app.py
    (por defecto escucha UDP en 0.0.0.0:5000 y sirve el web en :8080)

Variables de entorno opcionales:
    UDP_HOST, UDP_PORT   -> dónde escuchar los nodos (default 0.0.0.0:5000)
    WEB_PORT             -> puerto del dashboard (default 8080)
"""

import os

from flask import Flask, jsonify, render_template

from udp_receiver import ServiceState, start_udp_listener

UDP_HOST = os.getenv("UDP_HOST", "0.0.0.0")
UDP_PORT = int(os.getenv("UDP_PORT", "5000"))
WEB_PORT = int(os.getenv("WEB_PORT", "8080"))

app = Flask(__name__)
state = ServiceState()


@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/status")
def api_status():
    return jsonify(state.snapshot())


if __name__ == "__main__":
    start_udp_listener(state, host=UDP_HOST, port=UDP_PORT)
    print(f"[webservice] Dashboard en http://0.0.0.0:{WEB_PORT}")
    app.run(host="0.0.0.0", port=WEB_PORT, debug=False)
