/* alertas.h - Deteccion de anomalias e historial de alertas (thread-safe) */

#ifndef ALERTAS_H
#define ALERTAS_H

#include <stddef.h>
#include "config.h"

typedef struct {
    char id_nodo[TAM_ID];
    char codigo[32];       /* ej. TEMP_HIGH */
    double valor;
    long timestamp;        /* epoch reportado por el nodo */
} Alerta;

/* Retorna 1 si el valor supera el umbral de la variable y escribe el
 * codigo de alerta (ej. TEMP_HIGH) en codigo_salida. */
int alertas_evaluar_umbral(const char *variable, double valor,
                           char *codigo_salida, size_t tam);

/* Guarda la alerta. Si ya existe una igual (mismo nodo, codigo y timestamp)
 * no la duplica: el nodo envia ALERT y el servidor tambien la detecta en DATA. */
void alertas_registrar(const char *id_nodo, const char *codigo,
                       double valor, long timestamp);

/* Copia hasta max alertas, de la mas reciente a la mas antigua. */
int alertas_recientes(Alerta *destino, int max);

/* Total de alertas registradas desde que inicio el servidor. */
int alertas_total(void);

#endif
