/* main.c - Servidor central de telemetria
 *
 * Concurrencia: el hilo principal acepta operadores TCP y crea un hilo por cada
 * uno; un hilo aparte recibe la telemetria UDP de todos los nodos.
 */

#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include "config.h"
#include "nodos.h"
#include "protocolo.h"
#include "red.h"

static void manejar_senal(int senal) {
    (void)senal;
    servidor_detenido = 1;
}

/* Lee un puerto de una variable de entorno; si no existe o es invalido usa el defecto. */
static int puerto_desde_entorno(const char *nombre, int defecto) {
    const char *texto = getenv(nombre);
    if (texto == NULL) {
        return defecto;
    }
    int puerto = atoi(texto);
    return (puerto > 0 && puerto < 65536) ? puerto : defecto;
}

int main(void) {
    int puerto_tcp = puerto_desde_entorno("PUERTO_TCP", PUERTO_TCP_DEFECTO);
    int puerto_udp = puerto_desde_entorno("PUERTO_UDP", PUERTO_UDP_DEFECTO);

    /* Sin SA_RESTART para que accept/recv se interrumpan y se vea la bandera. */
    struct sigaction accion = {0};
    accion.sa_handler = manejar_senal;
    sigaction(SIGINT, &accion, NULL);
    sigaction(SIGTERM, &accion, NULL);
    signal(SIGPIPE, SIG_IGN);

    protocolo_iniciar();

    const char *lista_nodos = getenv("NODOS_REGISTRADOS");
    int registrados = nodos_registrar_lista(lista_nodos != NULL ? lista_nodos : NODOS_REGISTRADOS_DEFECTO);
    printf("[OK] %d nodos registrados\n", registrados);

    int socket_tcp = red_abrir_tcp(puerto_tcp);
    if (socket_tcp < 0) {
        return EXIT_FAILURE;
    }
    if (red_iniciar_udp(puerto_udp) < 0) {
        close(socket_tcp);
        return EXIT_FAILURE;
    }

    printf(">>> Servidor listo (Ctrl+C para detener)\n");
    red_atender_tcp(socket_tcp);

    printf("\n>>> Cerrando servidor\n");
    close(socket_tcp);
    return EXIT_SUCCESS;
}
