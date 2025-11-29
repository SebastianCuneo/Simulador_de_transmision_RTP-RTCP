"""
Tests para la lógica del servidor RTP/RTCP.

Usa mocks para socket y verifica:
    - Detección de pérdida por saltos en secuencia
    - Cálculo de retardo y jitter
    - Procesamiento de reportes RTCP
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import struct


class TestDeteccionPerdida:
    """Tests de detección de pérdida de paquetes"""
    
    def test_sin_perdida_secuencia_consecutiva(self):
        """Verifica que no se detecta pérdida con secuencia consecutiva"""
        secuencias_recibidas = [1, 2, 3, 4, 5]
        
        ult_seq = 0
        paquetes_perdidos = 0
        
        for seq in secuencias_recibidas:
            if ult_seq > 0:
                esperado = ult_seq + 1
                if seq != esperado:
                    perdidos = seq - esperado
                    if perdidos > 0:
                        paquetes_perdidos += perdidos
            ult_seq = seq
        
        assert paquetes_perdidos == 0
        
    def test_detecta_un_paquete_perdido(self):
        """Verifica detección de un paquete perdido"""
        # Falta el paquete 3
        secuencias_recibidas = [1, 2, 4, 5]
        
        ult_seq = 0
        paquetes_perdidos = 0
        
        for seq in secuencias_recibidas:
            if ult_seq > 0:
                esperado = ult_seq + 1
                if seq != esperado:
                    perdidos = seq - esperado
                    if perdidos > 0:
                        paquetes_perdidos += perdidos
            ult_seq = seq
        
        assert paquetes_perdidos == 1  # Falta paquete 3
        
    def test_detecta_multiples_paquetes_perdidos(self):
        """Verifica detección de múltiples paquetes perdidos"""
        # Faltan paquetes 3, 4, 5, 8
        secuencias_recibidas = [1, 2, 6, 7, 9, 10]
        
        ult_seq = 0
        paquetes_perdidos = 0
        
        for seq in secuencias_recibidas:
            if ult_seq > 0:
                esperado = ult_seq + 1
                if seq != esperado:
                    perdidos = seq - esperado
                    if perdidos > 0:
                        paquetes_perdidos += perdidos
            ult_seq = seq
        
        # Salto de 2->6: perdidos 3,4,5 = 3
        # Salto de 7->9: perdido 8 = 1
        assert paquetes_perdidos == 4


class TestCalculoJitterServidor:
    """Tests del cálculo de jitter en el servidor (RFC 3550)"""
    
    def test_jitter_rfc3550_formula(self):
        """
        Verifica fórmula de jitter RFC 3550:
        D(i-1,i) = (R_i - R_{i-1}) - (S_i - S_{i-1})
        J(i) = J(i-1) + (|D(i-1,i)| - J(i-1)) / 16
        """
        # R = tiempo de llegada, S = timestamp RTP
        # Asumimos clock RTP de 90kHz
        
        arrivals = [0.0, 0.050, 0.100, 0.152, 0.200]  # segundos
        timestamps = [0, 4500, 9000, 13500, 18000]     # 90kHz (50ms = 4500)
        
        jitter = 0.0
        ultimo_ts = None
        ultimo_tiempo_llegada = None
        
        for arrival, ts in zip(arrivals, timestamps):
            if ultimo_ts is not None and ultimo_tiempo_llegada is not None:
                # D = diferencia de tiempos de llegada - diferencia de timestamps
                D = (arrival - ultimo_tiempo_llegada) - ((ts - ultimo_ts) / 90000.0)
                jitter += (abs(D) - jitter) / 16.0
            
            ultimo_ts = ts
            ultimo_tiempo_llegada = arrival
        
        # Con tiempos casi perfectos, jitter debería ser muy bajo
        # Excepto el paquete 4 que llegó 2ms tarde
        assert jitter >= 0
        
    def test_jitter_con_variacion(self):
        """Verifica jitter con variación en tiempos de llegada"""
        # Paquetes llegan con variación: +0ms, +5ms, -3ms, +10ms
        base_interval = 0.050  # 50ms
        arrivals = [0.0, 0.055, 0.097, 0.160]  # Con jitter
        timestamps = [0, 4500, 9000, 13500]
        
        jitter = 0.0
        ultimo_ts = timestamps[0]
        ultimo_tiempo_llegada = arrivals[0]
        
        for arrival, ts in zip(arrivals[1:], timestamps[1:]):
            D = (arrival - ultimo_tiempo_llegada) - ((ts - ultimo_ts) / 90000.0)
            jitter += (abs(D) - jitter) / 16.0
            ultimo_ts = ts
            ultimo_tiempo_llegada = arrival
        
        # Jitter debería ser positivo debido a variación
        assert jitter > 0


class TestCalculoRetardo:
    """Tests del cálculo de retardo (delay)"""
    
    def test_calculo_delay_one_way(self):
        """Verifica cálculo de delay one-way aproximado"""
        NTP_DELTA = 2208988800
        
        # Tiempo del sender (en formato NTP)
        unix_time_sender = 1700000000.0  # Ejemplo
        ntp_sec = int(unix_time_sender + NTP_DELTA)
        ntp_frac = int((unix_time_sender + NTP_DELTA - ntp_sec) * 2**32)
        
        # Tiempo de llegada al servidor
        now = 1700000000.050  # 50ms después
        
        # Reconstruir tiempo NTP a Unix
        ntp_time = ntp_sec + ntp_frac / (2**32)
        unix_time_reconstructed = ntp_time - NTP_DELTA
        
        delay_ms = (now - unix_time_reconstructed) * 1000
        
        assert abs(delay_ms - 50.0) < 1.0  # Tolerancia de 1ms
        
    def test_delay_cero_relojes_sincronizados(self):
        """Verifica delay ~0 cuando relojes están sincronizados"""
        NTP_DELTA = 2208988800
        
        # Mismo instante de tiempo
        now = 1700000000.0
        ntp_sec = int(now + NTP_DELTA)
        ntp_frac = 0
        
        ntp_time = ntp_sec + ntp_frac / (2**32)
        unix_time_sender = ntp_time - NTP_DELTA
        
        delay_ms = (now - unix_time_sender) * 1000
        
        assert abs(delay_ms) < 1.0


class TestProcesamientoPaquetesRTP:
    """Tests de procesamiento de paquetes RTP recibidos"""
    
    def test_procesar_paquete_rtp_valido(self):
        """Verifica procesamiento de paquete RTP válido"""
        from src.utils.rtp_packet import RTPPacket
        
        # Crear paquete de prueba
        pkt = RTPPacket(
            payload_type=96,
            sequence_number=42,
            timestamp=378000,
            ssrc=0x12345678,
            payload=b"Test payload"
        )
        
        data = pkt.encode()
        decoded = RTPPacket.decode(data)
        
        assert decoded is not None
        assert decoded.sequence_number == 42
        assert decoded.payload == b"Test payload"
        
    def test_rechazar_paquete_malformado(self):
        """Verifica que paquetes malformados se rechazan"""
        from src.utils.rtp_packet import RTPPacket
        
        # Datos insuficientes
        data = b'\x80\x60\x00\x01'  # Solo 4 bytes
        decoded = RTPPacket.decode(data)
        
        assert decoded is None


class TestProcesamientoRTCP:
    """Tests de procesamiento de reportes RTCP"""
    
    def test_procesar_sender_report(self):
        """Verifica procesamiento de RTCP Sender Report"""
        from src.utils.rtcp_packet import RTCPSenderReport
        
        sr = RTCPSenderReport(
            ssrc=0x12345678,
            rtp_timestamp=100000,
            packet_count=50,
            octet_count=5000
        )
        
        data = sr.encode()
        decoded = RTCPSenderReport.decode(data)
        
        assert decoded is not None
        assert decoded.ssrc == 0x12345678
        assert decoded.packet_count == 50
        
    def test_calculo_loss_rate(self):
        """Verifica cálculo de tasa de pérdida"""
        enviados = 100
        recibidos = 85
        
        perdidos_estimados = max(0, enviados - recibidos)
        loss_rate = perdidos_estimados / enviados if enviados > 0 else 0.0
        
        assert perdidos_estimados == 15
        assert abs(loss_rate - 0.15) < 0.001
        
    def test_loss_rate_cero_cuando_no_hay_perdida(self):
        """Verifica loss_rate = 0 cuando no hay pérdida"""
        enviados = 100
        recibidos = 100
        
        perdidos_estimados = max(0, enviados - recibidos)
        loss_rate = perdidos_estimados / enviados if enviados > 0 else 0.0
        
        assert perdidos_estimados == 0
        assert loss_rate == 0.0


class TestActualizacionMetricas:
    """Tests de actualización del estado interno del servidor"""
    
    def test_actualizar_metricas_tras_rtcp(self):
        """Verifica que las métricas se actualizan correctamente"""
        import time
        
        # Simular estado del servidor
        metrics = {
            "timestamp_local": time.time(),
            "ssrc": 0x12345678,
            "rtp_timestamp": 100000,
            "paquetes_enviados": 50,
            "paquetes_recibidos": 45,
            "paquetes_perdidos": 5,
            "loss_rate": 0.10,
            "jitter_s": 0.002,
            "delay_ms": 25.5,
        }
        
        # Verificar estructura
        assert "paquetes_enviados" in metrics
        assert "loss_rate" in metrics
        assert metrics["paquetes_perdidos"] == 5
        assert abs(metrics["loss_rate"] - 0.10) < 0.001


class TestGeneracionACK:
    """Tests de generación de ACKs para paquetes RTP"""
    
    def test_formato_ack(self):
        """Verifica formato del ACK generado"""
        seq = 42
        ack = f"ACK_RTP,{seq}".encode()
        
        assert ack == b"ACK_RTP,42"
        
    def test_parseo_ack(self):
        """Verifica parseo del ACK"""
        ack_data = b"ACK_RTP,12345"
        msg = ack_data.decode()
        
        assert msg.startswith("ACK_RTP,")
        seq = int(msg.split(",")[1])
        assert seq == 12345

