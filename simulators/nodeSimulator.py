import random
import socket
import time


# Variables que puede medir el nodo
VARIABLES = {"TEMP", "HUMD", "ELEC"}

# Rangos válidos según el protocolo
RANGES = {
    "TEMP": (-50.0, 80.0),
    "HUMD": (0.0, 100.0),
    "ELEC": (0.0, float("inf")),
}


# Umbrales de alerta.
# Si una medición es igual o superior al umbral,
# se considera una medición crítica.
ALERT_THRESHOLDS = {
    "TEMP": 40.0,
    "HUMD": 90.0,
    "ELEC": 249.0,
}


# Probabilidad de generar una medición crítica.
# 0.01 = 1%
CRITICAL_PROBABILITY = 0.01


class NodeClient:
    def __init__(
        self,
        node_id,
        server_host,
        server_port,
        interval_min=2,
        interval_max=4,
        simulated_loss_probability=0.0,
    ):
        self.node_id = node_id
        self.server_host = server_host
        self.server_port = server_port

        self.interval_min = interval_min
        self.interval_max = interval_max

        self.simulated_loss_probability = simulated_loss_probability

        self.sequence_counter = 1

        # Socket UDP
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Timeout utilizado para esperar respuestas del servidor
        self.sock.settimeout(0.5)

    def resolve_server(self):
        """
        Resuelve el nombre del servidor mediante DNS.
        """
        try:
            server_ip = socket.gethostbyname(self.server_host)

            print(
                f"[{self.node_id}] Servidor resuelto: "
                f"{self.server_host} -> {server_ip}"
            )

            return server_ip

        except socket.gaierror as e:
            print(
                f"[{self.node_id}] Error resolviendo servidor "
                f"{self.server_host}: {e}"
            )
            return None

    def generate_sensor_data(self):
        """
        Genera una medición normal o crítica.

        La probabilidad de generar una medición crítica es del 1%.
        La variable que se mide se selecciona aleatoriamente.

        Rangos normales:
            TEMP: 20 - 39 °C
            HUMD: 30 - 89 %
            ELEC: 90 - 248

        Rangos críticos:
            TEMP: 40 - 45
            HUMD: 90 - 100
            ELEC: 249 - 255
        """

        # Valores normales.
        # Se mantienen por debajo de los umbrales de alerta.
        data_readings = {
            "TEMP": round(random.uniform(20.0, 39.0), 1),
            "HUMD": round(random.uniform(30.0, 89.0), 1),
            "ELEC": round(random.uniform(90.0, 248.0), 1),
        }

        # Seleccionamos aleatoriamente qué variable medir.
        variable = random.choice(list(data_readings.keys()))

        # Valor normal inicialmente.
        value = data_readings[variable]

        # 1% de probabilidad de generar una medición crítica.
        if random.random() < CRITICAL_PROBABILITY:

            if variable == "TEMP":
                value = round(random.uniform(40.0, 45.0), 1)

            elif variable == "HUMD":
                value = round(random.uniform(90.0, 100.0), 1)

            elif variable == "ELEC":
                value = round(random.uniform(249.0, 255.0), 1)

        return variable, value

    def parse_error_response(self, response):
        """
        Revisa si la respuesta del servidor corresponde
        a un mensaje ERROR del protocolo.
        """

        if not response:
            return None

        response = response.strip()

        parts = response.split("|")

        if len(parts) >= 2 and parts[0] == "ERROR":
            return parts[1]

        return None

    def wait_for_response(self):
        """
        Espera una respuesta UDP del servidor.

        El servidor puede no responder para mensajes válidos,
        por lo que el timeout es normal.
        """

        try:
            response, _ = self.sock.recvfrom(2048)

            response = response.decode("utf-8", errors="replace").strip()

            return response

        except socket.timeout:
            return None

        except OSError as e:
            print(
                f"[{self.node_id}] Error recibiendo respuesta: {e}"
            )
            return None

    def send_message(self, message, server_address):
        """
        Envía un mensaje UDP al servidor.

        Si el servidor responde con un error, se devuelve
        el código de error.

        Para ERR_002 se utiliza la política de reintento
        definida en el protocolo.
        """

        # Simulación opcional de pérdida de paquetes.
        if (
            self.simulated_loss_probability > 0
            and random.random() < self.simulated_loss_probability
        ):
            print(
                f"[{self.node_id}] "
                f"Paquete UDP simulado como perdido"
            )
            return None

        try:
            self.sock.sendto(
                message.encode("utf-8"),
                server_address,
            )

            print(
                f"[{self.node_id}] UDP enviado: "
                f"{message.strip()}"
            )

        except OSError as e:
            print(
                f"[{self.node_id}] Error enviando UDP: {e}"
            )
            return None

        # El servidor solamente responde en determinados casos,
        # especialmente cuando existe un ERROR.
        response = self.wait_for_response()

        if response:
            error_code = self.parse_error_response(response)

            if error_code:
                print(
                    f"[{self.node_id}] "
                    f"Servidor respondió: {response}"
                )

                return error_code

        return None

    def send_with_retry(self, message, server_address):
        """
        Envía un mensaje aplicando la política de reintento.

        ERR_002 = nodo desconocido:
            máximo 3 intentos.

        Los demás errores no se reintentan.
        """

        max_retries = 3

        for attempt in range(1, max_retries + 1):

            error_code = self.send_message(
                message,
                server_address,
            )

            # No hubo error.
            if error_code is None:
                return True

            # ERR_002 permite reintento.
            if error_code == "ERR_002":

                if attempt < max_retries:

                    print(
                        f"[{self.node_id}] "
                        f"ERR_002. Reintentando "
                        f"({attempt}/{max_retries})..."
                    )

                    time.sleep(0.5)

                    continue

                print(
                    f"[{self.node_id}] "
                    f"ERR_002. Se alcanzó el máximo "
                    f"de reintentos."
                )

                return False

            # Los demás errores no deben reintentarse.
            print(
                f"[{self.node_id}] "
                f"Error {error_code}. "
                f"No se reintenta."
            )

            return False

        return False

    def build_data_message(
        self,
        variable,
        value,
        timestamp,
    ):
        """
        Construye un mensaje DATA según el protocolo:

        DATA|ID_NODO|SECUENCIA|VARIABLE|VALOR|TIMESTAMP
        """

        return (
            f"DATA|"
            f"{self.node_id}|"
            f"{self.sequence_counter}|"
            f"{variable}|"
            f"{value}|"
            f"{timestamp}\n"
        )

    def build_alert_message(
        self,
        variable,
        value,
        timestamp,
    ):
        """
        Construye un mensaje ALERT según el protocolo:

        ALERT|ID_NODO|TIPO_ALERTA|VALOR|TIMESTAMP
        """

        alert_type = f"{variable}_HIGH"

        return (
            f"ALERT|"
            f"{self.node_id}|"
            f"{alert_type}|"
            f"{value}|"
            f"{timestamp}\n"
        )

    def run(self, interval_seconds=None):
        """
        Ciclo principal del nodo.

        Cada 2-4 segundos:

        1. Genera una medición.
        2. Envía DATA.
        3. Si la medición es crítica, envía ALERT.
        4. Incrementa la secuencia.
        """

        # Resolver el servidor mediante DNS.
        server_ip = self.resolve_server()

        if server_ip is None:
            print(
                f"[{self.node_id}] "
                f"No se pudo resolver el servidor."
            )
            return

        server_address = (
            server_ip,
            self.server_port,
        )

        print(
            f"[{self.node_id}] "
            f"Iniciando simulación hacia "
            f"{server_ip}:{self.server_port}"
        )

        try:

            while True:

                # -------------------------------------------------
                # 1. Generar medición
                # -------------------------------------------------

                variable, value = self.generate_sensor_data()

                # IMPORTANTE:
                # DATA y ALERT utilizan exactamente el mismo
                # timestamp cuando pertenecen a la misma medición.
                timestamp = int(time.time())

            

                data_message = self.build_data_message(
                    variable,
                    value,
                    timestamp,
                )

                print(
                    f"[{self.node_id}] "
                    f"Medición: {variable}={value}"
                )

                self.send_with_retry(
                    data_message,
                    server_address,
                )

        
                threshold = ALERT_THRESHOLDS[variable]

                if value >= threshold:

                    alert_message = self.build_alert_message(
                        variable,
                        value,
                        timestamp,
                    )

                    print(
                        f"[{self.node_id}] "
                        f"ALERT detectada: "
                        f"{variable}={value} "
                        f"(umbral={threshold})"
                    )

                    self.send_with_retry(
                        alert_message,
                        server_address,
                    )

           

                self.sequence_counter += 1

                

                if interval_seconds is not None:
                    time.sleep(interval_seconds)
                else:
                    wait_time = random.uniform(
                     self.interval_min,
                     self.interval_max,
                    )

                    time.sleep(wait_time)

        except KeyboardInterrupt:

            print(
                f"\n[{self.node_id}] "
                f"Simulación detenida."
            )

        finally:

            self.sock.close()