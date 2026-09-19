/* nodos.h - Tabla de nodos de telemetria (thread-safe) */

#ifndef NODOS_H
#define NODOS_H

#include <time.h>
#include "config.h"

/* Catalogo de variables: TEMP, HUMD, ELEC (en ese orden). */
#define NUM_VARIABLES 3

typedef struct {
    char id[TAM_ID];
    double valores[NUM_VARIABLES];   /* ultimo valor de cada variable */
    int tiene_valor[NUM_VARIABLES];  /* 1 si ya llego al menos una medicion */
    long timestamp;        /* epoch reportado por el nodo en el ultimo DATA */
    long secuencia;        /* ultimo numero de secuencia recibido */
    time_t ultimo_visto;   /* hora del servidor al recibir el ultimo DATA */
    long recibidos;        /* DATA recibidos */
    long perdidos;         /* DATA perdidos, inferidos por huecos en la secuencia */
} Nodo;

/* Nombre de la variable i del catalogo (0..NUM_VARIABLES-1). */
const char *nodos_nombre_variable(int indice);

/* Registra los nodos validos a partir de una lista "ID1,ID2,...".
 * Retorna cuantos quedaron registrados. */
int nodos_registrar_lista(const char *lista);

/* Retorna 1 si el ID_NODO esta registrado, 0 si no. */
int nodos_existe(const char *id);

/* Guarda la medicion de un nodo ya registrado.
 * Retorna 0 si todo bien, -2 si la variable no existe, -3 si el nodo no esta registrado. */
int nodos_registrar_dato(const char *id, const char *variable, double valor,
                         long timestamp, long secuencia);

/* Copia un nodo a *salida. Retorna 1 si existe, 0 si no. */
int nodos_obtener(const char *id, Nodo *salida);

/* Copia hasta max nodos en destino. Retorna cuantos copio. */
int nodos_copiar_todos(Nodo *destino, int max);

int nodos_esta_activo(const Nodo *nodo, time_t ahora);

void nodos_estadisticas(int *registrados, int *activos, long *recibidos, long *perdidos);

#endif
