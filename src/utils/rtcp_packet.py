"""
Módulo para crear y parsear paquetes RTCP (RTP Control Protocol)
RFC 3550 - RTP Control Protocol (RTCP)
"""
import struct
import time

class RTCPPacket:
    """Clase base para paquetes RTCP"""
    
    RTCP_VERSION = 2
    
    # Tipos de paquetes RTCP
    SR = 200   # Sender Report
    RR = 201   # Receiver Report
    SDES = 202 # Source Description
    BYE = 203  # Goodbye
    APP = 204  # Application-defined
    
    def __init__(self, packet_type, ssrc=0):
        self.version = self.RTCP_VERSION
        self.padding = 0
        self.packet_type = packet_type
        self.ssrc = ssrc & 0xFFFFFFFF
        
    def encode(self):
        """Método a implementar por subclases"""
        raise NotImplementedError


class RTCPSenderReport(RTCPPacket):
    """
    RTCP Sender Report (SR)
    
    Estructura:
    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |V=2|P|    RC   |   PT=SR=200   |             length            |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |                         SSRC of sender                        |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |              NTP timestamp, most significant word             |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |             NTP timestamp, least significant word             |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |                         RTP timestamp                         |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |                     sender's packet count                     |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |                      sender's octet count                     |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    """
    
    def __init__(self, ssrc, ntp_timestamp=None, rtp_timestamp=0, 
                 packet_count=0, octet_count=0):
        super().__init__(self.SR, ssrc)
        self.ntp_timestamp = ntp_timestamp if ntp_timestamp else self._get_ntp_timestamp()
        self.rtp_timestamp = rtp_timestamp & 0xFFFFFFFF
        self.packet_count = packet_count & 0xFFFFFFFF
        self.octet_count = octet_count & 0xFFFFFFFF
        self.report_count = 0  # Número de bloques de reporte
        
    def _get_ntp_timestamp(self):
        """Convierte tiempo actual a formato NTP (64 bits)"""
        # NTP epoch es 1900-01-01, Unix epoch es 1970-01-01
        # Diferencia: 70 años en segundos
        NTP_DELTA = 2208988800
        ntp_time = time.time() + NTP_DELTA
        ntp_sec = int(ntp_time)
        ntp_frac = int((ntp_time - ntp_sec) * 2**32)
        return (ntp_sec, ntp_frac)
        
    def encode(self):
        """Codifica el SR a bytes"""
        # Cabecera RTCP
        byte0 = (self.version << 6) | (self.padding << 5) | self.report_count
        
        # Longitud en palabras de 32 bits menos 1
        length = 6  # SR sin bloques de reporte = 28 bytes / 4 - 1
        
        # Empaquetar
        ntp_sec, ntp_frac = self.ntp_timestamp
        
        packet = struct.pack('!BBHIIIIII',
                            byte0,           # V, P, RC
                            self.SR,         # PT
                            length,          # length
                            self.ssrc,       # SSRC
                            ntp_sec,         # NTP timestamp (MSW)
                            ntp_frac,        # NTP timestamp (LSW)
                            self.rtp_timestamp,  # RTP timestamp
                            self.packet_count,   # Packet count
                            self.octet_count)    # Octet count
        
        return packet
    
    @classmethod
    def decode(cls, data):
        """Decodifica bytes a RTCPSenderReport"""
        if len(data) < 28:  # Tamaño mínimo de SR
            return None
            
        fields = struct.unpack('!BBHIIIIII', data[:28])
        
        byte0 = fields[0]
        version = (byte0 >> 6) & 0x03
        report_count = byte0 & 0x1F
        
        if version != cls.RTCP_VERSION or fields[1] != cls.SR:
            return None
        
        sr = cls(
            ssrc=fields[3],
            ntp_timestamp=(fields[4], fields[5]),
            rtp_timestamp=fields[6],
            packet_count=fields[7],
            octet_count=fields[8]
        )
        sr.report_count = report_count
        
        return sr
    
    def __str__(self):
        ntp_sec, ntp_frac = self.ntp_timestamp
        return (f"RTCP SR[ssrc={self.ssrc:08x}, packets={self.packet_count}, "
                f"octets={self.octet_count}, rtp_ts={self.rtp_timestamp}]")


class RTCPReceiverReport(RTCPPacket):
    """
    RTCP Receiver Report (RR)
    
    Similar a SR pero sin información de sender
    """
    
    def __init__(self, ssrc, reports=None):
        super().__init__(self.RR, ssrc)
        self.reports = reports if reports else []
        
    def add_report_block(self, ssrc_sender, fraction_lost, packets_lost, 
                        highest_seq, jitter, lsr=0, dlsr=0):
        """
        Añade un bloque de reporte de recepción
        
        Args:
            ssrc_sender: SSRC del sender que se reporta
            fraction_lost: Fracción de paquetes perdidos (0-255)
            packets_lost: Número total de paquetes perdidos
            highest_seq: Mayor número de secuencia recibido
            jitter: Estimación de jitter
            lsr: Last SR timestamp
            dlsr: Delay since last SR
        """
        report = {
            'ssrc': ssrc_sender & 0xFFFFFFFF,
            'fraction_lost': fraction_lost & 0xFF,
            'packets_lost': packets_lost & 0xFFFFFF,  # 24 bits
            'highest_seq': highest_seq & 0xFFFFFFFF,
            'jitter': jitter & 0xFFFFFFFF,
            'lsr': lsr & 0xFFFFFFFF,
            'dlsr': dlsr & 0xFFFFFFFF
        }
        self.reports.append(report)
        
    def encode(self):
        """Codifica el RR a bytes"""
        report_count = len(self.reports)
        byte0 = (self.version << 6) | (self.padding << 5) | (report_count & 0x1F)
        
        # Longitud: 1 palabra (header) + 6 palabras por reporte
        length = 1 + (6 * report_count)
        
        # Cabecera
        packet = struct.pack('!BBHI',
                            byte0,
                            self.RR,
                            length,
                            self.ssrc)
        
        # Añadir bloques de reporte
        for rep in self.reports:
            # Combinar fraction_lost (8 bits) y packets_lost (24 bits)
            fraction_and_lost = (rep['fraction_lost'] << 24) | rep['packets_lost']
            
            block = struct.pack('!IIIIII',
                               rep['ssrc'],
                               fraction_and_lost,
                               rep['highest_seq'],
                               rep['jitter'],
                               rep['lsr'],
                               rep['dlsr'])
            packet += block
            
        return packet
    
    @classmethod
    def decode(cls, data):
        """Decodifica bytes a RTCPReceiverReport"""
        if len(data) < 8:
            return None
            
        byte0, pt, length, ssrc = struct.unpack('!BBHI', data[:8])
        
        version = (byte0 >> 6) & 0x03
        report_count = byte0 & 0x1F
        
        if version != cls.RTCP_VERSION or pt != cls.RR:
            return None
        
        rr = cls(ssrc)
        
        # Leer bloques de reporte (24 bytes cada uno)
        offset = 8
        for _ in range(report_count):
            if offset + 24 > len(data):
                break
                
            fields = struct.unpack('!IIIIII', data[offset:offset+24])
            
            ssrc_sender = fields[0]
            fraction_lost = (fields[1] >> 24) & 0xFF
            packets_lost = fields[1] & 0xFFFFFF
            highest_seq = fields[2]
            jitter = fields[3]
            lsr = fields[4]
            dlsr = fields[5]
            
            rr.add_report_block(ssrc_sender, fraction_lost, packets_lost,
                              highest_seq, jitter, lsr, dlsr)
            
            offset += 24
            
        return rr
    
    def __str__(self):
        reports_str = f"{len(self.reports)} report(s)"
        if self.reports:
            rep = self.reports[0]
            reports_str += (f" [lost={rep['packets_lost']}, "
                          f"jitter={rep['jitter']}, seq={rep['highest_seq']}]")
        return f"RTCP RR[ssrc={self.ssrc:08x}, {reports_str}]"

