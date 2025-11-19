# servidor_rtp_rtcp.py
import socket
import threading
import time

RTP_PORT = 5005
RTCP_PORT = 5006

# Variables compartidas (métricas)
lock = threading.Lock()
ult_seq = 0
paquetes_perdidos = 0
jitter = 0
ultimo_ts = None


# ==============================================================
#   HILO: RECEPCIÓN DE RTP
# ==============================================================
def manejar_rtp():
    global ult_seq, paquetes_perdidos, jitter, ultimo_ts

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", RTP_PORT))
    print(f"[SERVIDOR] Escuchando RTP en puerto {RTP_PORT}")

    while True:
        data, addr = sock.recvfrom(4096)
        try:
            tipo, seq, ts = data.decode(errors="replace").split(",")
            seq = int(seq)
            ts = float(ts)
        except:
            print("[RTP] Paquete malformado")
            continue

        with lock:
            # detección de pérdidas
            if seq != ult_seq + 1:
                paquetes_perdidos += (seq - (ult_seq + 1))

            # cálculo de jitter
            if ultimo_ts is not None:
                jitter += abs((ts - ultimo_ts))

            ultimo_ts = ts
            ult_seq = seq

        print(f"[RTP] Recibido seq={seq} desde {addr}")
        ack = f"ACK_RTP,{seq}".encode()
        sock.sendto(ack, addr)



# ==============================================================
#   HILO: RECEPCIÓN DE RTCP
# ==============================================================
def manejar_rtcp():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", RTCP_PORT))
    print(f"[SERVIDOR] Escuchando RTCP en puerto {RTCP_PORT}")

    while True:
        data, addr = sock.recvfrom(4096)
        reporte = data.decode(errors='replace')

        print(f"[RTCP] Reporte recibido desde {addr}: {reporte}")

        with lock:
            print(f"[METRICAS] ult_seq={ult_seq} | perdidos={paquetes_perdidos} | jitter={jitter:.4f}")


# Lanzar hilos
t1 = threading.Thread(target=manejar_rtp)
t2 = threading.Thread(target=manejar_rtcp)

t1.start()
t2.start()
