# servidor_udp.py
import socket
import time

SERVER_IP = "0.0.0.0"   # escucha todas las interfaces; también puedes poner la IP específica
SERVER_PORT = 5005

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((SERVER_IP, SERVER_PORT))
print(f"[SERVIDOR] Escuchando UDP en {SERVER_IP}:{SERVER_PORT}")

try:
    while True:
        data, addr = sock.recvfrom(4096)   # buffer 4KB
        received_time = time.time()
        text = data.decode(errors='replace')
        print(f"[{time.strftime('%H:%M:%S')}] Recibido desde {addr}: {text}")
        # opcional: responder (echo)
        resp = f"ACK: recibido {len(data)} bytes".encode()
        sock.sendto(resp, addr)
except KeyboardInterrupt:
    print("\n[SERVIDOR] Interrumpido por el usuario.")
finally:
    sock.close()
