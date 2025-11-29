"""
Tests unitarios para la clase RTPPacket.

Valida:
    - Creación de paquetes con valores conocidos
    - Codificación y decodificación (roundtrip)
    - Casos borde: payload vacío, secuencias grandes
    - Manejo de datos inválidos
"""
import pytest
import struct
from src.utils.rtp_packet import RTPPacket


class TestRTPPacketCreation:
    """Tests de creación de paquetes RTP"""
    
    def test_creacion_paquete_basico(self):
        """Verifica que un paquete RTP se crea con los valores esperados"""
        packet = RTPPacket(
            payload_type=96,
            sequence_number=1234,
            timestamp=567890,
            ssrc=0xDEADBEEF,
            payload=b"test data"
        )
        
        assert packet.version == 2
        assert packet.payload_type == 96
        assert packet.sequence_number == 1234
        assert packet.timestamp == 567890
        assert packet.ssrc == 0xDEADBEEF
        assert packet.payload == b"test data"
        
    def test_valores_por_defecto(self):
        """Verifica valores por defecto del constructor"""
        packet = RTPPacket()
        
        assert packet.version == 2
        assert packet.payload_type == 96
        assert packet.sequence_number == 0
        assert packet.timestamp == 0
        assert packet.ssrc == 0
        assert packet.payload == b''
        
    def test_truncamiento_sequence_number_16bits(self):
        """Verifica que sequence_number se trunca a 16 bits"""
        packet = RTPPacket(sequence_number=0x1FFFF)  # 17 bits
        assert packet.sequence_number == 0xFFFF  # Solo 16 bits
        
    def test_truncamiento_timestamp_32bits(self):
        """Verifica que timestamp se trunca a 32 bits"""
        packet = RTPPacket(timestamp=0x1FFFFFFFF)  # 33 bits
        assert packet.timestamp == 0xFFFFFFFF
        
    def test_truncamiento_ssrc_32bits(self):
        """Verifica que ssrc se trunca a 32 bits"""
        packet = RTPPacket(ssrc=0x1FFFFFFFF)
        assert packet.ssrc == 0xFFFFFFFF


class TestRTPPacketEncode:
    """Tests de codificación de paquetes RTP a bytes"""
    
    def test_encode_estructura_cabecera(self):
        """Verifica que la cabecera codificada tiene 12 bytes"""
        packet = RTPPacket(payload=b'')
        encoded = packet.encode()
        
        assert len(encoded) == 12  # Solo cabecera, sin payload
        
    def test_encode_con_payload(self):
        """Verifica longitud total con payload"""
        payload = b"hello world"
        packet = RTPPacket(payload=payload)
        encoded = packet.encode()
        
        assert len(encoded) == 12 + len(payload)
        
    def test_encode_version_correcta(self):
        """Verifica que la versión RTP está en los bits correctos"""
        packet = RTPPacket()
        encoded = packet.encode()
        
        byte0 = encoded[0]
        version = (byte0 >> 6) & 0x03
        assert version == 2
        
    def test_encode_payload_type_correcto(self):
        """Verifica codificación del payload type"""
        packet = RTPPacket(payload_type=111)
        encoded = packet.encode()
        
        byte1 = encoded[1]
        pt = byte1 & 0x7F
        assert pt == 111
        
    def test_encode_sequence_number_big_endian(self):
        """Verifica que sequence_number se codifica en big-endian"""
        packet = RTPPacket(sequence_number=0x1234)
        encoded = packet.encode()
        
        seq = struct.unpack('!H', encoded[2:4])[0]
        assert seq == 0x1234


class TestRTPPacketDecode:
    """Tests de decodificación de bytes a RTPPacket"""
    
    def test_decode_paquete_valido(self):
        """Verifica decodificación de un paquete válido"""
        # Construir paquete manualmente: version=2, PT=96, seq=1000, ts=50000, ssrc=0x12345678
        byte0 = 0x80  # V=2, P=0, X=0, CC=0
        byte1 = 96     # M=0, PT=96
        seq = 1000
        ts = 50000
        ssrc = 0x12345678
        payload = b"test"
        
        data = struct.pack('!BBHII', byte0, byte1, seq, ts, ssrc) + payload
        packet = RTPPacket.decode(data)
        
        assert packet is not None
        assert packet.version == 2
        assert packet.payload_type == 96
        assert packet.sequence_number == 1000
        assert packet.timestamp == 50000
        assert packet.ssrc == 0x12345678
        assert packet.payload == b"test"
        
    def test_decode_datos_insuficientes(self):
        """Verifica que decode devuelve None si hay menos de 12 bytes"""
        data = b'\x80\x60' + b'\x00' * 8  # 10 bytes
        packet = RTPPacket.decode(data)
        assert packet is None
        
    def test_decode_version_incorrecta(self):
        """Verifica que decode devuelve None si la versión no es 2"""
        # Version = 1 (inválida)
        byte0 = 0x40  # V=1
        data = struct.pack('!BBHII', byte0, 96, 0, 0, 0)
        packet = RTPPacket.decode(data)
        assert packet is None


class TestRTPPacketRoundtrip:
    """Tests de ida y vuelta (encode + decode)"""
    
    def test_roundtrip_basico(self):
        """Verifica que encode->decode preserva todos los campos"""
        original = RTPPacket(
            payload_type=100,
            sequence_number=65000,
            timestamp=123456789,
            ssrc=0xABCDEF01,
            payload=b"roundtrip test payload"
        )
        
        encoded = original.encode()
        decoded = RTPPacket.decode(encoded)
        
        assert decoded is not None
        assert decoded.payload_type == original.payload_type
        assert decoded.sequence_number == original.sequence_number
        assert decoded.timestamp == original.timestamp
        assert decoded.ssrc == original.ssrc
        assert decoded.payload == original.payload
        
    def test_roundtrip_payload_vacio(self):
        """Verifica roundtrip con payload vacío"""
        original = RTPPacket(
            payload_type=96,
            sequence_number=1,
            timestamp=1000,
            ssrc=0x11111111,
            payload=b''
        )
        
        encoded = original.encode()
        decoded = RTPPacket.decode(encoded)
        
        assert decoded is not None
        assert decoded.payload == b''
        
    def test_roundtrip_secuencia_maxima(self):
        """Verifica roundtrip con número de secuencia máximo (65535)"""
        original = RTPPacket(sequence_number=65535)
        
        encoded = original.encode()
        decoded = RTPPacket.decode(encoded)
        
        assert decoded is not None
        assert decoded.sequence_number == 65535
        
    def test_roundtrip_payload_binario(self):
        """Verifica roundtrip con payload binario (bytes arbitrarios)"""
        original = RTPPacket(payload=bytes(range(256)))
        
        encoded = original.encode()
        decoded = RTPPacket.decode(encoded)
        
        assert decoded is not None
        assert decoded.payload == bytes(range(256))


class TestRTPPacketStr:
    """Tests del método __str__"""
    
    def test_str_formato(self):
        """Verifica que __str__ devuelve formato legible"""
        packet = RTPPacket(
            sequence_number=42,
            timestamp=1000,
            ssrc=0x12345678,
            payload_type=96,
            payload=b"test"
        )
        
        result = str(packet)
        
        assert "seq=42" in result
        assert "ts=1000" in result
        assert "12345678" in result
        assert "pt=96" in result
        assert "4B" in result  # len(payload) = 4


class TestRTPPacketGetTimestamp:
    """Tests del método estático get_timestamp"""
    
    def test_get_timestamp_retorna_entero(self):
        """Verifica que get_timestamp devuelve un entero"""
        ts = RTPPacket.get_timestamp()
        assert isinstance(ts, int)
        
    def test_get_timestamp_rango_32bits(self):
        """Verifica que el timestamp está en rango de 32 bits"""
        ts = RTPPacket.get_timestamp()
        assert 0 <= ts <= 0xFFFFFFFF
        
    def test_get_timestamp_incrementa(self):
        """Verifica que timestamps sucesivos son crecientes o iguales"""
        import time
        ts1 = RTPPacket.get_timestamp()
        time.sleep(0.01)  # 10ms
        ts2 = RTPPacket.get_timestamp()
        
        # Pueden ser iguales o ts2 > ts1 (considerando wrap-around de 32 bits)
        # Con 90kHz, 10ms = 900 unidades
        assert ts2 >= ts1 or (ts1 > 0xFFFFFE00 and ts2 < 0x200)  # wrap-around

