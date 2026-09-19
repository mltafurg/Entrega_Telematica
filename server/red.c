/* red.c - Sockets TCP (operadores) y UDP (nodos) del servidor */

#include <arpa/inet.h>
#include <errno.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>
#include "config.h"
#include "protocolo.h"
#include "red.h"

volatile sig_atomic_t servidor_detenido = 0;

typedef struct {
    int socket;
    struct sockaddr_in direccion;
} ClienteTcp;

// ---------- TCP ----------

/* send() puede enviar menos de lo pedido. Retorna 0 si envio todo, -1 si fallo. */
static int enviar_completo(int socket, const char *datos, size_t largo) {
    size_t enviados = 0;
    while (enviados < largo) {
        ssize_t n = send(socket, datos + enviados, largo - enviados, MSG_NOSIGNAL);
        if (n < 0) {
            if (errno == EINTR) {
                continue;
            }
            return -1;
        }
        enviados += n;
    }
    return 0;
}

/* Un hilo por operador. TCP es un flujo de bytes: un recv puede traer varios
 * comandos o solo la mitad de uno, asi que se acumula hasta encontrar '\n'. */
static void *atender_cliente(void *arg) {
    ClienteTcp cliente = *(ClienteTcp *)arg;
    free(arg);

    char ip[INET_ADDRSTRLEN];
    inet_ntop(AF_INET, &cliente.direccion.sin_addr, ip, sizeof(ip));
    int puerto = ntohs(cliente.direccion.sin_port);

    char acumulado[TAM_LINEA];
    size_t usado = 0;
    int continuar = 1;

    while (continuar) {
        ssize_t n = recv(cliente.socket, acumulado + usado, sizeof(acumulado) - usado, 0);
        if (n < 0) {
            if (errno == EINTR) {
                continue;
            }
            perror("[TCP] Error en recv");
            break;
        }
        if (n == 0) {
            printf("[TCP] Operador %s:%d cerro la conexion\n", ip, puerto);
            break;
        }
        usado += n;

        char *fin_linea;
        while ((fin_linea = memchr(acumulado, '\n', usado)) != NULL) {
            size_t largo = fin_linea - acumulado;
            acumulado[largo] = '\0';
            if (largo > 0 && acumulado[largo - 1] == '\r') {
                acumulado[largo - 1] = '\0';
            }

            if (acumulado[0] != '\0') {
                char respuesta[TAM_RESPUESTA];
                printf("[TCP] %s:%d -> \"%s\"\n", ip, puerto, acumulado);
                protocolo_procesar_tcp(acumulado, respuesta, sizeof(respuesta));
                if (enviar_completo(cliente.socket, respuesta, strlen(respuesta)) < 0) {
                    perror("[TCP] Error en send");
                    continuar = 0;
                    break;
                }
            }

            usado -= largo + 1;
            memmove(acumulado, fin_linea + 1, usado);
        }

        /* Buffer lleno y sin '\n': linea demasiado larga, se corta la conexion. */
        if (continuar && usado == sizeof(acumulado)) {
            const char *error = "ERROR|" ERR_FORMATO "|Linea demasiado larga\n";
            enviar_completo(cliente.socket, error, strlen(error));
            printf("[TCP] %s:%d envio una linea demasiado larga, se cierra\n", ip, puerto);
            break;
        }
    }

    close(cliente.socket);
    return NULL;
}

int red_abrir_tcp(int puerto) {
    int socket_escucha = socket(AF_INET, SOCK_STREAM, 0);
    if (socket_escucha < 0) {
        perror("Error al crear el socket TCP");
        return -1;
    }

    int opcion = 1;
    if (setsockopt(socket_escucha, SOL_SOCKET, SO_REUSEADDR, &opcion, sizeof(opcion)) < 0) {
        perror("Error en setsockopt");
        close(socket_escucha);
        return -1;
    }

    struct sockaddr_in direccion;
    memset(&direccion, 0, sizeof(direccion));
    direccion.sin_family = AF_INET;
    direccion.sin_addr.s_addr = INADDR_ANY;
    direccion.sin_port = htons(puerto);

    if (bind(socket_escucha, (struct sockaddr *)&direccion, sizeof(direccion)) < 0) {
        perror("Error en bind TCP");
        close(socket_escucha);
        return -1;
    }
    if (listen(socket_escucha, BACKLOG) < 0) {
        perror("Error en listen");
        close(socket_escucha);
        return -1;
    }
    printf("[OK] TCP escuchando en el puerto %d (operadores)\n", puerto);
    return socket_escucha;
}

void red_atender_tcp(int socket_escucha) {
    while (!servidor_detenido) {
        ClienteTcp *cliente = malloc(sizeof(ClienteTcp));
        if (cliente == NULL) {
            perror("Error en malloc");
            sleep(1);
            continue;
        }

        socklen_t tam_direccion = sizeof(cliente->direccion);
        cliente->socket = accept(socket_escucha, (struct sockaddr *)&cliente->direccion, &tam_direccion);
        if (cliente->socket < 0) {
            if (errno != EINTR) {
                perror("Error en accept");
            }
            free(cliente);
            continue;
        }

        char ip[INET_ADDRSTRLEN];
        inet_ntop(AF_INET, &cliente->direccion.sin_addr, ip, sizeof(ip));
        printf("[TCP] Operador conectado desde %s:%d\n", ip, ntohs(cliente->direccion.sin_port));

        pthread_t hilo;
        if (pthread_create(&hilo, NULL, atender_cliente, cliente) != 0) {
            perror("Error al crear el hilo");
            close(cliente->socket);
            free(cliente);
            continue;
        }
        pthread_detach(hilo);
    }
}

// ---------- UDP ----------

/* UDP no tiene conexiones: un solo hilo recibe los datagramas de todos los nodos. */
static void *recibir_telemetria(void *arg) {
    int socket_udp = *(int *)arg;
    free(arg);

    char datagrama[TAM_DATAGRAMA + 1];
    while (!servidor_detenido) {
        struct sockaddr_in origen;
        socklen_t tam_origen = sizeof(origen);

        ssize_t n = recvfrom(socket_udp, datagrama, sizeof(datagrama) - 1, 0,
                             (struct sockaddr *)&origen, &tam_origen);
        if (n < 0) {
            if (errno != EINTR) {
                perror("[UDP] Error en recvfrom");
            }
            continue;
        }

        char respuesta[TAM_RESPUESTA];
        if (protocolo_procesar_udp(datagrama, n, respuesta, sizeof(respuesta))) {
            char ip[INET_ADDRSTRLEN];
            inet_ntop(AF_INET, &origen.sin_addr, ip, sizeof(ip));
            printf("[UDP] Trama invalida de %s:%d -> %s", ip, ntohs(origen.sin_port), respuesta);

            if (sendto(socket_udp, respuesta, strlen(respuesta), 0,
                       (struct sockaddr *)&origen, tam_origen) < 0) {
                perror("[UDP] Error en sendto");
            }
        }
    }

    close(socket_udp);
    return NULL;
}

int red_iniciar_udp(int puerto) {
    int socket_udp = socket(AF_INET, SOCK_DGRAM, 0);
    if (socket_udp < 0) {
        perror("Error al crear el socket UDP");
        return -1;
    }

    struct sockaddr_in direccion;
    memset(&direccion, 0, sizeof(direccion));
    direccion.sin_family = AF_INET;
    direccion.sin_addr.s_addr = INADDR_ANY;
    direccion.sin_port = htons(puerto);

    if (bind(socket_udp, (struct sockaddr *)&direccion, sizeof(direccion)) < 0) {
        perror("Error en bind UDP");
        close(socket_udp);
        return -1;
    }

    int *arg = malloc(sizeof(int));
    if (arg == NULL) {
        perror("Error en malloc");
        close(socket_udp);
        return -1;
    }
    *arg = socket_udp;

    pthread_t hilo;
    if (pthread_create(&hilo, NULL, recibir_telemetria, arg) != 0) {
        perror("Error al crear el hilo UDP");
        free(arg);
        close(socket_udp);
        return -1;
    }
    pthread_detach(hilo);

    printf("[OK] UDP escuchando en el puerto %d (telemetria de los nodos)\n", puerto);
    return 0;
}
