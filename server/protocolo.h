/* protocolo.h - Parseo y respuestas del protocolo de aplicacion (texto, '|' y '\n')
 *
 * UDP (nodos):     DATA|ID|SEQ|VAR|VALOR|TS\n   ALERT|ID|TIPO|VALOR|TS\n
 *                  Solo se responde ERROR|ERR_00x|descripcion\n si la trama es invalida.
 * TCP (operador):  LIST_NODES, GET_STATUS|ID, GET_MEASUREMENTS, GET_ALERTS,
 *                  GET_SYSTEM_STATUS. Siempre hay una respuesta de una linea.
 */

#ifndef PROTOCOLO_H
#define PROTOCOLO_H

#include <stddef.h>

/* Codigos de error (los mismos que usan los simuladores de nodos) */
#define ERR_FORMATO    "ERR_001"  /* estructura invalida o tipo de mensaje desconocido */
#define ERR_NODO       "ERR_002"  /* ID_NODO invalido, no registrado o tabla llena */
#define ERR_VARIABLE   "ERR_003"  /* variable fuera del catalogo (TEMP, HUMD, ELEC) */
#define ERR_VALOR      "ERR_004"  /* valor no numerico o fuera de rango */
#define ERR_SECUENCIA  "ERR_005"  /* secuencia no es un entero positivo */
#define ERR_TIMESTAMP  "ERR_006"  /* timestamp Epoch invalido */

void protocolo_iniciar(void);

/* Procesa un datagrama UDP de un nodo. Retorna 1 si hay que responder
 * (siempre un ERROR), 0 si la trama fue valida y no se responde. */
int protocolo_procesar_udp(const char *datagrama, size_t len,
                           char *respuesta, size_t tam_respuesta);

/* Procesa una linea de comando TCP del operador (sin '\n' final).
 * Siempre deja una respuesta terminada en '\n'. */
void protocolo_procesar_tcp(const char *linea, char *respuesta, size_t tam_respuesta);

#endif
