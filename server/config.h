/* config.h - Constantes globales del servidor central */

#ifndef CONFIG_H
#define CONFIG_H

/* Puertos por defecto (se pueden cambiar con PUERTO_TCP y PUERTO_UDP).
 * TCP y UDP son espacios de puertos distintos, por eso pueden coincidir. */
#define PUERTO_TCP_DEFECTO 5000
#define PUERTO_UDP_DEFECTO 5000

#define BACKLOG 10
#define TAM_LINEA 512          /* maximo de una linea de comando TCP */
#define TAM_DATAGRAMA 2048     /* maximo de un datagrama UDP */
#define TAM_RESPUESTA 4096

#define TAM_ID 32              /* incluye el '\0' */
#define MAX_NODOS 20

/* Nodos registrados al iniciar (ID_NODO validos). Se puede cambiar con la
 * variable de entorno NODOS_REGISTRADOS, separando los IDs con comas. */
#define NODOS_REGISTRADOS_DEFECTO "NODE01,NODE02,NODE03,NODE04,NODE05"
#define MAX_ALERTAS 50
#define ALERTAS_EN_CONSULTA 10

/* Un nodo se considera activo si envio algo en los ultimos N segundos.
 * Los simuladores envian cada 2-4 s. */
#define TIMEOUT_NODO_SEG 15

#endif
