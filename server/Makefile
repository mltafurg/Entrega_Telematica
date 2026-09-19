CC = gcc
CFLAGS = -Wall -Wextra -pthread
SRC = main.c red.c protocolo.c nodos.c alertas.c
HDR = config.h red.h protocolo.h nodos.h alertas.h

servidor: $(SRC) $(HDR)
	$(CC) $(CFLAGS) -o servidor $(SRC) -lm

clean:
	rm -f servidor

.PHONY: clean
