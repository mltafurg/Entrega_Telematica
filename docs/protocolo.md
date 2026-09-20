# Especificación del Protocolo de Capa de Aplicación

## Plataforma Distribuida de Telemetría y Gestión de Infraestructura Inteligente

---

### 1. Introducción
El presente documento especifica el protocolo propio de capa de aplicación basado en texto plano diseñado para la comunicación entre los nodos IoT de telemetría, el servidor central en C y los clientes operadores (GUI / CLI / Servicio Web).

- **Delimitador de campos:** Cada mensaje utiliza obligatoriamente el carácter barra vertical (`|`) como separador estricto entre sus elementos.
- **Terminador de trama:** Cada mensaje finaliza estrictamente con un carácter de salto de línea (`\n`), lo que permite identificar el fin de lectura en los sockets.

---

### 2. Formato General de Trama
Todas las tramas intercambiadas siguen la siguiente estructura sintáctica:

```
ACCIÓN|PARAMETRO_1|PARAMETRO_2|...|PARAMETRO_N\n
```

---

### 3. Tipos de Mensajes y Acciones

#### 3.1. Mensajes de Telemetría y Alertas (Nodos $\rightarrow$ Servidor vía UDP)

* **`DATA` (6 campos obligatorios)**
  * **Estructura:** `DATA|ID_NODO|SECUENCIA|VARIABLE|VALOR|TIMESTAMP\n`
  * **Descripción:** Envío periódico de mediciones desde el nodo hacia el servidor central.
  * **Transporte:** UDP.
  * **Respuesta:** Si la trama es válida, el servidor no responde (ahorro de ancho de banda). Si la trama es corrupta o inválida, el servidor responde con un mensaje `ERROR`.

* **`ALERT` (5 campos obligatorios)**
  * **Estructura:** `ALERT|ID_NODO|TIPO_ALERTA|VALOR|TIMESTAMP\n`
  * **Descripción:** Notificación prioritaria inmediata enviada cuando el nodo detecta una medición anómala que supera el umbral crítico.
  * **Transporte:** UDP.
  * **Comportamiento en servidor:** Registra la alerta en el historial. Si el servidor ya había generado automáticamente la misma alerta a partir de un paquete `DATA`, no la duplica. No requiere respuesta si es válida.

---

#### 3.2. Mensajes de Consulta y Control (Operador $\leftrightarrow$ Servidor vía TCP)

* **`GET_STATUS` (2 campos obligatorios)**
  * **Estructura:** `GET_STATUS|ID_NODO\n`
  * **Respuesta:** `STATUS_RESP|ID_NODO|ESTADO|TIMESTAMP|VAR1:VAL|VAR2:VAL|VAR3:VAL\n`
  * **Regla:** `ESTADO` toma el valor `ONLINE` si el nodo ha reportado telemetría en los últimos 15 segundos, o `OFFLINE` en caso contrario. Para nodos registrados sin mediciones previas, responde `STATUS_RESP|NODE02|OFFLINE|0`.

* **`LIST_NODES` / `NODES_RESP`**
  * **Estructura Consulta:** `LIST_NODES\n`
  * **Estructura Respuesta:** `NODES_RESP|NODE01:ONLINE|NODE02:OFFLINE|...\n`
  * **Descripción:** Devuelve la lista de nodos registrados y su estado actual en la red.

* **`GET_MEASUREMENTS` / `MEASUREMENTS_RESP`**
  * **Estructura Consulta:** `GET_MEASUREMENTS\n`
  * **Estructura Respuesta:** `MEASUREMENTS_RESP|NODE01:TEMP:25.4:1758744000|...\n`
  * **Descripción:** Consulta las últimas mediciones de cada variable para todos los nodos.

* **`GET_ALERTS` / `ALERTS_RESP`**
  * **Estructura Consulta:** `GET_ALERTS\n`
  * **Estructura Respuesta:** `ALERTS_RESP|TOTAL_ALERTAS|NODO|TIPO|VALOR|TIMESTAMP|...\n`
  * **Descripción:** Retorna el historial de alertas detectadas en el sistema.

* **`GET_SYSTEM_STATUS` / `SYSTEM_STATUS_RESP`**
  * **Estructura Consulta:** `GET_SYSTEM_STATUS\n`
  * **Estructura Respuesta:** `SYSTEM_STATUS_RESP|REGISTRADOS|ACTIVOS|TOTAL_ALERTAS|PAQUETES_RECIBIDOS\n`
  * **Descripción:** Retorna el resumen del estado global de la infraestructura.

---

### 4. Catálogo de Variables y Tipos de Datos

#### 4.1. Variables de Telemetría
* **`TEMP`**: Temperatura ambiental medida en grados Celsius (°C). Ejemplo: `24.8`.
* **`HUMD`**: Humedad relativa en porcentaje (%). Ejemplo: `65.2`.
* **`ELEC`**: Consumo energético en kilovatios-hora (kWh) o Watts. Ejemplo: `150.4`.

#### 4.2. Tipos de Datos Auxiliares
* **Secuencia:** Número entero positivo estrictamente creciente que permite al servidor rastrear datagramas y detectar pérdidas en UDP.
* **Timestamp:** Representación de tiempo en formato Epoch (número entero de segundos desde el 1 de enero de 1970 UTC).

---

### 5. Códigos de Error y Políticas de Reintento

Cuando el servidor detecta una anomalía o falla en la estructura del mensaje recibido, emite una respuesta de error en texto plano:

```
ERROR|CÓDIGO|DESCRIPCIÓN\n
```

#### 5.1. Catálogo de Errores

| Código | Nombre | Descripción |
| :---: | :--- | :--- |
| `ERR_001` | Formato inválido | La estructura no cumple con el número de campos o separadores esperados (`|`). |
| `ERR_002` | Nodo desconocido | El `ID_NODO` reportado no está registrado en el servidor. |
| `ERR_003` | Variable no reconocida | La variable enviada no pertenece al catálogo permitido (`TEMP`, `HUMD`, `ELEC`). |
| `ERR_004` | Valor fuera de rango | El valor numérico reportado es físicamente imposible o viola los límites del protocolo. |
| `ERR_005` | Secuencia inválida | El valor de la secuencia no es un número entero válido. |
| `ERR_006` | Timestamp inválido | El timestamp no sigue el formato Epoch entero correcto. |

#### 5.2. Políticas de Manejo de Errores en los Nodos

* **Errores de Lógica (`ERR_001`, `ERR_003`, `ERR_005`, `ERR_006`):**
  * **Política:** **NO REINTENTAR.**
  * **Razón:** Son errores de sintaxis o programación en el armado del mensaje. Reenviar la trama causaría un bucle de saturación en la red. El nodo registra el error en consola, descarta la trama y aguarda al siguiente ciclo.
* **Errores de Estado / Fallas Temporales (`ERR_002`):**
  * **Política:** **REINTENTO CONTROLADO (Máximo 3 intentos).**
  * **Razón:** Si un nodo intenta reportar datos o alertas pero el servidor responde que no está registrado aún por una falla temporal, el emisor reintenta la operación de forma controlada.

---

### 6. Ejemplos de Intercambio de Tramas

1. **Envío de Telemetría (Nodo $\rightarrow$ Servidor vía UDP):**
   ```text
   DATA|NODE01|12|TEMP|24.8|1758744000\n
   ```

2. **Consulta de Estado de Nodo (Operador $\rightarrow$ Servidor vía TCP):**
   ```text
   GET_STATUS|NODE01\n
   ```

3. **Respuesta del Servidor al Operador (Servidor $\rightarrow$ Operador vía TCP):**
   ```text
   STATUS_RESP|NODE01|ONLINE|1758744000|TEMP:24.8|HUMD:65.2|ELEC:150.4\n
   ```

4. **Notificación de Alerta Crítica (Nodo $\rightarrow$ Servidor vía UDP):**
   ```text
   ALERT|NODE03|TEMP_HIGH|42.1|1758744000\n
   ```

5. **Mensaje de Error Estructurado (Servidor $\rightarrow$ Emisor):**
   ```text
   ERROR|ERR_001|Estructura de campos incompleta o invalida\n
   ```

---

### 7. Justificación de los Protocolos de Transporte (UDP vs TCP)

* **UDP (User Datagram Protocol) - Telemetría de Nodos:**
  * Se utiliza para el envío periódico de mediciones de sensores.
  * **Justificación:** Los nodos IoT envían flujos constantes de telemetría. La pérdida ocasional de un datagrama individual es tolerable, ya que la siguiente lectura llegará inmediatamente después. UDP elimina la sobrecarga del Three-Way Handshake y de conexiones persistentes, optimizando el ancho de banda y permitiendo alta concurrencia en el servidor central.

* **TCP (Transmission Control Protocol) - Consultas de Operadores y Servicio Web:**
  * Se utiliza para la gestión del sistema, paneles de control y cliente gráfico.
  * **Justificación:** Las operaciones de supervisión requieren estricta confiabilidad, entrega ordenada y cero pérdidas de información. Un operador no puede recibir respuestas parciales ni truncadas al consultar el estado de la infraestructura o la lista de alertas.

