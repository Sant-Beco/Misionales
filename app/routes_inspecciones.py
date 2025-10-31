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

# Si deseas conservar los registros después de consolidar, pon False.
DELETE_AFTER_CONSOLIDATION = True


# ✅ Función auxiliar para convertir rutas a formato compatible con WeasyPrint
def build_file_uri(path: Path):
    return "file:///" + path.as_posix()


# ✅ SUBMIT DE INSPECCIÓN INDIVIDUAL
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

        # ✅ GUARDAR INSPECCIÓN EN DB
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
        try:
            inspeccion.aspectos_parsed = json.loads(inspeccion.aspectos or "{}")
        except:
            inspeccion.aspectos_parsed = {}

        inspeccion.firma_path = (
            build_file_uri(PDF_DIR / inspeccion.firma_file)
            if inspeccion.firma_file else None
        )

        # ✅ Contar registros del conductor
        total_inspecciones = db.query(models.Inspeccion).filter(
            models.Inspeccion.nombre_conductor == nombre_conductor
        ).count()

        # ✅ Generar PDF INDIVIDUAL
        pdf_filename = f"inspeccion_{timestamp}.pdf"
        pdf_path = PDF_DIR / pdf_filename
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

        print(f"✅ PDF individual generado: {pdf_filename}")

        # ✅ SI YA TIENE 15 → GENERAR CONSOLIDADO
        if total_inspecciones >= 15:
            registros = db.query(models.Inspeccion).filter(
                models.Inspeccion.nombre_conductor == nombre_conductor
            ).order_by(models.Inspeccion.fecha.asc()).limit(15).all()

            if registros:
                # ✅ Preparar cada registro para PDF consolidado
                for r in registros:
                    try:
                        r.aspectos_parsed = json.loads(r.aspectos or "{}")
                    except:
                        r.aspectos_parsed = {}
                    r.firma_path = (
                        build_file_uri(PDF_DIR / r.firma_file)
                        if r.firma_file else None
                    )

                fecha_desde = registros[0].fecha.strftime("%d - %m - %Y")
                fecha_hasta = registros[-1].fecha.strftime("%d - %m - %Y")

                reporte_filename = (
                    f"reporte15_{nombre_conductor}_{datetime.now().strftime('%Y%m%d%H%M')}.pdf"
                )
                reporte_path = PDF_DIR / reporte_filename

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

                print(f"📘 Reporte consolidado generado: {reporte_filename}")

                # ✅ Registrar reporte consolidado
                reporte = models.ReporteInspeccion(
                    nombre_conductor=nombre_conductor,
                    fecha_reporte=datetime.now(),
                    archivo_pdf=str(reporte_path),
                    total_incluidas=15
                )
                db.add(reporte)
                db.commit()

                # ✅ BORRAR O NO BORRAR LAS 15 INSPECCIONES
                if DELETE_AFTER_CONSOLIDATION:
                    for r in registros:
                        db.delete(r)
                    db.commit()

                return FileResponse(
                    reporte_path,
                    media_type="application/pdf",
                    filename=reporte_filename
                )

        # ✅ Retorno cuando NO se consolida
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=pdf_filename
        )

    finally:
        try:
            db.close()
        except:
            pass


# ✅ Endpoint manual para generar consolidado
@router.get("/reporte15/{nombre_conductor}")
async def generar_pdf15(nombre_conductor: str):

    db = SessionLocal()
    try:
        registros = db.query(models.Inspeccion).filter(
            models.Inspeccion.nombre_conductor == nombre_conductor
        ).order_by(models.Inspeccion.fecha.asc()).limit(15).all()

        if not registros:
            return JSONResponse({"mensaje": "No hay inspecciones para este conductor"}, status_code=404)

        # ✅ Preparar registros
        for r in registros:
            try:
                r.aspectos_parsed = json.loads(r.aspectos or "{}")
            except:
                r.aspectos_parsed = {}

            r.firma_path = (
                build_file_uri(PDF_DIR / r.firma_file)
                if r.firma_file else None
            )

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
        try:
            db.close()
        except:
            pass

