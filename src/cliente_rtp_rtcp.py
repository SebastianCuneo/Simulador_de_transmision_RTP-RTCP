# cliente_udp.py
import socket
import time

SERVER_IP = "192.168.1.10"   # pon aquí la IP real del servidor
SERVER_PORT = 5005
MSG_COUNT = 5
INTERVAL = 1.0  # segundos entre mensajes

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(3.0)  # tiempo de espera para recibir ACKs

for i in range(1, MSG_COUNT+1):
    msg = f"mensaje #{i} desde cliente - ts={time.time()}"
    sock.sendto(msg.encode(), (SERVER_IP, SERVER_PORT))
    print(f"[CLIENTE] Enviado: {msg}")
    try:
        data, addr = sock.recvfrom(4096)
        print(f"[CLIENTE] Respuesta de {addr}: {data.decode()}")
    except socket.timeout:
        print("[CLIENTE] No se recibió ACK (timeout).")
    time.sleep(INTERVAL)

sock.close()
