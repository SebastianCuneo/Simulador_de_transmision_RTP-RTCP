# Simulador_de_transmision_RTP-RTCP
# UDP Lab - Cliente/Servidor

## Requisitos
- Python 3.x

## Uso (local)
1. Crear venv:
   python3 -m venv venv
   source venv/bin/activate  # linux/mac
   .\venv\Scripts\activate   # windows

2. Ejecutar servidor:
   python servidor_udp.py

3. En otra terminal ejecutar cliente:
   python cliente_udp.py

## Uso en LAN
- Editar SERVER_IP en cliente_udp.py con la IP del servidor (ej: 192.168.1.10).
- Abrir puerto UDP 5005 en firewall del servidor.
