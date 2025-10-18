from fastapi import APIRouter, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app import models
from app.utils_pdf import render_pdf_from_template
from pathlib import Path
from datetime import datetime
import base64
import json

router = APIRouter()
PDF_DIR = Path("app/data/generated_pdfs")
PDF_DIR.mkdir(parents=True, exist_ok=True)

@router.post("/submit")
async def submit_inspeccion(
    nombre_conductor: str = Form(...),
    placa: str = Form(""),
    proceso: str = Form(""),
    desde: str = Form(""),
    hasta: str = Form(""),
    marca: str = Form(""),
    gasolina: str = Form(""),
    modelo: str = Form(""),
    motor: str = Form(""),
    tipo_vehiculo: str = Form("Moto"),
    linea: str = Form(""),
    licencia_num: str = Form(""),
    licencia_venc: str = Form(""),
    porte_propiedad: str = Form(""),
    soat: str = Form(""),
    certificado_emision: str = Form(""),
    poliza_seguro: str = Form(""),
    aspectos: str = Form("{}"),
    firma_dataurl: str = Form(None),
    observaciones: str = Form(""),
    condiciones_optimas: str = Form("SI")
):
    db = SessionLocal()
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    # Guardar firma (si existe)
    firma_filename = None
    if firma_dataurl:
        try:
            header, encoded = firma_dataurl.split(",", 1)
            data = base64.b64decode(encoded)
            firma_filename = f"firma_{timestamp}.png"
            (PDF_DIR / firma_filename).write_bytes(data)
        except Exception as e:
            print("Error al guardar firma:", e)

    # Crear objeto de inspección
    inspeccion = models.Inspeccion(
        fecha=datetime.now(),
        nombre_conductor=nombre_conductor,
        placa=placa,
        proceso=proceso,
        desde=desde,
        hasta=hasta,
        marca=marca,
        gasolina=gasolina,
        modelo=modelo,
        motor=motor,
        tipo_vehiculo=tipo_vehiculo,
        linea=linea,
        licencia_num=licencia_num,
        licencia_venc=licencia_venc,
        porte_propiedad=porte_propiedad,
        soat=soat,
        certificado_emision=certificado_emision,
        poliza_seguro=poliza_seguro,
        observaciones=observaciones,
        condiciones_optimas=condiciones_optimas,
        firma_file=firma_filename
    )

    # Guardar en base de datos
    db.add(inspeccion)
    db.commit()
    db.refresh(inspeccion)
    db.close()

    # Generar PDF
    html_context = {
        "registro": inspeccion,
        "fecha": datetime.now().strftime("%d - %m - %Y"),
        "codigo": "FO-SST-063",
        "version": "01",
    }

    pdf_filename = f"inspeccion_{timestamp}.pdf"
    pdf_path = PDF_DIR / pdf_filename
    render_pdf_from_template("pdf_template.html", html_context, output_path=str(pdf_path))

    return FileResponse(path=str(pdf_path), media_type="application/pdf", filename=pdf_filename)
