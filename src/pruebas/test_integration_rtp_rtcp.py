"""
Test de integración liviano para RTP/RTCP.

Simula el envío de paquetes RTP y reportes RTCP entre
componentes cliente y servidor sin usar red real.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import struct
import time


class TestIntegracionRTPRTCP:
    """Tests de integración entre cliente y servidor"""
    
    def test_flujo_completo_sin_perdida(self):
        """Simula flujo completo: cliente envía, servidor recibe"""
        from src.utils.rtp_packet import RTPPacket
        from src.utils.rtcp_packet import RTCPSenderReport
        
        # === CONFIGURACIÓN ===
        PACKET_COUNT = 10
        SSRC = 0x12345678
        
        # === ESTADO CLIENTE ===
        client_seq = 0
        client_packets_sent = 0
        client_octets_sent = 0
        
        # === ESTADO SERVIDOR ===
        server_last_seq = 0
        server_packets_received = 0
        server_packets_lost = 0
        
        # Buffer para simular "red"
        rtp_buffer = []
        
        # === CLIENTE: Enviar paquetes RTP ===
        for i in range(PACKET_COUNT):
            client_seq += 1
            ts = 90000 + i * 4500
            payload = f"Packet {client_seq}".encode()
            
            pkt = RTPPacket(
                payload_type=96,
                sequence_number=client_seq,
                timestamp=ts,
                ssrc=SSRC,
                payload=payload
            )
            
            packet_bytes = pkt.encode()
            rtp_buffer.append(packet_bytes)
            
            client_packets_sent += 1
            client_octets_sent += len(packet_bytes)
        
        # === SERVIDOR: Recibir paquetes RTP ===
        for data in rtp_buffer:
            pkt = RTPPacket.decode(data)
            assert pkt is not None
            
            seq = pkt.sequence_number
            
            server_packets_received += 1
            
            if server_last_seq > 0:
                esperado = server_last_seq + 1
                if seq != esperado and seq > esperado:
                    server_packets_lost += (seq - esperado)
            
            server_last_seq = seq
        
        # === VERIFICACIONES ===
        assert client_packets_sent == PACKET_COUNT
        assert server_packets_received == PACKET_COUNT
        assert server_packets_lost == 0
        
    def test_flujo_con_perdida_simulada(self):
        """Simula flujo con pérdida de algunos paquetes"""
        from src.utils.rtp_packet import RTPPacket
        
        PACKET_COUNT = 10
        SSRC = 0x12345678
        
        # Índices de paquetes que se "pierden" (0-indexed)
        lost_indices = {2, 5, 7}  # Paquetes 3, 6, 8 no llegan
        
        # Estado
        client_seq = 0
        rtp_buffer = []
        
        # Cliente envía
        for i in range(PACKET_COUNT):
            client_seq += 1
            
            if i in lost_indices:
                # Paquete se "pierde", no se agrega al buffer
                continue
            
            pkt = RTPPacket(
                sequence_number=client_seq,
                ssrc=SSRC,
                payload=f"Pkt {client_seq}".encode()
            )
            rtp_buffer.append(pkt.encode())
        
        # Servidor recibe
        server_last_seq = 0
        server_packets_received = 0
        server_packets_lost = 0
        
        for data in rtp_buffer:
            pkt = RTPPacket.decode(data)
            seq = pkt.sequence_number
            
            server_packets_received += 1
            
            if server_last_seq > 0:
                esperado = server_last_seq + 1
                if seq != esperado and seq > esperado:
                    server_packets_lost += (seq - esperado)
            
            server_last_seq = seq
        
        # Verificaciones
        assert server_packets_received == PACKET_COUNT - len(lost_indices)
        assert server_packets_lost == len(lost_indices)
        
    def test_rtcp_sender_report_coherente(self):
        """Verifica que RTCP SR contiene métricas coherentes"""
        from src.utils.rtp_packet import RTPPacket
        from src.utils.rtcp_packet import RTCPSenderReport
        
        # Simular envío de paquetes
        SSRC = 0xCAFEBABE
        packets_sent = 25
        octets_sent = 0
        
        for i in range(packets_sent):
            pkt = RTPPacket(
                sequence_number=i + 1,
                ssrc=SSRC,
                payload=b"x" * 100
            )
            octets_sent += len(pkt.encode())
        
        # Generar SR
        sr = RTCPSenderReport(
            ssrc=SSRC,
            packet_count=packets_sent,
            octet_count=octets_sent
        )
        
        # Codificar y decodificar (simular transmisión)
        sr_bytes = sr.encode()
        sr_received = RTCPSenderReport.decode(sr_bytes)
        
        # Verificar
        assert sr_received is not None
        assert sr_received.ssrc == SSRC
        assert sr_received.packet_count == packets_sent
        assert sr_received.octet_count == octets_sent
        
    def test_integracion_metricas_servidor(self):
        """Verifica que servidor calcula métricas correctas tras recibir RTCP"""
        from src.utils.rtcp_packet import RTCPSenderReport
        
        # Estado del servidor
        paquetes_recibidos = 45
        
        # SR del cliente indica 50 enviados
        sr = RTCPSenderReport(
            ssrc=0x12345678,
            packet_count=50,
            octet_count=5000
        )
        
        # Servidor procesa SR
        enviados = sr.packet_count
        recibidos_local = paquetes_recibidos
        perdidos_estimados = max(0, enviados - recibidos_local)
        loss_rate = perdidos_estimados / enviados if enviados > 0 else 0.0
        
        # Verificar
        assert enviados == 50
        assert perdidos_estimados == 5
        assert abs(loss_rate - 0.10) < 0.001  # 10% pérdida


class TestIntegracionJitter:
    """Tests de integración para cálculo de jitter"""
    
    def test_jitter_con_secuencia_realista(self):
        """Simula secuencia realista y verifica jitter"""
        from src.utils.rtp_packet import RTPPacket
        
        # Simular tiempos de llegada con variación
        # Intervalo nominal: 50ms, variación: ±5ms
        base_interval = 0.050
        variations = [0, 0.003, -0.002, 0.005, -0.001, 0.004, -0.003, 0.002, 0, 0.001]
        
        arrivals = [0.0]
        for v in variations:
            arrivals.append(arrivals[-1] + base_interval + v)
        
        # Timestamps RTP (90kHz, intervalo = 4500)
        timestamps = [i * 4500 for i in range(len(arrivals))]
        
        # Calcular jitter
        jitter = 0.0
        for i in range(1, len(arrivals)):
            D = (arrivals[i] - arrivals[i-1]) - ((timestamps[i] - timestamps[i-1]) / 90000.0)
            jitter += (abs(D) - jitter) / 16.0
        
        # Jitter debería ser pequeño pero > 0
        assert jitter > 0
        assert jitter < 0.01  # Menos de 10ms de jitter


class TestIntegracionACK:
    """Tests de integración del sistema de ACK"""
    
    def test_ack_round_trip(self):
        """Simula envío de paquete y recepción de ACK"""
        from src.utils.rtp_packet import RTPPacket
        
        # Cliente envía
        pkt = RTPPacket(
            sequence_number=42,
            ssrc=0x12345678,
            payload=b"test"
        )
        pkt_bytes = pkt.encode()
        
        # Servidor recibe y genera ACK
        received = RTPPacket.decode(pkt_bytes)
        ack = f"ACK_RTP,{received.sequence_number}".encode()
        
        # Cliente recibe ACK
        msg = ack.decode()
        assert msg.startswith("ACK_RTP,")
        seq = int(msg.split(",")[1])
        
        assert seq == 42

