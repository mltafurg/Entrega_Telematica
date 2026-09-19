/* protocolo.c - Parseo y respuestas del protocolo de aplicacion */

#include <ctype.h>
#include <errno.h>
#include <math.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "alertas.h"
#include "config.h"
#include "nodos.h"
#include "protocolo.h"

#define MAX_CAMPOS 8

static time_t hora_inicio;

void protocolo_iniciar(void) {
    hora_inicio = time(NULL);
}

// ---------- Utilidades ----------

/* Divide la linea en campos separados por '|' (modifica la linea).
 * Conserva los campos vacios, a diferencia de strtok. Retorna cuantos campos
 * hay, o max + 1 si sobran. */
static int dividir_campos(char *linea, char *campos[], int max) {
    int n = 0;
    char *p = linea;

    campos[n++] = p;
    while ((p = strchr(p, '|')) != NULL) {
        if (n == max) {
            return max + 1;
        }
        *p++ = '\0';
        campos[n++] = p;
    }
    return n;
}

/* Escribe el valor con hasta 2 decimales sin ceros de sobra, dejando al menos
 * uno (24.80 -> 24.8, 30.00 -> 30.0), como en los ejemplos del protocolo. */
static void formatear_valor(double valor, char *salida, size_t tam) {
    snprintf(salida, tam, "%.2f", valor);
    char *fin = salida + strlen(salida) - 1;
    while (fin > salida && *fin == '0' && *(fin - 1) != '.') {
        *fin-- = '\0';
    }
}

static void responder_error(char *respuesta, size_t tam, const char *codigo, const char *descripcion) {
    snprintf(respuesta, tam, "ERROR|%s|%s\n", codigo, descripcion);
}

__attribute__((format(printf, 3, 4)))
static void anexar(char *destino, size_t tam, const char *formato, ...) {
    size_t usado = strlen(destino);
    if (usado >= tam - 1) {
        return;
    }
    va_list args;
    va_start(args, formato);
    vsnprintf(destino + usado, tam - usado, formato, args);
    va_end(args);
}

static int parsear_entero_positivo(const char *texto, long *salida) {
    char *fin;
    errno = 0;
    long valor = strtol(texto, &fin, 10);
    if (fin == texto || *fin != '\0' || errno != 0 || valor <= 0) {
        return 0;
    }
    *salida = valor;
    return 1;
}

static int parsear_numero(const char *texto, double *salida) {
    char *fin;
    errno = 0;
    double valor = strtod(texto, &fin);
    if (fin == texto || *fin != '\0' || errno != 0 || !isfinite(valor)) {
        return 0;
    }
    *salida = valor;
    return 1;
}

/* Letras, digitos, '_' y '-', maximo TAM_ID - 1 caracteres (TIPO_ALERTA). */
static int identificador_valido(const char *texto) {
    size_t largo = strlen(texto);
    if (largo == 0 || largo >= TAM_ID) {
        return 0;
    }
    for (size_t i = 0; i < largo; i++) {
        if (!isalnum((unsigned char)texto[i]) && texto[i] != '_' && texto[i] != '-') {
            return 0;
        }
    }
    return 1;
}

/* Catalogo de variables y su rango valido. Retorna 0 si no existe. */
static int rango_variable(const char *variable, double *minimo, double *maximo) {
    if (strcmp(variable, "TEMP") == 0) {
        *minimo = -50.0; *maximo = 80.0;
    } else if (strcmp(variable, "HUMD") == 0) {
        *minimo = 0.0; *maximo = 100.0;
    } else if (strcmp(variable, "ELEC") == 0) {
        *minimo = 0.0; *maximo = INFINITY;
    } else {
        return 0;
    }
    return 1;
}

// ---------- UDP: DATA y ALERT ----------

/* Retorna 1 si escribio un ERROR en respuesta, 0 si el DATA fue valido. */
static int procesar_data(char *campos[], int n, char *respuesta, size_t tam) {
    if (n != 6) {
        responder_error(respuesta, tam, ERR_FORMATO, "Estructura de campos incompleta o invalida");
        return 1;
    }

    const char *id = campos[1];
    const char *variable = campos[3];
    long secuencia, timestamp;
    double valor, minimo, maximo;

    if (!nodos_existe(id)) {
        responder_error(respuesta, tam, ERR_NODO, "El ID_NODO no se encuentra registrado");
        return 1;
    }
    if (!parsear_entero_positivo(campos[2], &secuencia)) {
        responder_error(respuesta, tam, ERR_SECUENCIA, "La secuencia debe ser un entero positivo");
        return 1;
    }
    if (!rango_variable(variable, &minimo, &maximo)) {
        responder_error(respuesta, tam, ERR_VARIABLE, "La variable enviada no pertenece al catalogo");
        return 1;
    }
    if (!parsear_numero(campos[4], &valor)) {
        responder_error(respuesta, tam, ERR_VALOR, "El valor numerico no es valido");
        return 1;
    }
    if (valor < minimo || valor > maximo) {
        responder_error(respuesta, tam, ERR_VALOR, "El valor numerico esta fuera de rango");
        return 1;
    }
    if (!parsear_entero_positivo(campos[5], &timestamp)) {
        responder_error(respuesta, tam, ERR_TIMESTAMP, "El timestamp no tiene formato Epoch valido");
        return 1;
    }

    int resultado = nodos_registrar_dato(id, variable, valor, timestamp, secuencia);
    if (resultado == -3) {
        responder_error(respuesta, tam, ERR_NODO, "El ID_NODO no se encuentra registrado");
        return 1;
    }
    if (resultado != 0) {
        responder_error(respuesta, tam, ERR_VARIABLE, "La variable enviada no pertenece al catalogo");
        return 1;
    }
    printf("[DATA] %s seq=%ld %s=%.2f\n", id, secuencia, variable, valor);

    /* El servidor tambien detecta anomalias por su cuenta. */
    char codigo[32];
    if (alertas_evaluar_umbral(variable, valor, codigo, sizeof(codigo))) {
        alertas_registrar(id, codigo, valor, timestamp);
        printf("[ALERTA] %s %s=%.2f\n", id, codigo, valor);
    }
    return 0;
}

static int procesar_alert(char *campos[], int n, char *respuesta, size_t tam) {
    if (n != 5) {
        responder_error(respuesta, tam, ERR_FORMATO, "Estructura de campos incompleta o invalida");
        return 1;
    }

    const char *id = campos[1];
    const char *tipo = campos[2];
    long timestamp;
    double valor;

    if (!nodos_existe(id)) {
        responder_error(respuesta, tam, ERR_NODO, "El ID_NODO no se encuentra registrado");
        return 1;
    }
    if (!identificador_valido(tipo)) {
        responder_error(respuesta, tam, ERR_FORMATO, "TIPO_ALERTA vacio o invalido");
        return 1;
    }
    if (!parsear_numero(campos[3], &valor)) {
        responder_error(respuesta, tam, ERR_VALOR, "El valor numerico no es valido");
        return 1;
    }
    if (!parsear_entero_positivo(campos[4], &timestamp)) {
        responder_error(respuesta, tam, ERR_TIMESTAMP, "El timestamp no tiene formato Epoch valido");
        return 1;
    }

    alertas_registrar(id, tipo, valor, timestamp);
    printf("[ALERTA] %s %s=%.2f (reportada por el nodo)\n", id, tipo, valor);
    return 0;
}

int protocolo_procesar_udp(const char *datagrama, size_t len,
                           char *respuesta, size_t tam_respuesta) {
    char linea[TAM_DATAGRAMA + 1];
    char *campos[MAX_CAMPOS];

    if (len == 0 || len > TAM_DATAGRAMA || memchr(datagrama, '\0', len) != NULL) {
        responder_error(respuesta, tam_respuesta, ERR_FORMATO, "Datagrama vacio, muy largo o con bytes nulos");
        return 1;
    }
    /* El protocolo exige que cada trama termine en salto de linea. */
    if (datagrama[len - 1] != '\n') {
        responder_error(respuesta, tam_respuesta, ERR_FORMATO, "La trama debe terminar con salto de linea");
        return 1;
    }

    memcpy(linea, datagrama, len - 1);
    linea[len - 1] = '\0';
    if (len >= 2 && linea[len - 2] == '\r') {
        linea[len - 2] = '\0';
    }

    int n = dividir_campos(linea, campos, MAX_CAMPOS);

    if (campos[0][0] == '\0') {
        responder_error(respuesta, tam_respuesta, ERR_FORMATO, "Tipo de mensaje inexistente");
        return 1;
    }
    if (strcmp(campos[0], "DATA") == 0) {
        return procesar_data(campos, n, respuesta, tam_respuesta);
    }
    if (strcmp(campos[0], "ALERT") == 0) {
        return procesar_alert(campos, n, respuesta, tam_respuesta);
    }
    responder_error(respuesta, tam_respuesta, ERR_FORMATO, "Tipo de mensaje no soportado por UDP");
    return 1;
}

// ---------- TCP: comandos del operador ----------

/* Agrega ",VAR:VALOR" por cada variable que el nodo ya ha reportado. */
static void anexar_variables(char *respuesta, size_t tam, const Nodo *nodo, char separador) {
    for (int v = 0; v < NUM_VARIABLES; v++) {
        if (nodo->tiene_valor[v]) {
            char valor_txt[352];
            formatear_valor(nodo->valores[v], valor_txt, sizeof(valor_txt));
            anexar(respuesta, tam, "%c%s:%s", separador, nodos_nombre_variable(v), valor_txt);
        }
    }
}

/* NODES_RESP|<total>|NODE01:ONLINE,NODE02:OFFLINE,... */
static void cmd_list_nodes(char *respuesta, size_t tam) {
    Nodo nodos[MAX_NODOS];
    int n = nodos_copiar_todos(nodos, MAX_NODOS);
    time_t ahora = time(NULL);

    snprintf(respuesta, tam, "NODES_RESP|%d|", n);
    for (int i = 0; i < n; i++) {
        anexar(respuesta, tam, "%s%s:%s", i > 0 ? "," : "", nodos[i].id,
               nodos_esta_activo(&nodos[i], ahora) ? "ONLINE" : "OFFLINE");
    }
    anexar(respuesta, tam, "\n");
}

/* STATUS_RESP|ID|ONLINE|TIMESTAMP|TEMP:VAL|HUMD:VAL|ELEC:VAL */
static void cmd_get_status(const char *id, char *respuesta, size_t tam) {
    Nodo nodo;
    if (!nodos_obtener(id, &nodo)) {
        responder_error(respuesta, tam, ERR_NODO, "El ID_NODO no se encuentra registrado");
        return;
    }
    snprintf(respuesta, tam, "STATUS_RESP|%s|%s|%ld", nodo.id,
             nodos_esta_activo(&nodo, time(NULL)) ? "ONLINE" : "OFFLINE", nodo.timestamp);
    anexar_variables(respuesta, tam, &nodo, '|');
    anexar(respuesta, tam, "\n");
}

/* MEASUREMENTS_RESP|<n>|ID,TIMESTAMP,TEMP:VAL,HUMD:VAL,ELEC:VAL;ID,... */
static void cmd_get_measurements(char *respuesta, size_t tam) {
    Nodo nodos[MAX_NODOS];
    int n = nodos_copiar_todos(nodos, MAX_NODOS);

    snprintf(respuesta, tam, "MEASUREMENTS_RESP|%d|", n);
    for (int i = 0; i < n; i++) {
        anexar(respuesta, tam, "%s%s,%ld", i > 0 ? ";" : "", nodos[i].id, nodos[i].timestamp);
        anexar_variables(respuesta, tam, &nodos[i], ',');
    }
    anexar(respuesta, tam, "\n");
}

/* ALERTS_RESP|<n>|ID,CODIGO,VALOR,TS;... (de la mas reciente a la mas antigua) */
static void cmd_get_alerts(char *respuesta, size_t tam) {
    Alerta alertas[ALERTAS_EN_CONSULTA];
    int n = alertas_recientes(alertas, ALERTAS_EN_CONSULTA);

    snprintf(respuesta, tam, "ALERTS_RESP|%d|", n);
    for (int i = 0; i < n; i++) {
        char valor_txt[352];
        formatear_valor(alertas[i].valor, valor_txt, sizeof(valor_txt));
        anexar(respuesta, tam, "%s%s,%s,%s,%ld", i > 0 ? ";" : "",
               alertas[i].id_nodo, alertas[i].codigo, valor_txt, alertas[i].timestamp);
    }
    anexar(respuesta, tam, "\n");
}

/* SYSTEM_STATUS_RESP|UPTIME=s|NODES_REGISTERED=n|NODES_ACTIVE=n|ALERTS=n|DATA_RECEIVED=n|DATA_LOST=n */
static void cmd_get_system_status(char *respuesta, size_t tam) {
    int registrados, activos;
    long recibidos, perdidos;
    nodos_estadisticas(&registrados, &activos, &recibidos, &perdidos);

    snprintf(respuesta, tam,
             "SYSTEM_STATUS_RESP|UPTIME=%ld|NODES_REGISTERED=%d|NODES_ACTIVE=%d|"
             "ALERTS=%d|DATA_RECEIVED=%ld|DATA_LOST=%ld\n",
             (long)(time(NULL) - hora_inicio), registrados, activos,
             alertas_total(), recibidos, perdidos);
}

void protocolo_procesar_tcp(const char *linea, char *respuesta, size_t tam_respuesta) {
    char copia[TAM_LINEA];
    char *campos[MAX_CAMPOS];

    snprintf(copia, sizeof(copia), "%s", linea);
    int n = dividir_campos(copia, campos, MAX_CAMPOS);
    const char *comando = campos[0];

    if (strcmp(comando, "GET_STATUS") == 0) {
        if (n != 2) {
            responder_error(respuesta, tam_respuesta, ERR_FORMATO, "Uso: GET_STATUS|ID_NODO");
            return;
        }
        cmd_get_status(campos[1], respuesta, tam_respuesta);
        return;
    }

    int sin_parametros = strcmp(comando, "LIST_NODES") == 0 ||
                         strcmp(comando, "GET_MEASUREMENTS") == 0 ||
                         strcmp(comando, "GET_ALERTS") == 0 ||
                         strcmp(comando, "GET_SYSTEM_STATUS") == 0;
    if (!sin_parametros) {
        responder_error(respuesta, tam_respuesta, ERR_FORMATO, "Tipo de mensaje desconocido");
        return;
    }
    if (n != 1) {
        responder_error(respuesta, tam_respuesta, ERR_FORMATO, "Este comando no recibe parametros");
        return;
    }

    if (strcmp(comando, "LIST_NODES") == 0) {
        cmd_list_nodes(respuesta, tam_respuesta);
    } else if (strcmp(comando, "GET_MEASUREMENTS") == 0) {
        cmd_get_measurements(respuesta, tam_respuesta);
    } else if (strcmp(comando, "GET_ALERTS") == 0) {
        cmd_get_alerts(respuesta, tam_respuesta);
    } else {
        cmd_get_system_status(respuesta, tam_respuesta);
    }
}
