from sqlalchemy import Column, Integer, String, DateTime, Text
from app.database import Base
from datetime import datetime

class Inspeccion(Base):
    __tablename__ = "inspecciones"

    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(DateTime, default=datetime.now)
    nombre_conductor = Column(String(100))
    placa = Column(String(20))
    proceso = Column(String(50))
    desde = Column(String(50))
    hasta = Column(String(50))
    marca = Column(String(50))
    gasolina = Column(String(50))
    modelo = Column(String(20))
    motor = Column(String(50))
    tipo_vehiculo = Column(String(20))
    linea = Column(String(50))
    licencia_num = Column(String(50))
    licencia_venc = Column(String(50))
    porte_propiedad = Column(String(50))
    soat = Column(String(50))
    certificado_emision = Column(String(50))
    poliza_seguro = Column(String(50))
    observaciones = Column(Text)
    condiciones_optimas = Column(String(5))
    firma_file = Column(String(200))

class ReporteInspeccion(Base):
    __tablename__ = "reporte_inspeccion"

    id = Column(Integer, primary_key=True, index=True)
    nombre_conductor = Column(String, index=True)
    fecha_reporte = Column(DateTime, default=datetime.utcnow)
    archivo_pdf = Column(String)
    total_incluidas = Column(Integer, default=15)

