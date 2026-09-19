/* red.h - Sockets TCP (operadores) y UDP (nodos) del servidor */

#ifndef RED_H
#define RED_H

#include <signal.h>

/* Lo pone en 1 el manejador de SIGINT/SIGTERM para terminar ordenadamente. */
extern volatile sig_atomic_t servidor_detenido;

/* Crea el socket TCP de escucha (socket, bind, listen). Retorna el fd o -1. */
int red_abrir_tcp(int puerto);

/* Bucle de accept: un hilo por cada operador conectado. */
void red_atender_tcp(int socket_escucha);

/* Crea el socket UDP y lanza el hilo que recibe la telemetria. Retorna 0 o -1. */
int red_iniciar_udp(int puerto);

#endif
