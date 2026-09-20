"""
Receptor UDP para el Servicio Web.

Escucha en el mismo puerto al que ya apuntan los simuladores de nodos
(simulators/main.py) y mantiene en memoria el estado necesario para el
dashboard: nodos conocidos, última medición de cada uno, y alertas
recientes. No depende del servidor en C ni del protocolo TCP del
operador (GET_STATUS/STATUS_RESP) — solo habla el protocolo UDP que ya
está definido en el README del proyecto (tramas DATA / ALERT).

La validación de tramas replica la que ya se usó en
simulators/test.py, así el comportamiento (qué se acepta, qué ERROR
se responde) es consistente con lo que el equipo ya probó.
"""

import socket
import threading
import time


KNOWN_NODES = {"NODE01", "NODE02", "NODE03", "NODE04", "NODE05"}

VARIABLE_RANGES = {
    "TEMP": (-50.0, 80.0),
    "HUMD": (0.0, 100.0),
    "ELEC": (0.0, float("inf")),
}

# Un nodo se considera "activo" si mandó algo en los últimos N segundos.
# Los nodos mandan cada 2-4s, así que 15s da margen sin marcar como
# caído a un nodo que solo tuvo un mensaje perdido.
ACTIVE_WINDOW_SECONDS = 15

# Cuántas alertas recientes se guardan para mostrar en el dashboard.
MAX_RECENT_ALERTS = 25


def _validate_number(value):
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False


def _validate_epoch(value):
    try:
        return int(value) > 0
    except (ValueError, TypeError):
        return False


def _validate_data(parts):
    if len(parts) != 6:
        return "ERR_001", "Estructura de campos incompleta o invalida"

    _, node_id, sequence, variable, value, timestamp = parts

    if node_id not in KNOWN_NODES:
        return "ERR_002", "El ID_NODO no se encuentra registrado"

    try:
        if int(sequence) <= 0:
            raise ValueError
    except ValueError:
        return "ERR_005", "La secuencia debe ser un entero positivo"

    if variable not in VARIABLE_RANGES:
        return "ERR_003", "La variable enviada no pertenece al catalogo"

    if not _validate_number(value):
        return "ERR_004", "El valor numerico no es valido"

    min_value, max_value = VARIABLE_RANGES[variable]
    if not (min_value <= float(value) <= max_value):
        return "ERR_004", "El valor numerico esta fuera de rango"

    if not _validate_epoch(timestamp):
        return "ERR_006", "El timestamp no tiene formato Epoch valido"

    return None


def _validate_alert(parts):
    if len(parts) != 5:
        return "ERR_001", "Estructura de campos incompleta o invalida"

    _, node_id, alert_type, value, timestamp = parts

    if node_id not in KNOWN_NODES:
        return "ERR_002", "El ID_NODO no se encuentra registrado"

    if not alert_type:
        return "ERR_001", "TIPO_ALERTA no puede estar vacio"

    if not _validate_number(value):
        return "ERR_004", "El valor numerico no es valido"

    if not _validate_epoch(timestamp):
        return "ERR_006", "El timestamp no tiene formato Epoch valido"

    return None


class ServiceState:
    """Estado compartido entre el hilo UDP y las rutas Flask."""

    def __init__(self):
        self._lock = threading.Lock()
        self.started_at = time.time()
        self.nodes = {}  # node_id -> {last_seen, readings: {var: {value, timestamp}}}
        self.recent_alerts = []  # lista de dicts, más reciente primero
        self.data_received = 0
        self.alerts_received = 0
        self.errors_sent = 0

    def register_data(self, node_id, variable, value, timestamp):
        with self._lock:
            node = self.nodes.setdefault(
                node_id, {"last_seen": 0.0, "readings": {}}
            )
            node["last_seen"] = time.time()
            node["readings"][variable] = {
                "value": float(value),
                "timestamp": int(timestamp),
            }
            self.data_received += 1

    def register_alert(self, node_id, alert_type, value, timestamp):
        with self._lock:
            node = self.nodes.setdefault(
                node_id, {"last_seen": 0.0, "readings": {}}
            )
            node["last_seen"] = time.time()
            self.recent_alerts.insert(
                0,
                {
                    "node_id": node_id,
                    "alert_type": alert_type,
                    "value": float(value),
                    "timestamp": int(timestamp),
                },
            )
            self.recent_alerts = self.recent_alerts[:MAX_RECENT_ALERTS]
            self.alerts_received += 1

    def register_error(self):
        with self._lock:
            self.errors_sent += 1

    def snapshot(self):
        """Copia serializable del estado, ya con nodos activos calculados."""
        now = time.time()
        with self._lock:
            nodes_out = {}
            active_count = 0
            for node_id, info in self.nodes.items():
                is_active = (now - info["last_seen"]) <= ACTIVE_WINDOW_SECONDS
                if is_active:
                    active_count += 1
                nodes_out[node_id] = {
                    "active": is_active,
                    "seconds_since_last_seen": round(now - info["last_seen"], 1),
                    "readings": info["readings"],
                }
            return {
                "server_status": "online",
                "uptime_seconds": round(now - self.started_at, 1),
                "known_nodes": len(KNOWN_NODES),
                "nodes_seen": len(self.nodes),
                "active_nodes": active_count,
                "nodes": nodes_out,
                "recent_alerts": list(self.recent_alerts),
                "counters": {
                    "data_received": self.data_received,
                    "alerts_received": self.alerts_received,
                    "errors_sent": self.errors_sent,
                },
            }


def _send_error(sock, addr, code, description, state):
    message = f"ERROR|{code}|{description}\n"
    try:
        sock.sendto(message.encode("utf-8"), addr)
        state.register_error()
    except OSError:
        pass


def _process_message(sock, data, addr, state):
    try:
        message = data.decode("utf-8")
    except UnicodeDecodeError:
        _send_error(sock, addr, "ERR_001", "El mensaje no usa UTF-8 valido", state)
        return

    if not message.endswith("\n"):
        _send_error(
            sock, addr, "ERR_001", "La trama debe terminar con salto de linea", state
        )
        return

    payload = message[:-1]
    if payload.endswith("\r"):
        payload = payload[:-1]

    parts = payload.split("|")
    if not parts or not parts[0]:
        _send_error(sock, addr, "ERR_001", "Tipo de mensaje inexistente", state)
        return

    message_type = parts[0]

    if message_type == "DATA":
        error = _validate_data(parts)
        if error:
            _send_error(sock, addr, error[0], error[1], state)
            return
        _, node_id, _sequence, variable, value, timestamp = parts
        state.register_data(node_id, variable, value, timestamp)

    elif message_type == "ALERT":
        error = _validate_alert(parts)
        if error:
            _send_error(sock, addr, error[0], error[1], state)
            return
        _, node_id, alert_type, value, timestamp = parts
        state.register_alert(node_id, alert_type, value, timestamp)

    else:
        # GET_STATUS/STATUS_RESP son del flujo TCP del operador,
        # este receptor solo atiende el canal UDP de los nodos.
        _send_error(
            sock, addr, "ERR_001", "Tipo de mensaje no soportado en este canal", state
        )


def start_udp_listener(state, host="0.0.0.0", port=5000):
    """Arranca el hilo que escucha UDP. No bloquea."""

    def _loop():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        print(f"[webservice] Escuchando UDP en {host}:{port}")
        while True:
            data, addr = sock.recvfrom(4096)
            _process_message(sock, data, addr, state)

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()
    return thread
