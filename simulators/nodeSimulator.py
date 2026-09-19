import random
import socket
import time


# Variables definidas por el protocolo de la aplicación.
VARIABLES = {"TEMP", "HUMD", "ELEC"}

# Rangos básicos de validación usados por el simulador/servidor de prueba.
RANGES = {
    "TEMP": (-50.0, 80.0),
    "HUMD": (0.0, 100.0),
    "ELEC": (0.0, float("inf")),
}

# Umbral de ejemplo para demostrar ALERT.
# La generación normal está entre 20 y 35 °C, y ocasionalmente
# se genera una temperatura alta para poder probar la alerta.
TEMP_ALERT_THRESHOLD = 40.0

MAX_RETRIES_ERR_002 = 3


class NodeClient:
    def __init__(
        self,
        node_id,
        server_host,
        server_port,
        simulated_loss_probability=0.0,
    ):
        self.node_id = node_id
        self.server_host = server_host
        self.server_port = server_port
        self.sequence_counter = 1
        self.simulated_loss_probability = max(
            0.0, min(1.0, simulated_loss_probability)
        )

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(0.5)

    def resolve_dns(self):
        """Resuelve el nombre del servidor sin usar una IP pública fija."""
        try:
            ip_address = socket.gethostbyname(self.server_host)
            return ip_address, self.server_port
        except socket.gaierror as error:
            print(
                f"[{self.node_id}] Error resolviendo DNS "
                f"'{self.server_host}': {error}"
            )
            return None

    def generate_sensor_data(self):
        """Genera una de las tres variables del proyecto."""
        data_readings = {
            "TEMP": round(random.uniform(20.0, 35.0), 1),
            "HUMD": round(random.uniform(30.0, 80.0), 1),
            "ELEC": round(random.uniform(90.0, 250.0), 1),
        }

        variable = random.choice(list(data_readings.keys()))
        value = data_readings[variable]

        # Solo para pruebas: ocasionalmente genera una temperatura crítica.
        if variable == "TEMP" and random.random() < 0.10:
            value = round(random.uniform(40.0, 45.0), 1)

        return variable, value

    def _parse_error(self, response):
        """Devuelve (codigo, descripcion) si la respuesta es ERROR."""
        if not response.startswith("ERROR|"):
            return None

        parts = response.split("|", 2)
        if len(parts) != 3:
            return "ERR_001", "Respuesta de error mal formada"

        return parts[1], parts[2]

    def _wait_for_server_error(self):
        """
        Escucha brevemente por una respuesta ERROR.
        En UDP una respuesta no es obligatoria para una trama correcta.
        """
        try:
            data, _ = self.sock.recvfrom(1024)
            response = data.decode("utf-8", errors="replace").rstrip("\n")
            return self._parse_error(response)
        except socket.timeout:
            return None
        except (OSError, UnicodeError) as error:
            print(f"[{self.node_id}] Error recibiendo respuesta: {error}")
            return None

    def _send_once(self, message, server_address):
        """Envía una única trama UDP o simula su pérdida para una prueba."""
        if self.simulated_loss_probability > 0:
            if random.random() < self.simulated_loss_probability:
                print(
                    f"[{self.node_id}] Pérdida UDP SIMULADA: "
                    f"{message.strip()}"
                )
                return "simulated_loss"

        try:
            self.sock.sendto(message.encode("utf-8"), server_address)
            print(f"[{self.node_id}] UDP -> {message.strip()}")
            return "sent"
        except OSError as error:
            print(f"[{self.node_id}] Error de comunicación UDP: {error}")
            return "send_error"

    def send_message(self, message, server_address):
        """
        Implementa la política definida en el protocolo:
        ERR_002 -> reintentar hasta 3 veces.
        ERR_001/003/005/006 -> no reintentar.
        ERR_004 -> no reintentar.
        """
        attempts = 0

        while attempts < MAX_RETRIES_ERR_002:
            attempts += 1
            result = self._send_once(message, server_address)

            # Si se simuló pérdida o el sendto falló, no existe respuesta.
            if result in ("simulated_loss", "send_error"):
                return result

            error = self._wait_for_server_error()

            if error is None:
                return "sent"

            code, description = error
            print(
                f"[{self.node_id}] ERROR del servidor: "
                f"{code} - {description}"
            )

            if code == "ERR_002" and attempts < MAX_RETRIES_ERR_002:
                print(
                    f"[{self.node_id}] Reintentando ({attempts}/"
                    f"{MAX_RETRIES_ERR_002})..."
                )
                continue

            # Para ERR_001, ERR_003, ERR_004, ERR_005 y ERR_006
            # no se reintenta.
            return "server_error"

        return "server_error"

    def build_data_message(self, variable, value, timestamp):
        """Construye la trama DATA de exactamente 6 campos."""
        return (
            f"DATA|{self.node_id}|{self.sequence_counter}|"
            f"{variable}|{value}|{timestamp}\n"
        )

    def build_alert_message(self, variable, value, timestamp):
        """Construye la trama ALERT de exactamente 5 campos."""
        alert_type = f"{variable}_HIGH"
        return (
            f"ALERT|{self.node_id}|{alert_type}|{value}|"
            f"{timestamp}\n"
        )

    def run(self, interval_seconds=3):
        print(
            f"[{self.node_id}] Iniciado. Buscando servidor vía DNS: "
            f"{self.server_host}..."
        )

        server_address = self.resolve_dns()
        if not server_address:
            print(f"[{self.node_id}] No se pudo resolver el host.")
            return

        print(
            f"[{self.node_id}] Servidor localizado en IP: "
            f"{server_address[0]}. Iniciando envíos UDP..."
        )

        try:
            while True:
                variable, value = self.generate_sensor_data()
                timestamp = int(time.time())

                # 1. Telemetría periódica.
                data_message = self.build_data_message(
                    variable, value, timestamp
                )
                self.send_message(data_message, server_address)

                # 2. Alerta inmediata si la medición supera el umbral.
                if variable == "TEMP" and value >= TEMP_ALERT_THRESHOLD:
                    alert_message = self.build_alert_message(
                        variable, value, timestamp
                    )
                    print(f"[{self.node_id}]  ALERT detectada")
                    self.send_message(alert_message, server_address)

                # La secuencia identifica la siguiente medición.
                self.sequence_counter += 1
                time.sleep(interval_seconds)

        except KeyboardInterrupt:
            print(f"[{self.node_id}] Detenido por el usuario.")
        except Exception as error:
            print(f"[{self.node_id}] Error inesperado: {error}")
        finally:
            self.sock.close()