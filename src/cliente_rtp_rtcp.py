# cliente_rtp_rtcp.py
import socket
import time
import threading
import random
import struct
from utils.rtp_packet import RTPPacket
from utils.rtcp_packet import RTCPSenderReport


# ==============================================================
#   CONFIGURACIÓN INTERACTIVA
# ==============================================================
def configurar_parametros():
    """Solicita parámetros al usuario de forma interactiva"""
    print("=" * 60)
    print("CONFIGURACIÓN DEL CLIENTE RTP/RTCP")
    print("=" * 60)
    print("(Presiona Enter para usar valor por defecto)\n")

    # Servidor IP
    server_ip = input("IP del servidor [127.0.0.1]: ").strip()
    if not server_ip:
        server_ip = "127.0.0.1"

    # Cantidad de paquetes
    packet_count = 20
    try:
        packets = input("Cantidad de paquetes a enviar [20]: ").strip()
        if packets:
            packet_count = int(packets)
            if packet_count <= 0:
                print("⚠️  Cantidad debe ser positiva, usando 20")
                packet_count = 20
    except ValueError:
        print("⚠️  Valor inválido, usando 20")

    # Intervalo entre paquetes
    interval_val = 0.5
    try:
        interval = input("Intervalo entre paquetes en segundos [0.5]: ").strip()
        if interval:
            interval_val = float(interval)
            if interval_val <= 0:
                print("⚠️  Intervalo debe ser positivo, usando 0.5")
                interval_val = 0.5
    except ValueError:
        print("⚠️  Valor inválido, usando 0.5")

    # Pérdida simulada
    loss_rate_val = 0.1
    try:
        loss = input("Tasa de pérdida (0.0-1.0) [0.1]: ").strip()
        if loss:
            loss_rate_val = float(loss)
            if not (0.0 <= loss_rate_val <= 1.0):
                print("⚠️  Tasa de pérdida fuera de rango (0.0-1.0), usando 0.1")
                loss_rate_val = 0.1
    except ValueError:
        print("⚠️  Valor inválido, usando 0.1")

    # Retardo artificial
    delay_val = 50
    try:
        delay = input("Retardo artificial en ms [50]: ").strip()
        if delay:
            delay_val = int(delay)
            if delay_val < 0:
                print("⚠️  Retardo no puede ser negativo, usando 50")
                delay_val = 50
    except ValueError:
        print("⚠️  Valor inválido, usando 50")

    print("\n" + "=" * 60)
    print("CONFIGURACIÓN APLICADA:")
    print("=" * 60)
    print(f"  Servidor:         {server_ip}")
    print(f"  Paquetes:         {packet_count}")
    print(f"  Intervalo:        {interval_val}s")
    print(f"  Pérdida:          {loss_rate_val * 100:.1f}%")
    print(f"  Retardo:          {delay_val}ms")
    print("=" * 60 + "\n")

    return server_ip, packet_count, interval_val, loss_rate_val, delay_val


# Obtener configuración del usuario
SERVER_IP, PACKET_COUNT, INTERVAL, loss_rate, delay_ms = configurar_parametros()

# Puertos fijos
RTP_PORT = 5005
RTCP_PORT = 5006

# RTP configuration
sequence_number = 0
SSRC = 0x12345678  # Identificador de fuente
PAYLOAD_TYPE = 96  # Payload dinámico
packet_count_sent = 0  # Para RTCP Sender Report
octet_count_sent = 0   # Para RTCP Sender Report

# RTCP configuration
RTCP_REPORT_INTERVAL = 5  # Enviar reporte cada N paquetes
rtcp_event = threading.Event()  # Señal para enviar RTCP

# Métricas del cliente
rtt_samples = []  # Lista de muestras RTT
rtt_promedio = 0.0  # RTT promedio en milisegundos
jitter_rtt = 0.0  # Jitter de RTT
acks_perdidos = 0  # ACKs no recibidos
packet_send_times = {}  # Diccionario: {seq: tiempo_envio}

lock = threading.Lock()

sock_rtp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_rtc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_rtp.settimeout(3)



# ==============================================================
#   HILO 1: ENVIAR RTP
# ==============================================================
def enviar_rtp():
    global sequence_number, packet_count_sent, octet_count_sent, packet_send_times
    for i in range(PACKET_COUNT):

        # pérdida simulada
        if random.random() < loss_rate:
            print("[RTP] Simulación: paquete perdido localmente")
            with lock:
                sequence_number += 1
            time.sleep(INTERVAL)
            continue

        # retardo
        time.sleep(delay_ms / 1000)

        # zona crítica protegida
        with lock:
            sequence_number += 1
            timestamp = RTPPacket.get_timestamp()

            # Crear payload con datos de prueba
            payload = f"Packet {sequence_number}".encode()

            # Crear paquete RTP usando struct
            rtp_packet = RTPPacket(
                payload_type=PAYLOAD_TYPE,
                sequence_number=sequence_number,
                timestamp=timestamp,
                ssrc=SSRC,
                payload=payload
            )

            # Codificar a bytes usando struct
            packet_bytes = rtp_packet.encode()

            # Guardar tiempo de envío para cálculo de RTT
            packet_send_times[sequence_number] = time.time()

            # Actualizar estadísticas para RTCP
            packet_count_sent += 1
            octet_count_sent += len(packet_bytes)

            # Señalizar envío de RTCP cada N paquetes
            if packet_count_sent % RTCP_REPORT_INTERVAL == 0:
                rtcp_event.set()

        sock_rtp.sendto(packet_bytes, (SERVER_IP, RTP_PORT))
        print(f"[RTP] Enviado {rtp_packet}")

        time.sleep(INTERVAL)




# ==============================================================
#   HILO 2: ENVIAR RTCP
# ==============================================================
def enviar_rtcp():
    while True:
        # Esperar señal de envío (cada N paquetes)
        rtcp_event.wait()
        rtcp_event.clear()

        with lock:
            # Crear RTCP Sender Report usando struct
            rtp_timestamp = RTPPacket.get_timestamp()
            sr = RTCPSenderReport(
                ssrc=SSRC,
                rtp_timestamp=rtp_timestamp,
                packet_count=packet_count_sent,
                octet_count=octet_count_sent
            )

            # Codificar a bytes usando struct
            rtcp_bytes = sr.encode()

            # Capturar métricas para mostrar
            rtt_avg = rtt_promedio
            jitter_val = jitter_rtt
            acks_lost = acks_perdidos

        sock_rtc.sendto(rtcp_bytes, (SERVER_IP, RTCP_PORT))
        print(f"[RTCP] Enviado {sr}")
        print(f"       Métricas: RTT={rtt_avg:.2f}ms | Jitter={jitter_val:.2f}ms | ACKs perdidos={acks_lost}")




# ==============================================================
#   HILO 3: RECIBIR ACKs RTP
# ==============================================================
def recibir_ack():
    global rtt_promedio, jitter_rtt, acks_perdidos, rtt_samples, packet_send_times
    ultimo_rtt = None

    while True:
        try:
            data, addr = sock_rtp.recvfrom(4096)
            tiempo_recepcion = time.time()

            # Parsear ACK: "ACK_RTP,{seq}"
            try:
                msg = data.decode(errors='replace')
                if msg.startswith("ACK_RTP,"):
                    seq = int(msg.split(",")[1])

                    with lock:
                        # Calcular RTT si tenemos el tiempo de envío
                        if seq in packet_send_times:
                            tiempo_envio = packet_send_times[seq]
                            rtt_ms = (tiempo_recepcion - tiempo_envio) * 1000  # Convertir a ms

                            # Agregar muestra
                            rtt_samples.append(rtt_ms)

                            # Calcular RTT promedio (últimas 20 muestras)
                            if len(rtt_samples) > 20:
                                rtt_samples.pop(0)
                            rtt_promedio = sum(rtt_samples) / len(rtt_samples)

                            # Calcular jitter de RTT (variación de RTT)
                            if ultimo_rtt is not None:
                                D = abs(rtt_ms - ultimo_rtt)
                                jitter_rtt += (D - jitter_rtt) / 16.0

                            ultimo_rtt = rtt_ms

                            # Limpiar tiempo de envío
                            del packet_send_times[seq]

                            print(f"[ACK] seq={seq} RTT={rtt_ms:.2f}ms")
                        else:
                            print(f"[ACK] seq={seq} (tiempo de envío no encontrado)")
            except (ValueError, IndexError):
                print(f"[ACK] Formato inesperado: {data.decode(errors='replace')}")

        except socket.timeout:
            # Detectar ACKs perdidos (paquetes enviados sin ACK recibido)
            with lock:
                acks_perdidos = len(packet_send_times)
                if acks_perdidos > 0:
                    print(f"[ACK] Timeout - {acks_perdidos} ACKs potencialmente perdidos")
            break




# Lanzar hilos
t_rtp = threading.Thread(target=enviar_rtp)
t_rtcp = threading.Thread(target=enviar_rtcp, daemon=True)
t_ack  = threading.Thread(target=recibir_ack, daemon=True)

t_rtp.start()
t_rtcp.start()
t_ack.start()

t_rtp.join()
print("[CLIENTE] Finalizó envío RTP")

# Dar tiempo para que se reciban los últimos ACKs y terminen los hilos daemon
time.sleep(1.0)

sock_rtp.close()
sock_rtc.close()
print("[CLIENTE] Conexión cerrada")
