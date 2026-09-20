"""
Cliente TCP del protocolo de operador, contra el servidor central real
(server/ en C). Implementa los 5 comandos que expone el servidor:
LIST_NODES, GET_STATUS, GET_MEASUREMENTS, GET_ALERTS, GET_SYSTEM_STATUS.

Cada comando y cada respuesta terminan en '\n', tal como exige el
protocolo. El servidor acepta varios comandos por conexión (un hilo
por operador que queda escuchando hasta que el cliente cierra), así
que para el dashboard se manda una tanda de comandos por conexión en
vez de abrir una conexión nueva por cada uno.
"""

import socket


class ServerUnavailable(Exception):
    """El servidor no respondió, se cayó o no se pudo conectar."""


def query(host, port, commands, timeout=3.0):
    """Abre una conexión, manda cada comando en `commands` y devuelve
    la lista de líneas de respuesta, en el mismo orden."""
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
    except OSError as exc:
        raise ServerUnavailable(str(exc)) from exc

    sock.settimeout(timeout)
    responses = []
    try:
        payload = "".join(cmd + "\n" for cmd in commands).encode("utf-8")
        sock.sendall(payload)

        buffer = b""
        while len(responses) < len(commands):
            chunk = sock.recv(4096)
            if not chunk:
                break
            buffer += chunk
            while b"\n" in buffer and len(responses) < len(commands):
                line, buffer = buffer.split(b"\n", 1)
                responses.append(line.decode("utf-8", errors="replace"))
    except OSError as exc:
        raise ServerUnavailable(str(exc)) from exc
    finally:
        sock.close()

    if len(responses) < len(commands):
        raise ServerUnavailable("El servidor cerro la conexion antes de responder todo")

    return responses


# ---------- Parsing de cada tipo de respuesta ----------

def is_error(line):
    return line.startswith("ERROR|")


def parse_error(line):
    """ERROR|CODIGO|DESCRIPCION -> {code, description}"""
    parts = line.split("|", 2)
    if len(parts) >= 3 and parts[0] == "ERROR":
        return {"code": parts[1], "description": parts[2]}
    return {"code": "ERR_DESCONOCIDO", "description": line}


def parse_status_resp(line):
    """STATUS_RESP|ID|ESTADO|TS|VAR:VAL|... -> {node_id, status, timestamp, readings}"""
    parts = line.split("|")
    if len(parts) < 4 or parts[0] != "STATUS_RESP":
        return None
    node_id, estado, timestamp_txt = parts[1], parts[2], parts[3]
    readings = {}
    for field in parts[4:]:
        if ":" not in field:
            continue
        variable, value = field.split(":", 1)
        try:
            readings[variable] = float(value)
        except ValueError:
            pass
    timestamp = int(timestamp_txt) if timestamp_txt.lstrip("-").isdigit() else None
    return {"node_id": node_id, "status": estado, "timestamp": timestamp, "readings": readings}


def parse_nodes_resp(line):
    """NODES_RESP|<total>|NODE01:ONLINE,NODE02:OFFLINE,... -> {id: bool}"""
    parts = line.split("|")
    if len(parts) < 3 or parts[0] != "NODES_RESP":
        return {}
    nodes = {}
    body = parts[2]
    if body:
        for item in body.split(","):
            if ":" not in item:
                continue
            node_id, status = item.split(":", 1)
            nodes[node_id] = status == "ONLINE"
    return nodes


def parse_measurements_resp(line):
    """MEASUREMENTS_RESP|<n>|ID,TS,VAR:VAL,...;ID,... -> {id: {timestamp, readings}}"""
    parts = line.split("|")
    if len(parts) < 3 or parts[0] != "MEASUREMENTS_RESP":
        return {}
    result = {}
    body = parts[2]
    if body:
        for entry in body.split(";"):
            fields = entry.split(",")
            if not fields or not fields[0]:
                continue
            node_id = fields[0]
            timestamp = int(fields[1]) if len(fields) > 1 and fields[1].lstrip("-").isdigit() else None
            readings = {}
            for field in fields[2:]:
                if ":" not in field:
                    continue
                variable, value = field.split(":", 1)
                try:
                    readings[variable] = float(value)
                except ValueError:
                    pass
            result[node_id] = {"timestamp": timestamp, "readings": readings}
    return result


def parse_alerts_resp(line):
    """ALERTS_RESP|<n>|ID,CODIGO,VALOR,TS;... -> [{node_id, code, value, timestamp}]"""
    parts = line.split("|")
    if len(parts) < 3 or parts[0] != "ALERTS_RESP":
        return []
    alerts = []
    body = parts[2]
    if body:
        for entry in body.split(";"):
            fields = entry.split(",")
            if len(fields) != 4:
                continue
            node_id, code, value, timestamp = fields
            try:
                alerts.append({
                    "node_id": node_id,
                    "code": code,
                    "value": float(value),
                    "timestamp": int(timestamp),
                })
            except ValueError:
                continue
    return alerts


def parse_system_status_resp(line):
    """SYSTEM_STATUS_RESP|UPTIME=s|NODES_REGISTERED=n|... -> {clave: int}"""
    parts = line.split("|")
    if not parts or parts[0] != "SYSTEM_STATUS_RESP":
        return {}
    result = {}
    for field in parts[1:]:
        if "=" not in field:
            continue
        key, value = field.split("=", 1)
        try:
            result[key] = int(value)
        except ValueError:
            result[key] = value
    return result
