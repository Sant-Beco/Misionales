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

# ===============================
#   DIRECTORIOS Y CONFIG
# ===============================

PDF_DIR = Path("app/data/generated_pdfs")
PDF_DIR.mkdir(parents=True, exist_ok=True)

LOGO_PATH = Path("app/static/img/incubant.jpg").resolve()

DELETE_AFTER_CONSOLIDATION = True  # opción B (borrar firmas al consolidar)



# ===============================
#   NORMALIZACIÓN DE NOMBRE
# ===============================

def normalize_name(name: str):
    """
    ✅ SOLO PRIMER NOMBRE
    Normaliza:
      - quita espacios duplicados
      - toma solo la primera palabra
      - capitaliza
        
    Ejemplo: "juan carlos pérez" → "Juan"
    """
    clean = " ".join(name.strip().split())
    parts = clean.split(" ")
    if len(parts) == 0:
        return ""
    return parts[0].capitalize()



# ===============================
#   UTILIDADES DE FIRMA + ASPECTOS
# ===============================

def build_file_uri(path: Path):
    return "file:///" + path.as_posix()


def prepare_registro(r):
    # ---------------------------------------------
    # ✅ ASPECTOS → diccionario seguro
    # ---------------------------------------------
    try:
        if r.aspectos and r.aspectos not in ["null", "None"]:
            r.aspectos_parsed = json.loads(r.aspectos)
        else:
            r.aspectos_parsed = {}
    except:
        r.aspectos_parsed = {}

    # ---------------------------------------------
    # ✅ FIRMA → archivo + base64 fallback
    # ---------------------------------------------
    if r.firma_file:

        # ruta real absoluta (Windows-safe)
        firma_path = (PDF_DIR / r.firma_file).resolve()

        if firma_path.exists():
            # ✅ RUTA file:// válida para WeasyPrint
            r.firma_path = build_file_uri(firma_path)

            # ✅ fallback Base64 SIEMPRE generado
            try:
                encoded = base64.b64encode(firma_path.read_bytes()).decode("utf-8")
                r.firma_base64 = f"data:image/png;base64,{encoded}"
            except:
                r.firma_base64 = None

        else:
            # archivo no existe → intentar base64 desde disco "sin verificar"
            r.firma_path = None
            try:
                encoded = base64.b64encode((PDF_DIR / r.firma_file).read_bytes()).decode("utf-8")
                r.firma_base64 = f"data:image/png;base64,{encoded}"
            except:
                r.firma_base64 = None

    else:
        r.firma_path = None
        r.firma_base64 = None

    return r



# ===============================
#   ENDPOINT: SUBMIT
# ===============================

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
    condiciones_optimas: str = Form("SI"),
):
    db = SessionLocal()
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    # ✅ convertir a PRIMER NOMBRE
    nombre_conductor = normalize_name(nombre_conductor)

    try:
        # =========================================================
        # ✅ GUARDAR FIRMA EN DISCO
        # =========================================================
        firma_filename = None
        if firma_dataurl:
            try:
                _, encoded = firma_dataurl.split(",", 1)
                data = base64.b64decode(encoded)
                firma_filename = f"firma_{timestamp}.png"
                (PDF_DIR / firma_filename).write_bytes(data)
            except:
                firma_filename = None

        # asegurar JSON válido
        if not isinstance(aspectos, str):
            aspectos = "{}"

        # =========================================================
        # ✅ GUARDAR EN BASE DE DATOS
        # =========================================================
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
            firma_file=firma_filename,
        )

        db.add(inspeccion)
        db.commit()
        db.refresh(inspeccion)

        inspeccion = prepare_registro(inspeccion)

        # =========================================================
        # ✅ CONTAR REGISTROS DE ESTE CONDUCTOR
        # =========================================================
        total_inspecciones = (
            db.query(models.Inspeccion)
            .filter(models.Inspeccion.nombre_conductor == nombre_conductor)
            .count()
        )

        # =========================================================
        # ✅ PDF DEL DÍA
        # =========================================================
        pdf_filename = f"inspeccion_{timestamp}.pdf"
        pdf_path = PDF_DIR / pdf_filename

        render_pdf_from_template(
            "pdf_template.html",
            {
                "registro": inspeccion,
                "fecha": datetime.now().strftime("%d - %m - %Y"),
                "codigo": "FO-SST-063",
                "version": "01",
                "logo_path": build_file_uri(LOGO_PATH),
            },
            output_path=str(pdf_path),
        )

        # =========================================================
        # ✅ CONSOLIDADO DE 15 INSPECCIONES
        # =========================================================
        if total_inspecciones >= 15:

            registros = (
                db.query(models.Inspeccion)
                .filter(models.Inspeccion.nombre_conductor == nombre_conductor)
                .order_by(models.Inspeccion.fecha.asc())
                .limit(15)
                .all()
            )

            registros = [prepare_registro(r) for r in registros]

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
                    "logo_path": build_file_uri(LOGO_PATH),
                },
                output_path=str(reporte_path),
            )

            # guardar historial
            reporte = models.ReporteInspeccion(
                nombre_conductor=nombre_conductor,
                fecha_reporte=datetime.now(),
                archivo_pdf=str(reporte_path),
                total_incluidas=15,
            )
            db.add(reporte)
            db.commit()

            # =====================================================
            # ✅ BORRAR INSPECCIONES + FIRMAS
            # =====================================================
            if DELETE_AFTER_CONSOLIDATION:
                for r in registros:

                    # borrar firma física
                    if r.firma_file:
                        firma_path = PDF_DIR / r.firma_file
                        if firma_path.exists():
                            firma_path.unlink()

                    # borrar de la BD
                    db.delete(r)

                db.commit()

            return FileResponse(
                reporte_path, media_type="application/pdf", filename=reporte_filename
            )

        # ✅ PDF individual
        return FileResponse(
            pdf_path, media_type="application/pdf", filename=pdf_filename
        )

    finally:
        db.close()



# ===============================
#   ENDPOINT: CONSOLIDADO MANUAL
# ===============================

@router.get("/reporte15/{nombre_conductor}")
async def generar_pdf15(nombre_conductor: str):

    db = SessionLocal()
    nombre_conductor = normalize_name(nombre_conductor)

    try:
        registros = (
            db.query(models.Inspeccion)
            .filter(models.Inspeccion.nombre_conductor == nombre_conductor)
            .order_by(models.Inspeccion.fecha.asc())
            .limit(15)
            .all()
        )

        if not registros:
            return JSONResponse({"mensaje": "No hay inspecciones"}, status_code=404)

        registros = [prepare_registro(r) for r in registros]

        fecha_desde = registros[0].fecha.strftime("%d - %m - %Y")
        fecha_hasta = registros[-1].fecha.strftime("%d - %m - %Y")

        pdf_filename = (
            f"reporte15_{nombre_conductor}_{datetime.now().strftime('%Y%m%d%H%M')}.pdf"
        )
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
                "logo_path": build_file_uri(LOGO_PATH),
            },
            output_path=str(pdf_path),
        )

        return FileResponse(pdf_path, media_type="application/pdf", filename=pdf_filename)

    finally:
        db.close()


