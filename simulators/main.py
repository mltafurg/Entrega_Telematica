import os
import random
import time
import threading
from nodeSimulator import NodeClient


SERVER_HOST = os.getenv("SERVER_HOST", "localhost")
SERVER_PORT = int(os.getenv("SERVER_PORT", "5000"))

# Se usa solo para una prueba controlada de pérdida UDP.
# Para funcionamiento normal déjalo en 0.
SIMULATED_LOSS_PROBABILITY = float(os.getenv("SIMULATED_LOSS_PROBABILITY", "0"))

NODE_IDS = ["NODE01", "NODE02", "NODE03", "NODE04", "NODE05"]


def run_node(node_id):
    node = NodeClient(
        node_id=node_id,
        server_host=SERVER_HOST,
        server_port=SERVER_PORT,
        simulated_loss_probability=SIMULATED_LOSS_PROBABILITY,
    )

    interval = random.randint(2, 4)
    node.run(interval_seconds=interval)


if __name__ == "__main__":
    threads = []

    print("=== Red de simuladores IoT ===")
    print(f"Servidor: {SERVER_HOST}:{SERVER_PORT}")
    print(f"Nodos simultáneos: {len(NODE_IDS)}")
    print(
        f"Pérdida UDP simulada: "
        f"{SIMULATED_LOSS_PROBABILITY * 100:.1f}%"
    )
    print("Presiona Ctrl + C para detener todos los nodos.\n")

    for node_id in NODE_IDS:
        thread = threading.Thread(
            target=run_node,
            args=(node_id,),
            daemon=True,
        )
        threads.append(thread)
        thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nDeteniendo todos los nodos simuladores...")