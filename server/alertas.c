/* alertas.c - Deteccion de anomalias e historial de alertas (thread-safe) */

#include <stdio.h>
#include <string.h>
#include <pthread.h>
#include "alertas.h"

/* Umbrales (>=). TEMP coincide con el de los simuladores. ELEC va casi al
 * tope de lo que generan (250) para que sea una alerta rara, no constante. */
#define UMBRAL_TEMP 40.0
#define UMBRAL_HUMD 90.0
#define UMBRAL_ELEC 249.0

/* Buffer circular: cuando se llena se sobrescribe la alerta mas antigua. */
static Alerta historial_alertas[MAX_ALERTAS];
static int total_alertas = 0;
static pthread_mutex_t mutex_alertas = PTHREAD_MUTEX_INITIALIZER;

int alertas_evaluar_umbral(const char *variable, double valor,
                           char *codigo_salida, size_t tam) {
    if (strcmp(variable, "TEMP") == 0 && valor >= UMBRAL_TEMP) {
        snprintf(codigo_salida, tam, "TEMP_HIGH");
        return 1;
    }
    if (strcmp(variable, "HUMD") == 0 && valor >= UMBRAL_HUMD) {
        snprintf(codigo_salida, tam, "HUMD_HIGH");
        return 1;
    }
    if (strcmp(variable, "ELEC") == 0 && valor >= UMBRAL_ELEC) {
        snprintf(codigo_salida, tam, "ELEC_HIGH");
        return 1;
    }
    return 0;
}

void alertas_registrar(const char *id_nodo, const char *codigo,
                       double valor, long timestamp) {
    pthread_mutex_lock(&mutex_alertas);

    int guardadas = total_alertas < MAX_ALERTAS ? total_alertas : MAX_ALERTAS;
    for (int i = 0; i < guardadas; i++) {
        Alerta *a = &historial_alertas[i];
        if (a->timestamp == timestamp &&
            strcmp(a->id_nodo, id_nodo) == 0 &&
            strcmp(a->codigo, codigo) == 0) {
            pthread_mutex_unlock(&mutex_alertas);
            return;
        }
    }

    Alerta *nueva = &historial_alertas[total_alertas % MAX_ALERTAS];
    snprintf(nueva->id_nodo, sizeof(nueva->id_nodo), "%s", id_nodo);
    snprintf(nueva->codigo, sizeof(nueva->codigo), "%s", codigo);
    nueva->valor = valor;
    nueva->timestamp = timestamp;
    total_alertas++;

    pthread_mutex_unlock(&mutex_alertas);
}

int alertas_recientes(Alerta *destino, int max) {
    pthread_mutex_lock(&mutex_alertas);

    int guardadas = total_alertas < MAX_ALERTAS ? total_alertas : MAX_ALERTAS;
    int n = guardadas < max ? guardadas : max;
    for (int i = 0; i < n; i++) {
        destino[i] = historial_alertas[(total_alertas - 1 - i) % MAX_ALERTAS];
    }

    pthread_mutex_unlock(&mutex_alertas);
    return n;
}

int alertas_total(void) {
    pthread_mutex_lock(&mutex_alertas);
    int total = total_alertas;
    pthread_mutex_unlock(&mutex_alertas);
    return total;
}
