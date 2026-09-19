/* nodos.c - Tabla de nodos de telemetria (thread-safe) */

#include <stdio.h>
#include <string.h>
#include <pthread.h>
#include "nodos.h"

static Nodo tabla_nodos[MAX_NODOS];
static int cantidad_nodos = 0;
static pthread_mutex_t mutex_nodos = PTHREAD_MUTEX_INITIALIZER;

static const char *catalogo_variables[NUM_VARIABLES] = {"TEMP", "HUMD", "ELEC"};

const char *nodos_nombre_variable(int indice) {
    return catalogo_variables[indice];
}

static int indice_variable(const char *variable) {
    for (int i = 0; i < NUM_VARIABLES; i++) {
        if (strcmp(catalogo_variables[i], variable) == 0) {
            return i;
        }
    }
    return -1;
}

/* Llamar con mutex_nodos tomado. */
static int buscar_nodo(const char *id) {
    for (int i = 0; i < cantidad_nodos; i++) {
        if (strcmp(tabla_nodos[i].id, id) == 0) {
            return i;
        }
    }
    return -1;
}

int nodos_registrar_lista(const char *lista) {
    char copia[256];
    snprintf(copia, sizeof(copia), "%s", lista);

    pthread_mutex_lock(&mutex_nodos);

    char *guardado;
    for (char *id = strtok_r(copia, ",", &guardado); id != NULL; id = strtok_r(NULL, ",", &guardado)) {
        if (strlen(id) >= TAM_ID || buscar_nodo(id) != -1) {
            continue;
        }
        if (cantidad_nodos >= MAX_NODOS) {
            break;
        }
        memset(&tabla_nodos[cantidad_nodos], 0, sizeof(Nodo));
        snprintf(tabla_nodos[cantidad_nodos].id, TAM_ID, "%s", id);
        cantidad_nodos++;
    }
    int total = cantidad_nodos;

    pthread_mutex_unlock(&mutex_nodos);
    return total;
}

int nodos_existe(const char *id) {
    pthread_mutex_lock(&mutex_nodos);
    int existe = buscar_nodo(id) != -1;
    pthread_mutex_unlock(&mutex_nodos);
    return existe;
}

int nodos_registrar_dato(const char *id, const char *variable, double valor,
                         long timestamp, long secuencia) {
    int variable_idx = indice_variable(variable);
    if (variable_idx < 0) {
        return -2;
    }

    pthread_mutex_lock(&mutex_nodos);

    int indice = buscar_nodo(id);
    if (indice == -1) {
        pthread_mutex_unlock(&mutex_nodos);
        return -3;
    }

    Nodo *nodo = &tabla_nodos[indice];

    /* Una secuencia menor a la ultima significa que el nodo se reinicio (vuelve a
     * contar desde 1, aunque ese primer mensaje se haya perdido). Un salto hacia
     * adelante son mensajes UDP perdidos. Una secuencia repetida es un duplicado. */
    int reinicio = secuencia < nodo->secuencia;
    if (!reinicio && nodo->secuencia > 0 && secuencia > nodo->secuencia + 1) {
        nodo->perdidos += secuencia - nodo->secuencia - 1;
    }
    nodo->recibidos++;
    nodo->ultimo_visto = time(NULL);

    if (secuencia != nodo->secuencia) {
        nodo->secuencia = secuencia;
        nodo->valores[variable_idx] = valor;
        nodo->tiene_valor[variable_idx] = 1;
        nodo->timestamp = timestamp;
    }

    pthread_mutex_unlock(&mutex_nodos);
    return 0;
}

int nodos_obtener(const char *id, Nodo *salida) {
    pthread_mutex_lock(&mutex_nodos);

    int indice = buscar_nodo(id);
    if (indice != -1) {
        *salida = tabla_nodos[indice];
    }

    pthread_mutex_unlock(&mutex_nodos);
    return indice != -1;
}

int nodos_copiar_todos(Nodo *destino, int max) {
    pthread_mutex_lock(&mutex_nodos);

    int n = cantidad_nodos < max ? cantidad_nodos : max;
    memcpy(destino, tabla_nodos, n * sizeof(Nodo));

    pthread_mutex_unlock(&mutex_nodos);
    return n;
}

int nodos_esta_activo(const Nodo *nodo, time_t ahora) {
    return (ahora - nodo->ultimo_visto) <= TIMEOUT_NODO_SEG;
}

void nodos_estadisticas(int *registrados, int *activos, long *recibidos, long *perdidos) {
    time_t ahora = time(NULL);

    pthread_mutex_lock(&mutex_nodos);

    *registrados = cantidad_nodos;
    *activos = 0;
    *recibidos = 0;
    *perdidos = 0;
    for (int i = 0; i < cantidad_nodos; i++) {
        if (nodos_esta_activo(&tabla_nodos[i], ahora)) {
            (*activos)++;
        }
        *recibidos += tabla_nodos[i].recibidos;
        *perdidos += tabla_nodos[i].perdidos;
    }

    pthread_mutex_unlock(&mutex_nodos);
}
