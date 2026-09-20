"""
Cliente operador (consola) — parte de la entrega de Oriana.

Menú interactivo que consulta al servidor central (server/, en C) por
TCP: nodos activos, últimas mediciones, un nodo específico, alertas
recientes y estado general de la red. No tiene dependencias externas,
solo la librería estándar de Python.

Uso:
    python operator_client.py

Variables de entorno (mismo patrón que simulators/main.py):
    SERVER_HOST, SERVER_PORT   -> dónde está el servidor (default localhost:5000)
"""

import os
import sys
from datetime import datetime

import tcp_client

SERVER_HOST = os.getenv("SERVER_HOST", "localhost")
SERVER_PORT = int(os.getenv("SERVER_PORT", "5000"))

MENU = """
==============================
  Cliente operador — Telemetria
  Servidor: {host}:{port}
==============================
  1. Nodos activos
  2. Ultimas mediciones
  3. Consultar un nodo especifico
  4. Alertas recientes
  5. Estado general del sistema
  0. Salir
==============================
"""


def fmt_time(ts):
    if ts is None:
        return "—"
    return datetime.fromtimestamp(ts).strftime("%H:%M:%S")


def fmt_readings(readings):
    if not readings:
        return "sin lecturas"
    return "  ".join(f"{var}={val}" for var, val in readings.items())


def print_table(headers, rows):
    if not rows:
        print("  (sin datos)")
        return
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))

    def print_row(cells):
        print("  " + "  ".join(str(c).ljust(widths[i]) for i, c in enumerate(cells)))

    print_row(headers)
    print_row(["-" * w for w in widths])
    for row in rows:
        print_row(row)


def run_command(*commands):
    """Manda uno o mas comandos en una sola conexion y devuelve las respuestas,
    o None (ya habiendo avisado al usuario) si el servidor no responde."""
    try:
        return tcp_client.query(SERVER_HOST, SERVER_PORT, commands)
    except tcp_client.ServerUnavailable as exc:
        print(f"\n  [!] No se pudo conectar al servidor ({SERVER_HOST}:{SERVER_PORT}): {exc}")
        print("      Verifica que este corriendo y que SERVER_HOST/SERVER_PORT sean correctos.\n")
        return None


def accion_nodos_activos():
    responses = run_command("LIST_NODES")
    if not responses:
        return
    nodes = tcp_client.parse_nodes_resp(responses[0])
    if not nodes:
        print("\n  El servidor no tiene nodos registrados.\n")
        return
    rows = [[node_id, "ONLINE" if activo else "OFFLINE"] for node_id, activo in nodes.items()]
    print()
    print_table(["Nodo", "Estado"], rows)
    activos = sum(1 for activo in nodes.values() if activo)
    print(f"\n  {activos}/{len(nodes)} nodos activos\n")


def accion_ultimas_mediciones():
    responses = run_command("GET_MEASUREMENTS")
    if not responses:
        return
    mediciones = tcp_client.parse_measurements_resp(responses[0])
    if not mediciones:
        print("\n  Todavia no hay mediciones registradas.\n")
        return
    rows = [
        [node_id, fmt_time(info["timestamp"]), fmt_readings(info["readings"])]
        for node_id, info in mediciones.items()
    ]
    print()
    print_table(["Nodo", "Ultima lectura", "Valores"], rows)
    print()


def accion_consultar_nodo():
    node_id = input("  ID del nodo (ej. NODE01): ").strip()
    if not node_id:
        print("  Tenes que escribir un ID de nodo.\n")
        return
    responses = run_command(f"GET_STATUS|{node_id}")
    if not responses:
        return
    line = responses[0]
    if tcp_client.is_error(line):
        error = tcp_client.parse_error(line)
        print(f"\n  [{error['code']}] {error['description']}\n")
        return
    status = tcp_client.parse_status_resp(line)
    print()
    print_table(
        ["Nodo", "Estado", "Ultima lectura", "Valores"],
        [[status["node_id"], status["status"], fmt_time(status["timestamp"]), fmt_readings(status["readings"])]],
    )
    print()


def accion_alertas():
    responses = run_command("GET_ALERTS")
    if not responses:
        return
    alertas = tcp_client.parse_alerts_resp(responses[0])
    if not alertas:
        print("\n  Sin alertas registradas.\n")
        return
    rows = [[a["node_id"], a["code"], a["value"], fmt_time(a["timestamp"])] for a in alertas]
    print()
    print_table(["Nodo", "Tipo", "Valor", "Hora"], rows)
    print()


def accion_estado_general():
    responses = run_command("GET_SYSTEM_STATUS")
    if not responses:
        return
    estado = tcp_client.parse_system_status_resp(responses[0])
    if not estado:
        print("\n  Respuesta inesperada del servidor.\n")
        return
    print()
    print_table(
        ["Metrica", "Valor"],
        [
            ["Uptime (s)", estado.get("UPTIME", "—")],
            ["Nodos registrados", estado.get("NODES_REGISTERED", "—")],
            ["Nodos activos", estado.get("NODES_ACTIVE", "—")],
            ["Alertas totales", estado.get("ALERTS", "—")],
            ["Datos recibidos", estado.get("DATA_RECEIVED", "—")],
            ["Datos perdidos", estado.get("DATA_LOST", "—")],
        ],
    )
    print()


ACCIONES = {
    "1": accion_nodos_activos,
    "2": accion_ultimas_mediciones,
    "3": accion_consultar_nodo,
    "4": accion_alertas,
    "5": accion_estado_general,
}


def main():
    while True:
        print(MENU.format(host=SERVER_HOST, port=SERVER_PORT))
        try:
            opcion = input("  Elegi una opcion: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Saliendo...")
            break

        if opcion == "0":
            print("  Saliendo...")
            break

        accion = ACCIONES.get(opcion)
        if accion is None:
            print("  Opcion invalida.\n")
            continue
        accion()


if __name__ == "__main__":
    sys.exit(main())
