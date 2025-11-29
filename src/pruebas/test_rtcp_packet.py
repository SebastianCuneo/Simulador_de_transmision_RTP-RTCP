"""
Tests unitarios para las clases RTCP (RTCPSenderReport, RTCPReceiverReport).

Valida:
    - Creación de reportes con métricas conocidas
    - Serialización y deserialización
    - Campos calculados (fraction_lost, etc.)
"""
import pytest
import struct
from src.utils.rtcp_packet import RTCPPacket, RTCPSenderReport, RTCPReceiverReport


class TestRTCPPacketBase:
    """Tests de la clase base RTCPPacket"""
    
    def test_constantes_tipo_paquete(self):
        """Verifica constantes de tipos RTCP definidas"""
        assert RTCPPacket.SR == 200
        assert RTCPPacket.RR == 201
        assert RTCPPacket.SDES == 202
        assert RTCPPacket.BYE == 203
        assert RTCPPacket.APP == 204
        
    def test_encode_no_implementado(self):
        """Verifica que encode() lanza NotImplementedError en clase base"""
        packet = RTCPPacket(RTCPPacket.SR, ssrc=0x12345678)
        
        with pytest.raises(NotImplementedError):
            packet.encode()


class TestRTCPSenderReportCreation:
    """Tests de creación de RTCP Sender Report"""
    
    def test_creacion_sr_basico(self):
        """Verifica creación de SR con valores básicos"""
        sr = RTCPSenderReport(
            ssrc=0xDEADBEEF,
            rtp_timestamp=100000,
            packet_count=50,
            octet_count=5000
        )
        
        assert sr.ssrc == 0xDEADBEEF
        assert sr.rtp_timestamp == 100000
        assert sr.packet_count == 50
        assert sr.octet_count == 5000
        assert sr.packet_type == RTCPPacket.SR
        
    def test_ntp_timestamp_automatico(self):
        """Verifica que NTP timestamp se genera automáticamente"""
        sr = RTCPSenderReport(ssrc=0x12345678)
        
        assert sr.ntp_timestamp is not None
        assert isinstance(sr.ntp_timestamp, tuple)
        assert len(sr.ntp_timestamp) == 2
        # NTP seconds debe ser mayor que Unix timestamp de 2020
        # 2020-01-01 en NTP = Unix + 2208988800
        assert sr.ntp_timestamp[0] > 3786825600  # Año 2020 aprox en NTP
        
    def test_ntp_timestamp_custom(self):
        """Verifica que se puede pasar NTP timestamp personalizado"""
        ntp_ts = (3800000000, 500000000)
        sr = RTCPSenderReport(ssrc=0x12345678, ntp_timestamp=ntp_ts)
        
        assert sr.ntp_timestamp == ntp_ts


class TestRTCPSenderReportEncode:
    """Tests de codificación de Sender Report"""
    
    def test_encode_longitud_correcta(self):
        """Verifica que SR codificado tiene 28 bytes"""
        sr = RTCPSenderReport(
            ssrc=0x12345678,
            ntp_timestamp=(3800000000, 0),
            rtp_timestamp=50000,
            packet_count=100,
            octet_count=10000
        )
        
        encoded = sr.encode()
        assert len(encoded) == 28
        
    def test_encode_version_y_tipo(self):
        """Verifica versión y tipo de paquete en cabecera"""
        sr = RTCPSenderReport(ssrc=0)
        encoded = sr.encode()
        
        byte0, pt = struct.unpack('!BB', encoded[0:2])
        version = (byte0 >> 6) & 0x03
        
        assert version == 2
        assert pt == 200  # SR
        
    def test_encode_ssrc_correcto(self):
        """Verifica SSRC codificado correctamente"""
        sr = RTCPSenderReport(ssrc=0xABCDEF01)
        encoded = sr.encode()
        
        ssrc = struct.unpack('!I', encoded[4:8])[0]
        assert ssrc == 0xABCDEF01


class TestRTCPSenderReportDecode:
    """Tests de decodificación de Sender Report"""
    
    def test_decode_sr_valido(self):
        """Verifica decodificación de SR válido"""
        # Construir SR manualmente
        byte0 = 0x80  # V=2, P=0, RC=0
        pt = 200
        length = 6
        ssrc = 0x12345678
        ntp_sec = 3800000000
        ntp_frac = 123456789
        rtp_ts = 50000
        pkt_count = 100
        octet_count = 10000
        
        data = struct.pack('!BBHIIIIII',
                          byte0, pt, length,
                          ssrc, ntp_sec, ntp_frac,
                          rtp_ts, pkt_count, octet_count)
        
        sr = RTCPSenderReport.decode(data)
        
        assert sr is not None
        assert sr.ssrc == 0x12345678
        assert sr.ntp_timestamp == (3800000000, 123456789)
        assert sr.rtp_timestamp == 50000
        assert sr.packet_count == 100
        assert sr.octet_count == 10000
        
    def test_decode_datos_insuficientes(self):
        """Verifica que decode devuelve None con datos insuficientes"""
        data = b'\x80\xC8' + b'\x00' * 20  # 22 bytes < 28
        sr = RTCPSenderReport.decode(data)
        assert sr is None
        
    def test_decode_tipo_incorrecto(self):
        """Verifica que decode devuelve None si PT != SR"""
        # PT = 201 (RR en vez de SR)
        data = struct.pack('!BBHIIIIII',
                          0x80, 201, 6,
                          0, 0, 0, 0, 0, 0)
        sr = RTCPSenderReport.decode(data)
        assert sr is None


class TestRTCPSenderReportRoundtrip:
    """Tests de ida y vuelta para Sender Report"""
    
    def test_roundtrip_sr(self):
        """Verifica que encode->decode preserva campos"""
        original = RTCPSenderReport(
            ssrc=0xCAFEBABE,
            ntp_timestamp=(3850000000, 999999999),
            rtp_timestamp=123456,
            packet_count=500,
            octet_count=50000
        )
        
        encoded = original.encode()
        decoded = RTCPSenderReport.decode(encoded)
        
        assert decoded is not None
        assert decoded.ssrc == original.ssrc
        assert decoded.ntp_timestamp == original.ntp_timestamp
        assert decoded.rtp_timestamp == original.rtp_timestamp
        assert decoded.packet_count == original.packet_count
        assert decoded.octet_count == original.octet_count


class TestRTCPReceiverReportCreation:
    """Tests de creación de RTCP Receiver Report"""
    
    def test_creacion_rr_basico(self):
        """Verifica creación de RR básico sin reportes"""
        rr = RTCPReceiverReport(ssrc=0x11111111)
        
        assert rr.ssrc == 0x11111111
        assert rr.packet_type == RTCPPacket.RR
        assert len(rr.reports) == 0
        
    def test_agregar_bloque_reporte(self):
        """Verifica agregar bloque de reporte de recepción"""
        rr = RTCPReceiverReport(ssrc=0x11111111)
        rr.add_report_block(
            ssrc_sender=0x22222222,
            fraction_lost=25,  # ~10% = 25/256
            packets_lost=100,
            highest_seq=5000,
            jitter=1500,
            lsr=0xAABBCCDD,
            dlsr=0x00001000
        )
        
        assert len(rr.reports) == 1
        assert rr.reports[0]['ssrc'] == 0x22222222
        assert rr.reports[0]['fraction_lost'] == 25
        assert rr.reports[0]['packets_lost'] == 100
        assert rr.reports[0]['jitter'] == 1500
        
    def test_multiples_bloques_reporte(self):
        """Verifica agregar múltiples bloques de reporte"""
        rr = RTCPReceiverReport(ssrc=0x11111111)
        
        for i in range(3):
            rr.add_report_block(
                ssrc_sender=0x22222222 + i,
                fraction_lost=10 * i,
                packets_lost=50 * i,
                highest_seq=1000 + i * 100,
                jitter=500 + i * 100
            )
        
        assert len(rr.reports) == 3


class TestRTCPReceiverReportEncode:
    """Tests de codificación de Receiver Report"""
    
    def test_encode_rr_sin_reportes(self):
        """Verifica longitud de RR sin bloques de reporte"""
        rr = RTCPReceiverReport(ssrc=0x12345678)
        encoded = rr.encode()
        
        # Header (4 bytes) + SSRC (4 bytes) = 8 bytes
        assert len(encoded) == 8
        
    def test_encode_rr_con_un_reporte(self):
        """Verifica longitud de RR con un bloque de reporte"""
        rr = RTCPReceiverReport(ssrc=0x12345678)
        rr.add_report_block(
            ssrc_sender=0x87654321,
            fraction_lost=50,
            packets_lost=200,
            highest_seq=10000,
            jitter=2000
        )
        
        encoded = rr.encode()
        # Header + SSRC (8) + 1 report block (24) = 32 bytes
        assert len(encoded) == 32
        
    def test_encode_fraction_lost_y_packets_lost_combinados(self):
        """Verifica codificación correcta de fraction_lost y packets_lost"""
        rr = RTCPReceiverReport(ssrc=0)
        rr.add_report_block(
            ssrc_sender=0,
            fraction_lost=0xAB,  # 8 bits
            packets_lost=0x123456,  # 24 bits
            highest_seq=0,
            jitter=0
        )
        
        encoded = rr.encode()
        # El campo combinado está en bytes 12-15 (después de header+ssrc+ssrc_sender)
        combined = struct.unpack('!I', encoded[12:16])[0]
        
        fraction = (combined >> 24) & 0xFF
        lost = combined & 0xFFFFFF
        
        assert fraction == 0xAB
        assert lost == 0x123456


class TestRTCPReceiverReportDecode:
    """Tests de decodificación de Receiver Report"""
    
    def test_decode_rr_sin_reportes(self):
        """Verifica decodificación de RR sin bloques de reporte"""
        # Construir RR manualmente
        byte0 = 0x80  # V=2, P=0, RC=0
        pt = 201  # RR
        length = 1  # Solo header
        ssrc = 0x12345678
        
        data = struct.pack('!BBHI', byte0, pt, length, ssrc)
        rr = RTCPReceiverReport.decode(data)
        
        assert rr is not None
        assert rr.ssrc == 0x12345678
        assert len(rr.reports) == 0
        
    def test_decode_rr_con_reporte(self):
        """Verifica decodificación de RR con bloque de reporte"""
        # Construir RR con 1 report block
        byte0 = 0x81  # V=2, P=0, RC=1
        pt = 201
        length = 7  # 1 + 6 words
        ssrc = 0x12345678
        
        # Report block
        ssrc_sender = 0x87654321
        fraction_lost = 25
        packets_lost = 100
        combined = (fraction_lost << 24) | packets_lost
        highest_seq = 5000
        jitter = 1500
        lsr = 0
        dlsr = 0
        
        data = struct.pack('!BBHI', byte0, pt, length, ssrc)
        data += struct.pack('!IIIIII', ssrc_sender, combined, highest_seq, jitter, lsr, dlsr)
        
        rr = RTCPReceiverReport.decode(data)
        
        assert rr is not None
        assert len(rr.reports) == 1
        assert rr.reports[0]['ssrc'] == 0x87654321
        assert rr.reports[0]['fraction_lost'] == 25
        assert rr.reports[0]['packets_lost'] == 100
        assert rr.reports[0]['jitter'] == 1500


class TestRTCPReceiverReportRoundtrip:
    """Tests de ida y vuelta para Receiver Report"""
    
    def test_roundtrip_rr_sin_reportes(self):
        """Verifica roundtrip de RR vacío"""
        original = RTCPReceiverReport(ssrc=0xABCDEF01)
        
        encoded = original.encode()
        decoded = RTCPReceiverReport.decode(encoded)
        
        assert decoded is not None
        assert decoded.ssrc == original.ssrc
        assert len(decoded.reports) == 0
        
    def test_roundtrip_rr_con_reportes(self):
        """Verifica roundtrip de RR con múltiples bloques"""
        original = RTCPReceiverReport(ssrc=0x11111111)
        original.add_report_block(
            ssrc_sender=0x22222222,
            fraction_lost=128,  # 50%
            packets_lost=500,
            highest_seq=10000,
            jitter=2500,
            lsr=0xAABBCCDD,
            dlsr=0x00002000
        )
        original.add_report_block(
            ssrc_sender=0x33333333,
            fraction_lost=64,  # 25%
            packets_lost=250,
            highest_seq=5000,
            jitter=1000
        )
        
        encoded = original.encode()
        decoded = RTCPReceiverReport.decode(encoded)
        
        assert decoded is not None
        assert len(decoded.reports) == 2
        
        # Verificar primer reporte
        assert decoded.reports[0]['ssrc'] == 0x22222222
        assert decoded.reports[0]['fraction_lost'] == 128
        assert decoded.reports[0]['packets_lost'] == 500
        
        # Verificar segundo reporte
        assert decoded.reports[1]['ssrc'] == 0x33333333
        assert decoded.reports[1]['fraction_lost'] == 64


class TestRTCPMetricsCalculations:
    """Tests para verificar cálculos de métricas RTCP"""
    
    def test_fraction_lost_calculo(self):
        """Verifica interpretación de fraction_lost (0-255 -> 0-100%)"""
        # fraction_lost = 255 significa 100% pérdida
        # fraction_lost = 128 significa ~50% pérdida
        # fraction_lost = 0 significa 0% pérdida
        
        test_cases = [
            (0, 0.0),
            (128, 0.5),
            (255, 1.0),
            (64, 0.25),
        ]
        
        for fraction_lost, expected_rate in test_cases:
            actual_rate = fraction_lost / 255.0
            assert abs(actual_rate - expected_rate) < 0.01, \
                f"fraction_lost={fraction_lost}: esperado {expected_rate}, obtenido {actual_rate}"
                
    def test_packets_lost_24bits(self):
        """Verifica que packets_lost se trunca a 24 bits"""
        rr = RTCPReceiverReport(ssrc=0)
        rr.add_report_block(
            ssrc_sender=0,
            fraction_lost=0,
            packets_lost=0x1FFFFFF,  # 25 bits
            highest_seq=0,
            jitter=0
        )
        
        # Debería truncarse a 24 bits
        assert rr.reports[0]['packets_lost'] == 0xFFFFFF

