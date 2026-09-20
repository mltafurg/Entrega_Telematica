# Entrega_Telematica
# Plataforma Distribuida de Telemetría y Gestión de Infraestructura Inteligente

**Asignatura:** Telemática / Internet: Arquitectura y Protocolos  
**Tecnologías:** C, Python, Docker, Sockets TCP/UDP, POSIX Threads, Flask, Tkinter, AWS EC2.

El sistema es una solución distribuida para el monitoreo y gestión en tiempo real de instalaciones remotas equipadas con dispositivos IoT. Los nodos simulados capturan periódicamente variables de telemetría (temperatura, humedad y consumo eléctrico) y envían datagramas UDP hacia un servidor central desarrollado en C y desplegado en la nube dentro de un contenedor Docker.

---

## 1. Estructura del Repositorio

```text
Entrega_Telematica/
├── server/                     # Servidor Central en C
│   ├── main.c                  # Punto de entrada y manejo de señales
│   ├── red.c / red.h           # Gestión de Sockets TCP/UDP y Concurrencia POSIX
│   ├── nodos.c / nodos.h       # Tabla hash / lista de nodos y estado (ONLINE/OFFLINE)
│   ├── protocolo.c / .h        # Parser y generador de tramas de texto
│   ├── alertas.c / .h          # Gestor e historial de alertas críticas
│   ├── config.h                # Definiciones de puertos y constantes
│   ├── Makefile                # Script de compilación del servidor C
│   └── Dockerfile              # Construcción multietapa (Multi-stage build) Debian
├── simulators/                 # Nodos IoT Simulados
│   ├── main.py                 # Orquestador concurrente (5 hilos simultáneos)
│   └── nodeSimulator.py        # Cliente de telemetría UDP, DNS, reintentos y alertas
├── clients/                    # Clientes de Operador
│   ├── operator_gui.py         # Interfaz Gráfica Tkinter (Pestañas de consulta)
│   ├── operator_cli.py         # Interfaz de Línea de Comandos
│   └── tcp_client.py           # Cliente TCP reutilizable para protocolo
├── interface/webservice/       # Servicio Web Dashboard (HTTP)
│   ├── app.py                  # Servidor Flask (Puerto 8080)
│   ├── tcp_client.py           # Adaptador TCP hacia el servidor C
│   ├── templates/              # Vistas HTML/CSS
│   └── Dockerfile              # Imagen Docker para el servicio web
├── docs/                       # Documentación
│   └── protocolo.md            # Especificación detallada del Protocolo de Aplicación
├── docker-compose.yml          # Orquestación de contenedores (Servidor C + Servicio Web)
└── README.md                   # Guía de ejecución y despliegue
```

---

## 2. Requisitos Previos y Configuración de Red

Para permitir la comunicación entre los nodos, el cliente operador y el servidor central:

- **Dockers y Docker Compose** instalados en la máquina del servidor.
- **Reglas de entrada (Inbound Rules)** en el **Security Group** de AWS EC2:
  - `5000/UDP`: Recepción de telemetría de Nodos IoT.
  - `5000/TCP`: Conexiones interactivas del Cliente Operador y Servicio Web.
  - `8080/TCP`: Acceso al Dashboard Web desde el navegador.

---

## 3. Escenario A: Despliegue en la Nube (AWS EC2) y Conexión Remota

Utiliza este flujo para desplegar el servidor en AWS y conectarle los nodos y el cliente operador desde tu equipo personal.

### Paso 1: Iniciar el Servidor en AWS EC2 (Vía SSH)
Conéctate a tu instancia de AWS EC2 y ejecuta:

```bash
ssh -i "ruta\a\telematica-key.pem" ubuntu@IP-O-DOMINIO
git clone https://github.com/tu-usuario/Entrega_Telematica.git
cd Entrega_Telematica
docker compose up -d --build
```

Verifica que los contenedores estén activos:
```bash
docker ps
```

### Paso 2: Probar el Servicio Web
Abre un navegador e ingresa a la dirección de tu servidor AWS en el puerto 8080:
```text
http://<IP_PUBLICA_EC2_O_DNS>:8080
Ejemplo: telematica-entrega1-eafit.duckdns.org:8080
```
Dominio gratuito creado en duckdns.org, apuntando a esa IP elástica: telematica-entrega1-eafit.duckdns.org. Para probar ejecuta:
```bash
nslookup telematica-entrega1-eafit.duckdns.org
```
Servicio web el cual da una vista general de lo que esta sucediendo con los nodos.

### Paso 3: Ejecutar Nodos Simuladores desde tu PC Local
Desde una terminal en tu computadora personal situado en la carpeta de tu proyecto, apunta los nodos hacia el servidor en la nube usando el DNS o IP pública de AWS:

- **Linux / macOS:**
  ```bash
  SERVER_HOST="telematica-entrega1-eafit.duckdns.org" SERVER_PORT="5000" python simulators/main.py
  ```
- **Windows (PowerShell):**
  ```powershell
  $env:SERVER_HOST="telematica-entrega1-eafit.duckdns.org"; $env:SERVER_PORT="5000"; python simulators/main.py
  ```

### Paso 4: Ejecutar el Cliente Operador GUI desde tu PC Local
En otra terminal en tu PC sin detener los simuladores, conecta la interfaz gráfica al servidor en AWS:

- **Linux / macOS:**
  ```bash
  SERVER_HOST="ec2-54-156-62-108.compute-1.amazonaws.com" SERVER_PORT="5000" python clients/operator_gui.py
  ```
- **Windows (PowerShell):**
  ```powershell
  $env:SERVER_HOST="telematica-entrega1-eafit.duckdns.org"; $env:SERVER_PORT="5000"; python clients/operator_gui.py
  ```
Interfaz iteractiva con 5 pestañas: Nodos activos, Últimas mediciones, Consultar nodo, Alertas, Estado general. Se auto-actualiza cada 4 segundos (togglable).

**Para apagar todo**

En la instancia por SSH:

```bash
docker compose down
```
---

## 4. Escenario B: Ejecución y Pruebas 100% Locales (en tu PC)

Utiliza este flujo para probar todo el ecosistema de forma local en tu computadora sin depender de AWS.

### Paso 1: Compilar y Ejecutar el Servidor C en Local

```bash
cd server
make
./servidor
```

### Paso 2: Ejecutar los Nodos Simuladores Apuntando a `localhost`

- **Linux / macOS:**
  ```bash
  SERVER_HOST="localhost" SERVER_PORT="5000" python simulators/main.py
  ```
- **Windows (PowerShell):**
  ```powershell
  $env:SERVER_HOST="localhost"; $env:SERVER_PORT="5000"; python simulators/main.py
  ```

### Paso 3: Ejecutar la Interfaz Gráfica Apuntando a `localhost`

- **Linux / macOS:**
  ```bash
  SERVER_HOST="localhost" SERVER_PORT="5000" python clients/operator_gui.py
  ```
- **Windows (PowerShell):**
  ```powershell
  $env:SERVER_HOST="localhost"; $env:SERVER_PORT="5000"; python clients/operator_gui.py
  ```

---

## 5. Protocolo de Aplicación

El sistema implementa un protocolo propio de capa de aplicación basado en texto plano.

- **Delimitador:** `|` (Barra vertical)
- **Terminador de trama:** `\n` (Salto de línea)

### Ejemplos de tramas:
- **Telemetría (UDP):** `DATA|NODE01|12|TEMP|24.8|1758744000\n`
- **Alerta (UDP):** `ALERT|NODE03|TEMP_HIGH|42.1|1758744000\n`
- **Consulta Operador (TCP):** `GET_STATUS|NODE01\n`
- **Respuesta Operador (TCP):** `STATUS_RESP|NODE01|ONLINE|1758744000|TEMP:24.8|HUMD:65.2|ELEC:150.4\n`

> 📄 **Documentación Completa:** Revisa la especificación detallada del protocolo, códigos de error (`ERR_001` a `ERR_006`) y políticas de reintento en [`docs/protocolo.md`]

---

## 6. Diagnóstico y Solución de Problemas

1. **`ERR_CONNECTION_TIMED_OUT` en el navegador o GUI:**
   - Verifica las **Inbound Rules** en el Security Group de AWS EC2 (abrir puertos `5000/TCP`, `5000/UDP` y `8080/TCP`).
   - Revisa si la IP pública o dominio de la EC2 cambió tras reiniciar la instancia.

2. **Error `Sin conexión` en la GUI:**
   - Si estás usando AWS, asegúrate de haber configurado `$env:SERVER_HOST` con el dominio/IP de AWS y no con `localhost`.

3. **Error `Puerto 5000 ocupado`:**
   - Asegúrate de detener cualquier instancia previa del servidor antes de volver a ejecutar `make` o `docker compose`.
