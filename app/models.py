from sqlalchemy import Column, Integer, String, DateTime, Text
from app.database import Base
from datetime import datetime
import json


class Inspeccion(Base):
    __tablename__ = "inspecciones"

    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(DateTime, default=datetime.now)
    nombre_conductor = Column(String(100))
    placa = Column(String(50))
    proceso = Column(String(100))
    desde = Column(String(100))
    hasta = Column(String(100))
    marca = Column(String(100))
    gasolina = Column(String(50))
    modelo = Column(String(50))
    motor = Column(String(50))
    tipo_vehiculo = Column(String(50))
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
    aspectos = Column(Text, nullable=True)  # JSON con valores B/M

    @property
    def aspectos_dict(self):
        """
        Devuelve el JSON de aspectos como diccionario.
        Si no hay datos o el formato es incorrecto, devuelve un diccionario vacío.
        """
        try:
            return json.loads(self.aspectos) if self.aspectos else {}
        except Exception:
            return {}


class ReporteInspeccion(Base):
    __tablename__ = "reportes_inspeccion"

    id = Column(Integer, primary_key=True, index=True)
    nombre_conductor = Column(String(100))
    fecha_reporte = Column(DateTime, default=datetime.now)
    archivo_pdf = Column(String(255))
    total_incluidas = Column(Integer, default=15)



