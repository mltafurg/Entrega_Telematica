# syntax=docker/dockerfile:1

# --- Etapa 1: compilacion -------------------------------------------------
# Imagen con gcc + make para compilar el servidor. No queda en la imagen final.
FROM debian:bookworm-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY . .
RUN make

# --- Etapa 2: imagen final -------------------------------------------------
# Solo el binario ya compilado + las librerias minimas para correrlo
# (libc y libm, que ya vienen en debian-slim). Sin gcc/make: imagen chica.
FROM debian:bookworm-slim

WORKDIR /app
COPY --from=builder /build/servidor .

# TCP (operadores) y UDP (telemetria de nodos). Mismo numero de puerto por
# defecto porque TCP y UDP son namespaces distintos (ver config.h).
EXPOSE 5000/tcp
EXPOSE 5000/udp

# Se pueden sobreescribir en el "docker run" con -e, por ejemplo:
#   docker run -e PUERTO_TCP=6000 -e PUERTO_UDP=6000 ...
ENV PUERTO_TCP=5000
ENV PUERTO_UDP=5000

ENTRYPOINT ["./servidor"]
