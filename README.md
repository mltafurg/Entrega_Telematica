# Entrega_Telematica

# Guía de Integración: Simulador Python (Nodos) -> Servidor C

detalles clave para que el servidor en C reciba correctamente los mensajes del simulador de nodos.

## 1. Ejecución del Simulador (No requiere cambios en código)
El archivo `main.py` está preparado para conectarse a cualquier entorno leyendo las variables dinámicamente. No necesitas modificar nada en los scripts de Python.

*   **Para pruebas locales:** Solo ejecuta `python main.py`. Por defecto, apuntará a `localhost` en el puerto `5000`.
*   **Para pruebas en red (ej. AWS EC2 o máquinas distintas):** Pasa tu IP y puerto directamente por la terminal:
    *   *Linux/Mac:* `SERVER_HOST="<TU_IP_AQUI>" SERVER_PORT="<TU_PUERTO>" python main.py`
    *   *Windows (PowerShell):* `$env:SERVER_HOST="<TU_IP_AQUI>"; $env:SERVER_PORT="<TU_PUERTO>"; python main.py`

## 2. Estructura de las Tramas UDP
El simulador envía los datos usando el delimitador `|` y **todas las tramas terminan estrictamente con un salto de línea (`\n`)**. 
Ejemplos exactos de lo que te va a llegar al *socket* en C:
*   **DATA:** `DATA|NODE01|1|TEMP|25.4|1690000000\n`
*   **ALERT:** `ALERT|NODE01|TEMP_HIGH|42.1|1690000000\n`

## 3. Recomendaciones Clave para el Parsing en C
*   **El salto de línea (`\n`):** Antes de dividir la trama, asegúrate de limpiar o reemplazar el `\n` al final del *buffer* recibido. Si no lo haces, el último campo (el *timestamp*) te quedará con basura (ej. `"1690000000\n"`) y fallará la conversión a entero.
*   **Cuidado con `strtok`:** La función `strtok` de la librería `<string.h>` suele omitir campos vacíos si hay dos delimitadores seguidos (`||`). Aunque el simulador Python envía todos los datos completos, si planeas validar errores de estructura (como el `ERR_001`), es más seguro usar `strsep` o contar los delimitadores manualmente.
*   **Liberar el puerto:** Cuando vayas a encender el servidor en C, asegúrate de que el archivo `test.py` no esté corriendo en ninguna terminal. Si ambos intentan escuchar en el puerto 5000 al mismo tiempo, el sistema te dará un error de "puerto ocupado".