"""
Módulo para crear y parsear paquetes RTP (Real-time Transport Protocol)
RFC 3550 - RTP: A Transport Protocol for Real-Time Applications
"""
import struct
import time

class RTPPacket:
    """
    Clase para manejar paquetes RTP
    
    Estructura de cabecera RTP (12 bytes):
    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |V=2|P|X|  CC   |M|     PT      |       sequence number         |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |                           timestamp                           |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |           synchronization source (SSRC) identifier            |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |                            payload                            |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    """
    
    RTP_VERSION = 2
    HEADER_SIZE = 12
    
    def __init__(self, payload_type=96, sequence_number=0, timestamp=0, ssrc=0, payload=b''):
        """
        Inicializa un paquete RTP
        
        Args:
            payload_type: Tipo de payload (0-127). 96 es dinámico por defecto
            sequence_number: Número de secuencia (0-65535)
            timestamp: Marca de tiempo RTP
            ssrc: Identificador de fuente de sincronización
            payload: Datos del payload
        """
        self.version = self.RTP_VERSION
        self.padding = 0
        self.extension = 0
        self.csrc_count = 0
        self.marker = 0
        self.payload_type = payload_type
        self.sequence_number = sequence_number & 0xFFFF  # 16 bits
        self.timestamp = timestamp & 0xFFFFFFFF  # 32 bits
        self.ssrc = ssrc & 0xFFFFFFFF  # 32 bits
        self.payload = payload
        
    def encode(self):
        """Codifica el paquete RTP a bytes"""
        # Primer byte: V(2bits) + P(1bit) + X(1bit) + CC(4bits)
        byte0 = (self.version << 6) | (self.padding << 5) | \
                (self.extension << 4) | self.csrc_count
        
        # Segundo byte: M(1bit) + PT(7bits)
        byte1 = (self.marker << 7) | self.payload_type
        
        # Construir cabecera (12 bytes)
        header = struct.pack('!BBHII',
                           byte0,
                           byte1,
                           self.sequence_number,
                           self.timestamp,
                           self.ssrc)
        
        return header + self.payload
    
    @classmethod
    def decode(cls, data):
        """
        Decodifica bytes a un objeto RTPPacket
        
        Args:
            data: Bytes del paquete RTP
            
        Returns:
            RTPPacket o None si hay error
        """
        if len(data) < cls.HEADER_SIZE:
            return None
            
        # Desempaquetar cabecera
        byte0, byte1, seq_num, timestamp, ssrc = struct.unpack('!BBHII', data[:12])
        
        # Extraer campos del primer byte
        version = (byte0 >> 6) & 0x03
        padding = (byte0 >> 5) & 0x01
        extension = (byte0 >> 4) & 0x01
        csrc_count = byte0 & 0x0F
        
        # Extraer campos del segundo byte
        marker = (byte1 >> 7) & 0x01
        payload_type = byte1 & 0x7F
        
        # Validar versión
        if version != cls.RTP_VERSION:
            return None
        
        # Crear paquete
        packet = cls(payload_type, seq_num, timestamp, ssrc, data[12:])
        packet.padding = padding
        packet.extension = extension
        packet.csrc_count = csrc_count
        packet.marker = marker
        
        return packet
    
    def __str__(self):
        return (f"RTP[seq={self.sequence_number}, ts={self.timestamp}, "
                f"ssrc={self.ssrc:08x}, pt={self.payload_type}, "
                f"payload={len(self.payload)}B]")
    
    @staticmethod
    def get_timestamp():
        """Genera timestamp RTP basado en tiempo actual (90kHz para video)"""
        return int(time.time() * 90000) & 0xFFFFFFFF

