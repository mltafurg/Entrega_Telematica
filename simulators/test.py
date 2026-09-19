import socket
import time


IP = "0.0.0.0"
PORT = 5000

KNOWN_NODES = {
    "NODE01",
    "NODE02",
    "NODE03",
    "NODE04",
    "NODE05",
}

VARIABLE_RANGES = {
    "TEMP": (-50.0, 80.0),
    "HUMD": (0.0, 100.0),
    "ELEC": (0.0, float("inf")),
}

last_sequence = {}
data_received = 0
data_lost = 0
alerts_received = 0
errors_sent = 0


def send_error(sock, addr, code, description):
    global errors_sent

    message = f"ERROR|{code}|{description}\n"
    try:
        sock.sendto(message.encode("utf-8"), addr)
        errors_sent += 1
        print(f"   ↳ ERROR enviado: {message.strip()}")
    except OSError as error:
        print(f"   ↳ No se pudo enviar ERROR: {error}")


def validate_epoch(value):
    try:
        timestamp = int(value)
        return timestamp > 0
    except (ValueError, TypeError):
        return False


def validate_number(value):
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False


def validate_data(parts):
    if len(parts) != 6:
        return "ERR_001", "Estructura de campos incompleta o invalida"

    _, node_id, sequence, variable, value, timestamp = parts

    if node_id not in KNOWN_NODES:
        return "ERR_002", "El ID_NODO no se encuentra registrado"

    try:
        sequence_number = int(sequence)
        if sequence_number <= 0:
            raise ValueError
    except ValueError:
        return "ERR_005", "La secuencia debe ser un entero positivo"

    if variable not in VARIABLE_RANGES:
        return "ERR_003", "La variable enviada no pertenece al catalogo"

    if not validate_number(value):
        return "ERR_004", "El valor numerico no es valido"

    numeric_value = float(value)
    min_value, max_value = VARIABLE_RANGES[variable]
    if numeric_value < min_value or numeric_value > max_value:
        return "ERR_004", "El valor numerico esta fuera de rango"

    if not validate_epoch(timestamp):
        return "ERR_006", "El timestamp no tiene formato Epoch valido"

    return None


def validate_alert(parts):
    if len(parts) != 5:
        return "ERR_001", "Estructura de campos incompleta o invalida"

    _, node_id, alert_type, value, timestamp = parts

    if node_id not in KNOWN_NODES:
        return "ERR_002", "El ID_NODO no se encuentra registrado"

    if not alert_type:
        return "ERR_001", "TIPO_ALERTA no puede estar vacio"

    if not validate_number(value):
        return "ERR_004", "El valor numerico no es valido"

    if not validate_epoch(timestamp):
        return "ERR_006", "El timestamp no tiene formato Epoch valido"

    return None


def process_data(sock, addr, parts):
    global data_received, data_lost

    error = validate_data(parts)
    if error:
        send_error(sock, addr, error[0], error[1])
        return

    _, node_id, sequence, variable, value, timestamp = parts
    sequence_number = int(sequence)

    previous = last_sequence.get(node_id)

    if previous is not None and sequence_number > previous + 1:
        missing = sequence_number - previous - 1
        data_lost += missing
        print(
            f"    Pérdida detectada en {node_id}: "
            f"faltaron {missing} mensaje(s) entre {previous} y {sequence_number}"
        )

    if previous is None or sequence_number > previous:
        last_sequence[node_id] = sequence_number

    data_received += 1

    print(
        f"   DATA válida | nodo={node_id} | seq={sequence_number} | "
        f"{variable}={value} | timestamp={timestamp}"
    )


def process_alert(sock, addr, parts):
    global alerts_received

    error = validate_alert(parts)
    if error:
        send_error(sock, addr, error[0], error[1])
        return

    _, node_id, alert_type, value, timestamp = parts
    alerts_received += 1

    print(
        f"    ALERT válida | nodo={node_id} | "
        f"tipo={alert_type} | valor={value} | timestamp={timestamp}"
    )


def process_message(sock, data, addr):
    try:
        message = data.decode("utf-8")
    except UnicodeDecodeError:
        send_error(sock, addr, "ERR_001", "El mensaje no usa UTF-8 valido")
        return

    # El protocolo exige que cada trama termine en \n.
    if not message.endswith("\n"):
        send_error(sock, addr, "ERR_001", "La trama debe terminar con salto de linea")
        return

    payload = message[:-1]
    if payload.endswith("\r"):
        payload = payload[:-1]

    parts = payload.split("|")

    if not parts or not parts[0]:
        send_error(sock, addr, "ERR_001", "Tipo de mensaje inexistente")
        return

    message_type = parts[0]

    if message_type == "DATA":
        process_data(sock, addr, parts)
    elif message_type == "ALERT":
        process_alert(sock, addr, parts)
    else:
        # En este receptor de prueba nos enfocamos en la parte UDP.
        # GET_STATUS y STATUS_RESP pertenecen al flujo TCP del operador.
        send_error(sock, addr, "ERR_001", "Tipo de mensaje no soportado por este receptor UDP")


def print_summary():
    estimated_transmitted = data_received + data_lost

    print("\n========== RESUMEN DE PRUEBA UDP ==========")
    print(f"DATA recibidos:              {data_received}")
    print(f"DATA perdidos detectados:    {data_lost}")
    print(f"DATA transmitidos estimados: {estimated_transmitted}")
    print(f"ALERT recibidas:              {alerts_received}")
    print(f"Errores enviados:             {errors_sent}")
    print("============================================")


if __name__ == "__main__":
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((IP, PORT))

    print(f"Receptor UDP escuchando en {IP}:{PORT}")
    print("Esperando tramas de los nodos... (Ctrl+C para salir)\n")

    try:
        while True:
            data, addr = sock.recvfrom(4096)
            print(f"[RECIBIDO desde {addr}]")
            process_message(sock, data, addr)

    except KeyboardInterrupt:
        print_summary()
        print("Cerrando receptor de prueba...")
    finally:
        sock.close()