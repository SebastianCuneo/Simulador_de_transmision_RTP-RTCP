# servidor_rtp_rtcp.py
import socket
import threading
import time
import struct
from utils.rtp_packet import RTPPacket
from utils.rtcp_packet import RTCPSenderReport

RTP_PORT = 5005
RTCP_PORT = 5006

# Archivo donde se registrarán las métricas RTCP del servidor
RTCP_LOG_FILE = "rtcp_server_log.csv"

# Variables compartidas (métricas)
lock = threading.Lock()
ult_seq = 0
paquetes_recibidos = 0
paquetes_perdidos = 0
jitter = 0.0
ultimo_ts = None
ultimo_tiempo_llegada = None  # Para calcular jitter correctamente

# Historial de métricas recibidas por RTCP (en memoria)
rtcp_metrics_history = []


# ==============================================================
#   HILO: RECEPCIÓN DE RTP
# ==============================================================
def manejar_rtp():
    global ult_seq, paquetes_recibidos, paquetes_perdidos, jitter, ultimo_ts, ultimo_tiempo_llegada

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", RTP_PORT))
    print(f"[SERVIDOR] Escuchando RTP en puerto {RTP_PORT}")

    while True:
        data, addr = sock.recvfrom(4096)
        tiempo_llegada = time.time()

        # Decodificar paquete RTP usando struct
        rtp_packet = RTPPacket.decode(data)

        if rtp_packet is None:
            print("[RTP] Paquete malformado o versión incorrecta")
            continue

        seq = rtp_packet.sequence_number
        ts = rtp_packet.timestamp
        payload = rtp_packet.payload.decode(errors='replace')

        with lock:
            paquetes_recibidos += 1
            # Detección de pérdidas
            if ult_seq > 0:  # Ignorar el primer paquete
                esperado = ult_seq + 1
                if seq != esperado:
                    perdidos = seq - esperado
                    if perdidos > 0:
                        paquetes_perdidos += perdidos
                        print(f"[RTP] ¡Pérdida detectada! Esperado {esperado}, recibido {seq}")

            # Cálculo de jitter (RFC 3550)
            # J(i) = J(i-1) + (|D(i-1,i)| - J(i-1))/16
            if ultimo_ts is not None and ultimo_tiempo_llegada is not None:
                # Diferencia de tiempos de llegada y timestamps
                D = (tiempo_llegada - ultimo_tiempo_llegada) - \
                    ((ts - ultimo_ts) / 90000.0)  # Convertir de 90kHz a segundos
                jitter += (abs(D) - jitter) / 16.0

            ultimo_ts = ts
            ultimo_tiempo_llegada = tiempo_llegada
            ult_seq = seq

        print(f"[RTP] Recibido {rtp_packet} payload='{payload}' desde {addr}")

        # Enviar ACK
        ack = f"ACK_RTP,{seq}".encode()
        sock.sendto(ack, addr)



# ==============================================================
#   HILO: RECEPCIÓN DE RTCP
# ==============================================================
def manejar_rtcp():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", RTCP_PORT))
    print(f"[SERVIDOR] Escuchando RTCP en puerto {RTCP_PORT}")

    # Inicializar archivo de log (si no existe, escribir cabecera)
    try:
        with open(RTCP_LOG_FILE, "x", encoding="utf-8") as f:
            f.write("timestamp_local,ssrc,rtp_timestamp,paquetes_enviados,"
                    "paquetes_recibidos,paquetes_perdidos,loss_rate,jitter_s,delay_ms\n")
    except FileExistsError:
        # Ya existe, no hacer nada
        pass

    NTP_DELTA = 2208988800  # Diferencia entre época NTP y Unix

    while True:
        data, addr = sock.recvfrom(4096)
        now = time.time()

        # Decodificar RTCP Sender Report usando struct
        sr = RTCPSenderReport.decode(data)

        if sr is None:
            print("[RTCP] Paquete RTCP malformado o tipo incorrecto")
            continue

        # Calcular retardo (one-way delay aproximado) a partir del timestamp NTP
        ntp_sec, ntp_frac = sr.ntp_timestamp
        ntp_time = ntp_sec + ntp_frac / (2**32)
        unix_time_sender = ntp_time - NTP_DELTA
        delay_ms = (now - unix_time_sender) * 1000.0

        with lock:
            enviados = sr.packet_count
            recibidos_local = paquetes_recibidos
            perdidos_estimados = max(0, enviados - recibidos_local)
            loss_rate = (perdidos_estimados / enviados) if enviados > 0 else 0.0
            jitter_val = jitter

            # Guardar en estructura en memoria
            metrics = {
                "timestamp_local": now,
                "ssrc": sr.ssrc,
                "rtp_timestamp": sr.rtp_timestamp,
                "paquetes_enviados": enviados,
                "paquetes_recibidos": recibidos_local,
                "paquetes_perdidos": perdidos_estimados,
                "loss_rate": loss_rate,
                "jitter_s": jitter_val,
                "delay_ms": delay_ms,
            }
            rtcp_metrics_history.append(metrics)

        # Escribir en archivo de log
        with open(RTCP_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{now:.3f},{sr.ssrc:08x},{sr.rtp_timestamp},"
                    f"{enviados},{recibidos_local},{perdidos_estimados},"
                    f"{loss_rate:.6f},{jitter_val:.6f},{delay_ms:.3f}\n")

        # Mostrar métricas por consola
        print(f"[RTCP] Reporte desde {addr}: {sr}")
        print(f"[RTCP-METRICAS] delay={delay_ms:.2f} ms | jitter={jitter_val:.6f} s | "
              f"enviados={enviados} | recibidos={recibidos_local} | "
              f"perdidos={perdidos_estimados} ({loss_rate*100:.2f}%)")


# Lanzar hilos
t1 = threading.Thread(target=manejar_rtp)
t2 = threading.Thread(target=manejar_rtcp)

t1.start()
t2.start()
