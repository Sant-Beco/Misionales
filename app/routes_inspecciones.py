# app/routes/routes_inspecciones.py

from fastapi import APIRouter, Form
from fastapi.responses import FileResponse, JSONResponse
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

# Cambia a False si deseas conservar las inspecciones después de generar el consolidado
DELETE_AFTER_CONSOLIDATION = True


# ✅ Crea ruta absoluta tipo file:/// para WeasyPrint
def build_file_uri(path: Path):
    return "file:///" + path.as_posix()


# ✅ Limpia y prepara un registro para el PDF
def prepare_registro(r):
    # 1️⃣ Parsear JSON de aspectos
    try:
        if not r.aspectos or r.aspectos in ["null", "None", None]:
            r.aspectos_parsed = {}
        else:
            r.aspectos_parsed = json.loads(r.aspectos)
    except:
        r.aspectos_parsed = {}

    # 2️⃣ Validar existencia de firma
    if r.firma_file:
        firma_path = PDF_DIR / r.firma_file
        r.firma_path = build_file_uri(firma_path) if firma_path.exists() else None
    else:
        r.firma_path = None

    return r


# ✅ SUBMIT DE INSPECCIÓN (SE GENERA EL INDIVIDUAL + ACUMULA PARA CONSOLIDADO)
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

    try:
        # ✅ GUARDAR FIRMA
        firma_filename = None
        if firma_dataurl:
            try:
                _, encoded = firma_dataurl.split(",", 1)
                data = base64.b64decode(encoded)
                firma_filename = f"firma_{timestamp}.png"
                (PDF_DIR / firma_filename).write_bytes(data)
            except Exception as e:
                print("⚠️ Error guardando firma:", e)

        # ✅ Validar JSON básico
        if not isinstance(aspectos, str):
            aspectos = "{}"

        # ✅ GUARDAR EN BD
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
            aspectos=aspectos,
            observaciones=observaciones,
            condiciones_optimas=condiciones_optimas,
            firma_file=firma_filename
        )

        db.add(inspeccion)
        db.commit()
        db.refresh(inspeccion)

        # ✅ Preparar datos para PDF individual
        inspeccion = prepare_registro(inspeccion)

        # ✅ Contar inspecciones del conductor
        total_inspecciones = db.query(models.Inspeccion).filter(
            models.Inspeccion.nombre_conductor == nombre_conductor
        ).count()

        # ✅ Generar PDF INDIVIDUAL
        pdf_filename = f"inspeccion_{timestamp}.pdf"
        pdf_path = PDF_DIR / pdf_filename

        try:
            render_pdf_from_template(
                "pdf_template.html",
                {
                    "registro": inspeccion,
                    "fecha": datetime.now().strftime("%d - %m - %Y"),
                    "codigo": "FO-SST-063",
                    "version": "01",
                },
                output_path=str(pdf_path)
            )
        except Exception as e:
            print("❌ Error generando PDF individual:", e)
            return JSONResponse({"error": "Error generando PDF individual"}, status_code=500)

        # ✅ SI YA TIENE 15 → GENERAR CONSOLIDADO
        if total_inspecciones >= 15:
            registros = db.query(models.Inspeccion).filter(
                models.Inspeccion.nombre_conductor == nombre_conductor
            ).order_by(models.Inspeccion.fecha.asc()).limit(15).all()

            registros = [prepare_registro(r) for r in registros]

            fecha_desde = registros[0].fecha.strftime("%d - %m - %Y")
            fecha_hasta = registros[-1].fecha.strftime("%d - %m - %Y")

            reporte_filename = f"reporte15_{nombre_conductor}_{datetime.now().strftime('%Y%m%d%H%M')}.pdf"
            reporte_path = PDF_DIR / reporte_filename

            try:
                render_pdf_from_template(
                    "pdf_template_multiple.html",
                    {
                        "registros": registros,
                        "fecha": datetime.now().strftime("%d - %m - %Y"),
                        "codigo": "FO-SST-063",
                        "version": "01",
                        "desde": fecha_desde,
                        "hasta": fecha_hasta,
                    },
                    output_path=str(reporte_path)
                )
            except Exception as e:
                print("❌ Error generando PDF consolidado:", e)
                return JSONResponse({"error": "Error generando PDF consolidado"}, status_code=500)

            # ✅ Guardar reporte en BD
            reporte = models.ReporteInspeccion(
                nombre_conductor=nombre_conductor,
                fecha_reporte=datetime.now(),
                archivo_pdf=str(reporte_path),
                total_incluidas=15
            )
            db.add(reporte)
            db.commit()

            # ✅ Borrar inspecciones después del consolidado
            if DELETE_AFTER_CONSOLIDATION:
                for r in registros:
                    db.delete(r)
                db.commit()

            return FileResponse(
                reporte_path,
                media_type="application/pdf",
                filename=reporte_filename
            )

        # ✅ Retorno normal
        return FileResponse(pdf_path, media_type="application/pdf", filename=pdf_filename)

    finally:
        db.close()


# ✅ GENERAR CONSOLIDADO MANUALMENTE
@router.get("/reporte15/{nombre_conductor}")
async def generar_pdf15(nombre_conductor: str):

    db = SessionLocal()
    try:
        registros = db.query(models.Inspeccion).filter(
            models.Inspeccion.nombre_conductor == nombre_conductor
        ).order_by(models.Inspeccion.fecha.asc()).limit(15).all()

        if not registros:
            return JSONResponse({"mensaje": "No hay inspecciones para este conductor"}, status_code=404)

        registros = [prepare_registro(r) for r in registros]

        fecha_desde = registros[0].fecha.strftime("%d - %m - %Y")
        fecha_hasta = registros[-1].fecha.strftime("%d - %m - %Y")

        pdf_filename = f"reporte15_{nombre_conductor}_{datetime.now().strftime('%Y%m%d%H%M')}.pdf"
        pdf_path = PDF_DIR / pdf_filename

        render_pdf_from_template(
            "pdf_template_multiple.html",
            {
                "registros": registros,
                "fecha": datetime.now().strftime("%d - %m - %Y"),
                "codigo": "FO-SST-063",
                "version": "01",
                "desde": fecha_desde,
                "hasta": fecha_hasta,
            },
            output_path=str(pdf_path)
        )

        return FileResponse(pdf_path, media_type="application/pdf", filename=pdf_filename)

    finally:
        db.close()

