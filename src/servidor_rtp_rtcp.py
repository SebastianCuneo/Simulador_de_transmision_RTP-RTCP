# servidor_rtp_rtcp.py
import socket
import threading
import time
import struct
from utils.rtp_packet import RTPPacket
from utils.rtcp_packet import RTCPSenderReport

RTP_PORT = 5005
RTCP_PORT = 5006

# Variables compartidas (métricas)
lock = threading.Lock()
ult_seq = 0
paquetes_perdidos = 0
jitter = 0.0
ultimo_ts = None
ultimo_tiempo_llegada = None  # Para calcular jitter correctamente


# ==============================================================
#   HILO: RECEPCIÓN DE RTP
# ==============================================================
def manejar_rtp():
    global ult_seq, paquetes_perdidos, jitter, ultimo_ts, ultimo_tiempo_llegada

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

    while True:
        data, addr = sock.recvfrom(4096)

        # Decodificar RTCP Sender Report usando struct
        sr = RTCPSenderReport.decode(data)

        if sr is None:
            print("[RTCP] Paquete RTCP malformado o tipo incorrecto")
            continue

        print(f"[RTCP] Recibido desde {addr}: {sr}")

        with lock:
            print(f"[METRICAS] ult_seq={ult_seq} | perdidos={paquetes_perdidos} | jitter={jitter:.6f}s")


# Lanzar hilos
t1 = threading.Thread(target=manejar_rtp)
t2 = threading.Thread(target=manejar_rtcp)

t1.start()
t2.start()
