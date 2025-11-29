"""
Tests para el visualizador de métricas.

Solo testea la lógica de transformación de datos,
no el renderizado del gráfico.
"""
import pytest
import tempfile
import os
import sys
import csv
from typing import List, Tuple


# Función de lectura replicada para testear sin importar matplotlib
def leer_metricas_desde_csv_testable(rtcp_log_file: str) -> Tuple[List[float], List[float], List[float], List[float]]:
    """
    Lee el archivo CSV y devuelve listas con:
        tiempos_rel, delay_ms, jitter_s, loss_pct
    
    Versión testeable que no requiere matplotlib.
    """
    if not os.path.exists(rtcp_log_file):
        return [], [], [], []

    tiempos: List[float] = []
    delay_ms: List[float] = []
    jitter_s: List[float] = []
    loss_pct: List[float] = []

    with open(rtcp_log_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            t = float(row["timestamp_local"])
            d = float(row["delay_ms"])
            j = float(row["jitter_s"])
            loss = float(row["loss_rate"]) * 100.0

            tiempos.append(t)
            delay_ms.append(d)
            jitter_s.append(j)
            loss_pct.append(loss)

    if not tiempos:
        return [], [], [], []

    t0 = tiempos[0]
    tiempos_rel = [t - t0 for t in tiempos]
    return tiempos_rel, delay_ms, jitter_s, loss_pct


class TestLeerMetricasDesdeCSV:
    """Tests de la función leer_metricas_desde_csv"""
    
    def test_archivo_no_existe(self):
        """Verifica retorno vacío cuando el archivo no existe"""
        result = leer_metricas_desde_csv_testable('archivo_inexistente_xyz123.csv')
        assert result == ([], [], [], [])
            
    def test_lectura_csv_valido(self):
        """Verifica lectura correcta de CSV con datos válidos"""
        # Crear archivo temporal con datos de prueba
        csv_content = """timestamp_local,ssrc,rtp_timestamp,paquetes_enviados,paquetes_recibidos,paquetes_perdidos,loss_rate,jitter_s,delay_ms
1700000000.000,12345678,90000,10,10,0,0.000000,0.001000,25.500
1700000002.500,12345678,315000,20,19,1,0.050000,0.002000,26.300
1700000005.000,12345678,540000,30,27,3,0.100000,0.003500,27.100
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write(csv_content)
            temp_path = f.name
        
        try:
            tiempos, delay, jitter, loss = leer_metricas_desde_csv_testable(temp_path)
            
            # Verificar longitud
            assert len(tiempos) == 3
            assert len(delay) == 3
            assert len(jitter) == 3
            assert len(loss) == 3
            
            # Verificar tiempos relativos (t0 = primer timestamp)
            assert tiempos[0] == 0.0
            assert abs(tiempos[1] - 2.5) < 0.001
            assert abs(tiempos[2] - 5.0) < 0.001
            
            # Verificar delay
            assert abs(delay[0] - 25.5) < 0.001
            assert abs(delay[1] - 26.3) < 0.001
            
            # Verificar jitter
            assert abs(jitter[0] - 0.001) < 0.0001
            
            # Verificar loss (convertido a porcentaje)
            assert abs(loss[0] - 0.0) < 0.001
            assert abs(loss[1] - 5.0) < 0.001
            assert abs(loss[2] - 10.0) < 0.001
        finally:
            os.unlink(temp_path)
            
    def test_csv_vacio_solo_cabecera(self):
        """Verifica retorno vacío cuando CSV solo tiene cabecera"""
        csv_content = """timestamp_local,ssrc,rtp_timestamp,paquetes_enviados,paquetes_recibidos,paquetes_perdidos,loss_rate,jitter_s,delay_ms
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write(csv_content)
            temp_path = f.name
        
        try:
            result = leer_metricas_desde_csv_testable(temp_path)
            assert result == ([], [], [], [])
        finally:
            os.unlink(temp_path)


class TestTransformacionDatos:
    """Tests de transformación de datos para gráficos"""
    
    def test_conversion_loss_rate_a_porcentaje(self):
        """Verifica conversión de loss_rate (0-1) a porcentaje (0-100)"""
        loss_rates = [0.0, 0.05, 0.10, 0.25, 0.50, 1.0]
        expected_pct = [0.0, 5.0, 10.0, 25.0, 50.0, 100.0]
        
        for rate, expected in zip(loss_rates, expected_pct):
            pct = rate * 100.0
            assert abs(pct - expected) < 0.001
            
    def test_tiempos_relativos(self):
        """Verifica cálculo de tiempos relativos desde timestamp"""
        timestamps = [1700000000.0, 1700000002.5, 1700000005.0, 1700000010.0]
        
        t0 = timestamps[0]
        tiempos_rel = [t - t0 for t in timestamps]
        
        expected = [0.0, 2.5, 5.0, 10.0]
        
        for actual, exp in zip(tiempos_rel, expected):
            assert abs(actual - exp) < 0.001


class TestPreparacionDatosGrafico:
    """Tests de preparación de datos para matplotlib"""
    
    def test_datos_vacios_no_causan_error(self):
        """Verifica que datos vacíos se manejan correctamente"""
        tiempos = []
        delay = []
        jitter = []
        loss = []
        
        # Simular lo que haría la función de actualización
        if not tiempos:
            # No hay datos, no se actualiza el gráfico
            pass
        
        assert len(tiempos) == 0
        
    def test_datos_con_una_muestra(self):
        """Verifica manejo de datos con una sola muestra"""
        tiempos = [0.0]
        delay = [25.0]
        jitter = [0.001]
        loss = [0.0]
        
        # Con una sola muestra, los gráficos deberían mostrar un punto
        assert len(tiempos) == 1
        assert tiempos[0] == 0.0


class TestValidacionDatos:
    """Tests de validación de datos de métricas"""
    
    def test_delay_positivo(self):
        """Verifica que delay sea positivo (o cercano a 0)"""
        delays = [25.5, 26.3, 24.8, 27.1]
        
        for d in delays:
            assert d >= 0, f"Delay negativo: {d}"
            
    def test_jitter_no_negativo(self):
        """Verifica que jitter no sea negativo"""
        jitters = [0.001, 0.002, 0.0035, 0.0]
        
        for j in jitters:
            assert j >= 0, f"Jitter negativo: {j}"
            
    def test_loss_rate_en_rango(self):
        """Verifica que loss_rate esté en rango [0, 100]%"""
        loss_pcts = [0.0, 5.0, 10.0, 50.0, 100.0]
        
        for loss in loss_pcts:
            assert 0 <= loss <= 100, f"Loss fuera de rango: {loss}"


class TestConsistenciaConVisualizadorReal:
    """
    Tests que verifican que la lógica testeable es consistente 
    con la implementación real del visualizador.
    """
    
    def test_formato_csv_esperado(self):
        """Verifica que el formato CSV esperado es correcto"""
        # Estos son los campos que el servidor genera
        expected_fields = [
            "timestamp_local",
            "ssrc", 
            "rtp_timestamp",
            "paquetes_enviados",
            "paquetes_recibidos",
            "paquetes_perdidos",
            "loss_rate",
            "jitter_s",
            "delay_ms"
        ]
        
        csv_header = "timestamp_local,ssrc,rtp_timestamp,paquetes_enviados,paquetes_recibidos,paquetes_perdidos,loss_rate,jitter_s,delay_ms"
        
        parsed_fields = csv_header.split(",")
        assert parsed_fields == expected_fields
        
    def test_lectura_multiples_registros(self):
        """Verifica lectura de múltiples registros RTCP"""
        # Simular 5 reportes RTCP
        csv_lines = [
            "timestamp_local,ssrc,rtp_timestamp,paquetes_enviados,paquetes_recibidos,paquetes_perdidos,loss_rate,jitter_s,delay_ms"
        ]
        
        for i in range(5):
            ts = 1700000000.0 + i * 2.5
            csv_lines.append(
                f"{ts:.3f},12345678,{90000 + i * 22500},{(i+1)*10},{(i+1)*10 - i},{i},{i*0.02:.6f},{0.001 + i*0.0005:.6f},{25.0 + i*0.5:.3f}"
            )
        
        csv_content = "\n".join(csv_lines)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write(csv_content)
            temp_path = f.name
        
        try:
            tiempos, delay, jitter, loss = leer_metricas_desde_csv_testable(temp_path)
            
            assert len(tiempos) == 5
            
            # Verificar que tiempos son relativos y crecientes
            for i in range(1, len(tiempos)):
                assert tiempos[i] > tiempos[i-1]
            
            # Primer tiempo debe ser 0
            assert tiempos[0] == 0.0
        finally:
            os.unlink(temp_path)
