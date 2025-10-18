# app/models.py
from sqlalchemy import Column, Integer, String, DateTime, Text
from datetime import datetime
from app.database import Base

class Inspeccion(Base):
    __tablename__ = "inspecciones"

    id = Column(Integer, primary_key=True, index=True)
    nombre_conductor = Column(String)
    placa = Column(String)
    proceso = Column(String)
    desde = Column(String)
    hasta = Column(String)
    marca = Column(String)
    gasolina = Column(String)
    modelo = Column(String)
    motor = Column(String)
    tipo_vehiculo = Column(String)
    linea = Column(String)
    licencia_num = Column(String)
    licencia_venc = Column(String)
    porte_propiedad = Column(String)
    soat = Column(String)
    certificado_emision = Column(String)
    poliza_seguro = Column(String)
    aspectos = Column(Text)
    observaciones = Column(Text)
    condiciones_optimas = Column(String)
    firma_file = Column(String)
    fecha = Column(DateTime, default=datetime.utcnow)
