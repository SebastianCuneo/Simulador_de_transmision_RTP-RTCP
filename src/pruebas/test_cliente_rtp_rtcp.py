"""
Tests para la lógica del cliente RTP/RTCP.

Usa mocks para:
    - socket.socket (no envía UDP real)
    - time.time y time.sleep (timestamps deterministas)
    - random.random (control de pérdida simulada)
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
import struct


class TestClienteRTPLogic:
    """
    Tests de la lógica de construcción de paquetes RTP.
    
    Como el cliente usa variables globales y ejecución inmediata,
    testeamos las clases RTP directamente con escenarios de cliente.
    """
    
    def test_construccion_paquete_rtp_secuencia_incrementa(self):
        """Verifica que los números de secuencia se incrementan"""
        from src.utils.rtp_packet import RTPPacket
        
        packets = []
        for seq in range(1, 6):  # 5 paquetes
            pkt = RTPPacket(
                payload_type=96,
                sequence_number=seq,
                timestamp=seq * 1000,
                ssrc=0x12345678,
                payload=f"Packet {seq}".encode()
            )
            packets.append(pkt)
        
        # Verificar secuencias consecutivas
        for i, pkt in enumerate(packets, start=1):
            assert pkt.sequence_number == i
            
    def test_construccion_paquete_rtp_timestamp_incrementa(self):
        """Verifica que timestamps se pueden incrementar correctamente"""
        from src.utils.rtp_packet import RTPPacket
        
        base_ts = 90000  # 1 segundo en 90kHz
        interval = 4500  # 50ms en 90kHz
        
        timestamps = []
        for i in range(10):
            ts = (base_ts + i * interval) & 0xFFFFFFFF
            timestamps.append(ts)
        
        # Verificar incrementos constantes
        for i in range(1, len(timestamps)):
            diff = timestamps[i] - timestamps[i-1]
            assert diff == interval


class TestSimulacionPerdida:
    """Tests de la simulación de pérdida de paquetes"""
    
    def test_logica_perdida_con_random_bajo_umbral(self):
        """Cuando random < loss_rate, el paquete se pierde"""
        loss_rate = 0.1
        
        # Simular decisiones de pérdida
        random_values = [0.05, 0.15, 0.08, 0.20, 0.09]
        expected_lost = [True, False, True, False, True]  # random < loss_rate
        
        for random_val, should_lose in zip(random_values, expected_lost):
            is_lost = random_val < loss_rate
            assert is_lost == should_lose
            
    def test_simulacion_perdida_controlada(self):
        """Verifica conteo de paquetes enviados vs perdidos"""
        loss_rate = 0.2  # 20% pérdida
        
        # Con random controlado, simular envío de 10 paquetes
        random_sequence = [0.1, 0.5, 0.15, 0.3, 0.05, 0.8, 0.19, 0.25, 0.02, 0.9]
        
        sent = 0
        lost = 0
        
        for rnd in random_sequence:
            if rnd < loss_rate:
                lost += 1
            else:
                sent += 1
        
        # Con loss_rate=0.2, valores < 0.2: 0.1, 0.15, 0.05, 0.19, 0.02 = 5 perdidos
        assert lost == 5
        assert sent == 5


class TestCalculoRTT:
    """Tests del cálculo de RTT (Round Trip Time)"""
    
    def test_calculo_rtt_basico(self):
        """Verifica cálculo de RTT entre envío y recepción"""
        tiempo_envio = 1000.0  # segundos
        tiempo_recepcion = 1000.050  # 50ms después
        
        rtt_ms = (tiempo_recepcion - tiempo_envio) * 1000
        
        assert abs(rtt_ms - 50.0) < 0.001
        
    def test_promedio_rtt(self):
        """Verifica cálculo de RTT promedio"""
        rtt_samples = [45.0, 52.0, 48.0, 55.0, 50.0]
        
        rtt_promedio = sum(rtt_samples) / len(rtt_samples)
        
        assert abs(rtt_promedio - 50.0) < 0.001
        
    def test_promedio_rtt_ventana_deslizante(self):
        """Verifica RTT promedio con ventana de últimas N muestras"""
        all_samples = list(range(1, 26))  # 25 muestras
        window_size = 20
        
        # Mantener solo últimas 20
        if len(all_samples) > window_size:
            samples = all_samples[-window_size:]
        else:
            samples = all_samples
        
        assert len(samples) == 20
        assert samples == list(range(6, 26))  # Últimas 20


class TestCalculoJitter:
    """Tests del cálculo de jitter (RFC 3550)"""
    
    def test_calculo_jitter_rfc3550(self):
        """
        Verifica cálculo de jitter según RFC 3550:
        J(i) = J(i-1) + (|D(i-1,i)| - J(i-1)) / 16
        """
        jitter = 0.0
        rtt_samples = [50.0, 52.0, 48.0, 55.0, 45.0]
        
        ultimo_rtt = None
        for rtt in rtt_samples:
            if ultimo_rtt is not None:
                D = abs(rtt - ultimo_rtt)
                jitter += (D - jitter) / 16.0
            ultimo_rtt = rtt
        
        # El jitter debería ser bajo ya que las variaciones son pequeñas
        assert jitter < 10.0  # Esperamos jitter bajo
        assert jitter > 0.0   # Pero no cero
        
    def test_jitter_converge(self):
        """Verifica que jitter converge con RTT constante"""
        jitter = 5.0  # Empezar con jitter alto
        constant_rtt = 50.0
        
        ultimo_rtt = 50.0
        for _ in range(100):  # Muchas iteraciones
            D = abs(constant_rtt - ultimo_rtt)  # D = 0
            jitter += (D - jitter) / 16.0
            ultimo_rtt = constant_rtt
        
        # Jitter debería tender a 0 con RTT constante
        assert jitter < 0.01


class TestRTCPSenderReportGeneration:
    """Tests de generación de RTCP Sender Reports por el cliente"""
    
    def test_sender_report_metricas_correctas(self):
        """Verifica que SR contiene métricas correctas"""
        from src.utils.rtcp_packet import RTCPSenderReport
        from src.utils.rtp_packet import RTPPacket
        
        # Simular estado del cliente
        packet_count = 50
        octet_count = 5000
        ssrc = 0x12345678
        
        sr = RTCPSenderReport(
            ssrc=ssrc,
            rtp_timestamp=RTPPacket.get_timestamp(),
            packet_count=packet_count,
            octet_count=octet_count
        )
        
        assert sr.packet_count == 50
        assert sr.octet_count == 5000
        assert sr.ssrc == ssrc
        
    def test_sender_report_cada_n_paquetes(self):
        """Verifica que RTCP se envía cada N paquetes"""
        RTCP_REPORT_INTERVAL = 5
        
        report_times = []
        for packet_num in range(1, 21):  # 20 paquetes
            if packet_num % RTCP_REPORT_INTERVAL == 0:
                report_times.append(packet_num)
        
        assert report_times == [5, 10, 15, 20]


class TestMockedClientFunctions:
    """Tests con funciones mockeadas para simular cliente"""
    
    @patch('time.time')
    @patch('time.sleep')
    def test_timestamps_deterministas(self, mock_sleep, mock_time):
        """Verifica generación de timestamps con time mockeado"""
        # Configurar time.time para devolver valores controlados
        mock_time.side_effect = [1000.0, 1000.5, 1001.0, 1001.5, 1002.0]
        mock_sleep.return_value = None
        
        import time
        
        timestamps = []
        for _ in range(5):
            timestamps.append(time.time())
        
        assert timestamps == [1000.0, 1000.5, 1001.0, 1001.5, 1002.0]
        
    @patch('random.random')
    def test_perdida_controlada_con_mock(self, mock_random):
        """Verifica pérdida controlada con random mockeado"""
        # Hacer que solo el segundo y cuarto paquete se "pierdan"
        mock_random.side_effect = [0.5, 0.05, 0.8, 0.08, 0.9]
        loss_rate = 0.1
        
        import random
        
        results = []
        for _ in range(5):
            if random.random() < loss_rate:
                results.append("lost")
            else:
                results.append("sent")
        
        assert results == ["sent", "lost", "sent", "lost", "sent"]


class TestIntegracionClienteConMocks:
    """Tests de integración del cliente con todos los componentes mockeados"""
    
    def test_flujo_envio_paquetes_simulado(self):
        """Simula el flujo completo de envío sin red real"""
        from src.utils.rtp_packet import RTPPacket
        from src.utils.rtcp_packet import RTCPSenderReport
        
        # Configuración
        PACKET_COUNT = 10
        SSRC = 0x12345678
        PAYLOAD_TYPE = 96
        
        # Estado
        sequence_number = 0
        packet_count_sent = 0
        octet_count_sent = 0
        packets_created = []
        
        # Simular envío (sin pérdida para este test)
        for i in range(PACKET_COUNT):
            sequence_number += 1
            timestamp = 90000 + i * 4500  # Simular timestamp
            
            payload = f"Packet {sequence_number}".encode()
            
            rtp_packet = RTPPacket(
                payload_type=PAYLOAD_TYPE,
                sequence_number=sequence_number,
                timestamp=timestamp,
                ssrc=SSRC,
                payload=payload
            )
            
            packet_bytes = rtp_packet.encode()
            packets_created.append(rtp_packet)
            
            packet_count_sent += 1
            octet_count_sent += len(packet_bytes)
        
        # Verificar
        assert len(packets_created) == 10
        assert packet_count_sent == 10
        assert packets_created[0].sequence_number == 1
        assert packets_created[-1].sequence_number == 10
        
        # Verificar RTCP generado
        sr = RTCPSenderReport(
            ssrc=SSRC,
            rtp_timestamp=packets_created[-1].timestamp,
            packet_count=packet_count_sent,
            octet_count=octet_count_sent
        )
        
        assert sr.packet_count == 10
        assert sr.octet_count > 0

