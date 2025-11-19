# cliente_rtp_rtcp.py
import socket
import time
import threading
import random

SERVER_IP = "192.168.1.10"
RTP_PORT = 5005
RTCP_PORT = 5006

PACKET_COUNT = 20
INTERVAL = 0.5   # tiempo entre RTP
loss_rate = 0.1  # 10% pérdida simulada
delay_ms = 50    # retardo artificial

sequence_number = 0
lock = threading.Lock()

sock_rtp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_rtc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_rtp.settimeout(3)



# ==============================================================
#   HILO 1: ENVIAR RTP
# ==============================================================
def enviar_rtp():
    global sequence_number
    for i in range(PACKET_COUNT):

        # pérdida simulada
        if random.random() < loss_rate:
            print("[RTP] Simulación: paquete perdido localmente")
            time.sleep(INTERVAL)
            continue

        # retardo
        time.sleep(delay_ms / 1000)

        # zona crítica protegida
        with lock:
            sequence_number += 1
            ts = time.time()
            mensaje = f"RTP,{sequence_number},{ts}"

        sock_rtp.sendto(mensaje.encode(), (SERVER_IP, RTP_PORT))
        print(f"[RTP] Enviado seq={sequence_number} ts={ts}")

        time.sleep(INTERVAL)




# ==============================================================
#   HILO 2: ENVIAR RTCP
# ==============================================================
def enviar_rtcp():
    while True:
        time.sleep(2)  # frecuencia de reporte

        with lock:
            reporte = f"RTCP_REPORT seq={sequence_number} time={time.time()}"

        sock_rtc.sendto(reporte.encode(), (SERVER_IP, RTCP_PORT))
        print(f"[RTCP] Reporte enviado: {reporte}")




# ==============================================================
#   HILO 3: RECIBIR ACKs RTP
# ==============================================================
def recibir_ack():
    while True:
        try:
            data, addr = sock_rtp.recvfrom(4096)
            print(f"[ACK] {data.decode(errors='replace')}")
        except socket.timeout:
            break




# Lanzar hilos
t_rtp = threading.Thread(target=enviar_rtp)
t_rtcp = threading.Thread(target=enviar_rtcp)
t_ack  = threading.Thread(target=recibir_ack)

t_rtp.start()
t_rtcp.start()
t_ack.start()

t_rtp.join()
print("[CLIENTE] Finalizó envío RTP")

sock_rtp.close()
sock_rtc.close()
