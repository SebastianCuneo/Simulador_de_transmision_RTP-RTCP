"""
Visualización en tiempo real de métricas RTCP del servidor.

Lee el archivo CSV `rtcp_server_log.csv` generado por `servidor_rtp_rtcp.py`
y grafica:
    - Retardo (ms)
    - Jitter (s)
    - Pérdida (loss rate %)

Uso:
    1) Ejecutar primero el servidor RTP/RTCP para que vaya llenando el CSV.
    2) En otra terminal, ejecutar:

        python -m src.visualizador_metricas
"""

import csv
import os
import time
from typing import List, Tuple

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

RTCP_LOG_FILE = "rtcp_server_log.csv"


def leer_metricas_desde_csv() -> Tuple[List[float], List[float], List[float], List[float]]:
    """
    Lee el archivo CSV y devuelve listas con:
        tiempos_rel, delay_ms, jitter_s, loss_pct
    """
    if not os.path.exists(RTCP_LOG_FILE):
        return [], [], [], []

    tiempos: List[float] = []
    delay_ms: List[float] = []
    jitter_s: List[float] = []
    loss_pct: List[float] = []

    with open(RTCP_LOG_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            t = float(row["timestamp_local"])
            d = float(row["delay_ms"])
            j = float(row["jitter_s"])
            loss = float(row["loss_rate"]) * 100.0

            tiempos.append(t)
            delay_ms.append(d)
            jitter_s.append(j)
            loss_pct.append(loss)

    if not tiempos:
        return [], [], [], []

    t0 = tiempos[0]
    tiempos_rel = [t - t0 for t in tiempos]
    return tiempos_rel, delay_ms, jitter_s, loss_pct


def iniciar_grafico(interval_ms: int = 500) -> None:
    """Crea una ventana de matplotlib y actualiza las gráficas en tiempo real."""
    plt.style.use("seaborn-v0_8")
    fig, (ax_delay, ax_jitter, ax_loss) = plt.subplots(3, 1, figsize=(8, 8), sharex=True)
    fig.suptitle("Métricas RTP/RTCP en tiempo real")

    line_delay, = ax_delay.plot([], [], label="Retardo (ms)", color="tab:blue")
    line_jitter, = ax_jitter.plot([], [], label="Jitter (s)", color="tab:orange")
    line_loss, = ax_loss.plot([], [], label="Pérdida (%)", color="tab:red")

    for ax, ylabel in (
        (ax_delay, "Retardo [ms]"),
        (ax_jitter, "Jitter [s]"),
        (ax_loss, "Pérdida [%]"),
    ):
        ax.set_ylabel(ylabel)
        ax.grid(True, linestyle="--", alpha=0.3)
        ax.legend(loc="upper right")

    ax_loss.set_xlabel("Tiempo desde inicio [s]")

    def actualizar(_frame):
        tiempos, delay_ms, jitter_s, loss_pct = leer_metricas_desde_csv()
        if not tiempos:
            return line_delay, line_jitter, line_loss

        line_delay.set_data(tiempos, delay_ms)
        line_jitter.set_data(tiempos, jitter_s)
        line_loss.set_data(tiempos, loss_pct)

        ax_delay.relim()
        ax_delay.autoscale_view()
        ax_jitter.relim()
        ax_jitter.autoscale_view()
        ax_loss.relim()
        ax_loss.autoscale_view()

        fig.tight_layout()
        return line_delay, line_jitter, line_loss

    # Animación: llama a `actualizar` cada `interval_ms` milisegundos
    FuncAnimation(fig, actualizar, interval=interval_ms, blit=False)
    plt.show()


if __name__ == "__main__":
    if not os.path.exists(RTCP_LOG_FILE):
        print(f"[VISUALIZADOR] No se encontró '{RTCP_LOG_FILE}'. "
              "Ejecuta primero el servidor RTP/RTCP para generar el archivo.")
        # Espera unos segundos por si el archivo aparece luego
        print("[VISUALIZADOR] Esperando a que se creen métricas...")
        while not os.path.exists(RTCP_LOG_FILE):
            time.sleep(1)

    iniciar_grafico()


