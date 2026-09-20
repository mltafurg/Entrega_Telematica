"""
Cliente operador (interfaz gráfica) — parte de la entrega de Oriana.

Ventana con pestañas que consultan al servidor central (server/, en C)
por TCP: nodos activos, últimas mediciones, un nodo específico,
alertas recientes y estado general de la red. Usa Tkinter (viene con
Python, no hay que instalar nada aparte) y el mismo protocolo que ya
usa el servicio web.

Uso:
    python operator_gui.py

Variables de entorno (mismo patrón que simulators/main.py):
    SERVER_HOST, SERVER_PORT   -> dónde está el servidor (default localhost:5000)
"""

import os
import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

import tcp_client

SERVER_HOST = os.getenv("SERVER_HOST", "localhost")
SERVER_PORT = int(os.getenv("SERVER_PORT", "5000"))

REFRESH_MS = 4000  # auto-actualizar cada 4s cuando está activado


def fmt_time(ts):
    if ts is None:
        return "—"
    return datetime.fromtimestamp(ts).strftime("%H:%M:%S")


class OperatorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Cliente operador — Telemetría")
        self.geometry("780x520")
        self.minsize(680, 460)

        self._auto_refresh_job = None
        self._build_layout()
        self.refresh_all()

    # ---------- Construcción de la interfaz ----------

    def _build_layout(self):
        top = ttk.Frame(self, padding=(12, 10))
        top.pack(fill="x")

        self.status_var = tk.StringVar(value="Conectando...")
        ttk.Label(top, textvariable=self.status_var, font=("TkDefaultFont", 10, "bold")).pack(side="left")

        ttk.Label(top, text=f"  ·  Servidor: {SERVER_HOST}:{SERVER_PORT}").pack(side="left")

        self.auto_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            top, text="Auto-actualizar", variable=self.auto_var, command=self._toggle_auto_refresh
        ).pack(side="right")
        ttk.Button(top, text="Actualizar ahora", command=self.refresh_all).pack(side="right", padx=(0, 10))

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self._build_tab_nodos()
        self._build_tab_mediciones()
        self._build_tab_consulta()
        self._build_tab_alertas()
        self._build_tab_sistema()

    def _build_tab_nodos(self):
        frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(frame, text="Nodos activos")

        self.tree_nodos = ttk.Treeview(frame, columns=("estado",), show="tree headings", height=12)
        self.tree_nodos.heading("#0", text="Nodo")
        self.tree_nodos.heading("estado", text="Estado")
        self.tree_nodos.column("#0", width=200)
        self.tree_nodos.column("estado", width=120)
        self.tree_nodos.pack(fill="both", expand=True)

        self.nodos_resumen_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.nodos_resumen_var).pack(anchor="w", pady=(8, 0))

    def _build_tab_mediciones(self):
        frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(frame, text="Últimas mediciones")

        columns = ("hora", "temp", "humd", "elec")
        self.tree_med = ttk.Treeview(frame, columns=columns, show="tree headings", height=12)
        self.tree_med.heading("#0", text="Nodo")
        self.tree_med.heading("hora", text="Última lectura")
        self.tree_med.heading("temp", text="TEMP")
        self.tree_med.heading("humd", text="HUMD")
        self.tree_med.heading("elec", text="ELEC")
        for col, width in (("#0", 100), ("hora", 110), ("temp", 80), ("humd", 80), ("elec", 80)):
            self.tree_med.column(col, width=width, anchor="center" if col != "#0" else "w")
        self.tree_med.pack(fill="both", expand=True)

    def _build_tab_consulta(self):
        frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(frame, text="Consultar nodo")

        row = ttk.Frame(frame)
        row.pack(fill="x", pady=(0, 12))
        ttk.Label(row, text="ID del nodo:").pack(side="left")
        self.entry_nodo = ttk.Entry(row, width=20)
        self.entry_nodo.pack(side="left", padx=8)
        self.entry_nodo.insert(0, "NODE01")
        self.entry_nodo.bind("<Return>", lambda _event: self.consultar_nodo())
        # Selecciona todo el texto al hacer clic, para que escribir reemplace
        # el valor anterior en vez de concatenarse con él. "break" evita que
        # el binding por defecto del Entry (que ubica el cursor donde se hizo
        # clic) pise la seleccion que acabamos de hacer.
        self.entry_nodo.bind("<Button-1>", self._select_all_on_click)
        ttk.Button(row, text="Consultar", command=self.consultar_nodo).pack(side="left")

        self.consulta_result_var = tk.StringVar(value="Escribí un ID de nodo y presioná Consultar.")
        ttk.Label(frame, textvariable=self.consulta_result_var, justify="left", wraplength=680).pack(
            anchor="w", fill="x"
        )

    @staticmethod
    def _select_all_on_click(event):
        widget = event.widget
        widget.focus_set()
        widget.select_range(0, "end")
        widget.icursor("end")
        return "break"

    def _build_tab_alertas(self):
        frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(frame, text="Alertas")

        columns = ("tipo", "valor", "hora")
        self.tree_alertas = ttk.Treeview(frame, columns=columns, show="tree headings", height=12)
        self.tree_alertas.heading("#0", text="Nodo")
        self.tree_alertas.heading("tipo", text="Tipo")
        self.tree_alertas.heading("valor", text="Valor")
        self.tree_alertas.heading("hora", text="Hora")
        for col, width in (("#0", 100), ("tipo", 140), ("valor", 90), ("hora", 110)):
            self.tree_alertas.column(col, width=width, anchor="center" if col != "#0" else "w")
        self.tree_alertas.pack(fill="both", expand=True)

    def _build_tab_sistema(self):
        frame = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(frame, text="Estado general")

        self.sistema_vars = {}
        etiquetas = [
            ("UPTIME", "Uptime (s)"),
            ("NODES_REGISTERED", "Nodos registrados"),
            ("NODES_ACTIVE", "Nodos activos"),
            ("ALERTS", "Alertas totales"),
            ("DATA_RECEIVED", "Datos recibidos"),
            ("DATA_LOST", "Datos perdidos"),
        ]
        for i, (key, etiqueta) in enumerate(etiquetas):
            ttk.Label(frame, text=etiqueta + ":", font=("TkDefaultFont", 10, "bold")).grid(
                row=i, column=0, sticky="w", pady=4
            )
            var = tk.StringVar(value="—")
            self.sistema_vars[key] = var
            ttk.Label(frame, textvariable=var).grid(row=i, column=1, sticky="w", padx=12)

    # ---------- Actualización de datos ----------

    def _toggle_auto_refresh(self):
        if self.auto_var.get():
            self._schedule_auto_refresh()
        elif self._auto_refresh_job is not None:
            self.after_cancel(self._auto_refresh_job)
            self._auto_refresh_job = None

    def _schedule_auto_refresh(self):
        if self._auto_refresh_job is not None:
            self.after_cancel(self._auto_refresh_job)
        self._auto_refresh_job = self.after(REFRESH_MS, self._auto_refresh_tick)

    def _auto_refresh_tick(self):
        self.refresh_all()
        if self.auto_var.get():
            self._schedule_auto_refresh()

    def refresh_all(self):
        """Dispara la consulta en un hilo aparte para no congelar la ventana."""
        threading.Thread(target=self._fetch_and_update, daemon=True).start()

    def _fetch_and_update(self):
        commands = ["LIST_NODES", "GET_MEASUREMENTS", "GET_ALERTS", "GET_SYSTEM_STATUS"]
        try:
            responses = tcp_client.query(SERVER_HOST, SERVER_PORT, commands)
            nodes = tcp_client.parse_nodes_resp(responses[0])
            mediciones = tcp_client.parse_measurements_resp(responses[1])
            alertas = tcp_client.parse_alerts_resp(responses[2])
            sistema = tcp_client.parse_system_status_resp(responses[3])
            self.after(0, self._update_ui, nodes, mediciones, alertas, sistema, None)
        except tcp_client.ServerUnavailable as exc:
            self.after(0, self._update_ui, None, None, None, None, str(exc))

    def _update_ui(self, nodes, mediciones, alertas, sistema, error):
        if error is not None:
            self.status_var.set("Sin conexión")
            return
        self.status_var.set("En línea")

        self.tree_nodos.delete(*self.tree_nodos.get_children())
        for node_id, activo in nodes.items():
            self.tree_nodos.insert("", "end", text=node_id, values=("ONLINE" if activo else "OFFLINE",))
        activos = sum(1 for a in nodes.values() if a)
        self.nodos_resumen_var.set(f"{activos}/{len(nodes)} nodos activos")

        self.tree_med.delete(*self.tree_med.get_children())
        for node_id, info in mediciones.items():
            r = info["readings"]
            self.tree_med.insert(
                "",
                "end",
                text=node_id,
                values=(
                    fmt_time(info["timestamp"]),
                    r.get("TEMP", "—"),
                    r.get("HUMD", "—"),
                    r.get("ELEC", "—"),
                ),
            )

        self.tree_alertas.delete(*self.tree_alertas.get_children())
        for alerta in alertas:
            self.tree_alertas.insert(
                "",
                "end",
                text=alerta["node_id"],
                values=(alerta["code"], alerta["value"], fmt_time(alerta["timestamp"])),
            )

        for key, var in self.sistema_vars.items():
            var.set(sistema.get(key, "—"))

    def consultar_nodo(self):
        node_id = self.entry_nodo.get().strip()
        if not node_id:
            messagebox.showwarning("Cliente operador", "Escribí un ID de nodo.")
            return
        threading.Thread(target=self._fetch_nodo, args=(node_id,), daemon=True).start()

    def _fetch_nodo(self, node_id):
        try:
            responses = tcp_client.query(SERVER_HOST, SERVER_PORT, [f"GET_STATUS|{node_id}"])
            line = responses[0]
            if tcp_client.is_error(line):
                error = tcp_client.parse_error(line)
                texto = f"[{error['code']}] {error['description']}"
            else:
                status = tcp_client.parse_status_resp(line)
                valores = "  ".join(f"{k}={v}" for k, v in status["readings"].items()) or "sin lecturas"
                texto = (
                    f"{status['node_id']} — {status['status']}\n"
                    f"Última lectura: {fmt_time(status['timestamp'])}\n"
                    f"Valores: {valores}"
                )
            self.after(0, self.consulta_result_var.set, texto)
        except tcp_client.ServerUnavailable as exc:
            self.after(0, self.consulta_result_var.set, f"No se pudo conectar al servidor: {exc}")


if __name__ == "__main__":
    app = OperatorApp()
    app.mainloop()
