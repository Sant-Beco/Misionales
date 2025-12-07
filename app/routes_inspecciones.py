# app/routes_inspecciones.py

from fastapi import APIRouter, Form
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app import models
from app.utils_pdf import render_pdf_from_template
from pathlib import Path
from datetime import datetime
import base64
import json
import mimetypes

router = APIRouter()

# ===============================
#   DIRECTORIOS Y CONFIG
# ===============================

PDF_DIR = Path("app/data/generated_pdfs")
PDF_DIR.mkdir(parents=True, exist_ok=True)

LOGO_PATH = Path("app/static/img/incubant.jpg").resolve()

DELETE_AFTER_CONSOLIDATION = True  # borrar inspecciones al consolidar


# ===============================
#   FIX — RETORNAR PDF CORRECTO
# ===============================

def safe_return_pdf(path: Path, filename: str):
    """
    Retorna un PDF siempre con la extensión correcta,
    evitando que el navegador renombre como .pdf_ u otros.
    """
    path = path.resolve()

    if not path.exists():
        return Response("PDF no encontrado", status_code=500)

    mime = mimetypes.guess_type(path)[0] or "application/pdf"

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": mime,
        "X-Content-Type-Options": "nosniff"
    }

    return FileResponse(
        path,
        media_type=mime,
        filename=filename,
        headers=headers
    )


# ===============================
#   NORMALIZACIÓN DE NOMBRE
# ===============================

def normalize_name(name: str):
    if not name:
        return ""
    clean = " ".join(name.strip().split())
    return clean.title()

def normalize_placa(s: str):
    """ Normaliza placa para evitar datos corruptos enviados al backend. """
    if not s:
        return ""
    s = s.upper().strip()
    return "".join([c for c in s if c.isalnum()])[:7]



# ===============================
#   UTILIDADES
# ===============================

def build_file_uri(path: Path):
    return "file:///" + path.as_posix()


def prepare_registro(r):
    # ASPECTOS
    try:
        if r.aspectos and r.aspectos not in ["null", "None"]:
            r.aspectos_parsed = json.loads(r.aspectos)
        else:
            r.aspectos_parsed = {}
    except:
        r.aspectos_parsed = {}

    # FIRMA
    if r.firma_file:
        firma_path = (PDF_DIR / r.firma_file)

        if firma_path.exists() and firma_path.is_file():
            try:
                r.firma_path = build_file_uri(firma_path)
                encoded = base64.b64encode(firma_path.read_bytes()).decode("utf-8")
                r.firma_base64 = f"data:image/png;base64,{encoded}"
            except Exception as e:
                print("Error leyendo firma:", e)
                r.firma_path = None
                r.firma_base64 = None
        else:
            r.firma_path = None
            r.firma_base64 = None
    else:
        r.firma_path = None
        r.firma_base64 = None

    return r


# ===============================
#   ENDPOINT SUBMIT
# ===============================

@router.post("/submit")
async def submit_inspeccion(
    usuario_id: int = Form(...),
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

    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not usuario:
        return JSONResponse({"error": "Usuario no encontrado"}, status_code=404)

    nombre_conductor = normalize_name(usuario.nombre_visible or usuario.nombre)
    placa = normalize_placa(placa)

    # ================================
    # VALIDACIÓN BACKEND (ANTI BYPASS)
    # ================================
    if not placa or len(placa) < 5:
        return JSONResponse({"error": "Placa inválida"}, status_code=400)

    if proceso.strip() == "":
        return JSONResponse({"error": "Proceso requerido"}, status_code=400)

    if desde.strip() == "" or hasta.strip() == "":
        return JSONResponse({"error": "Origen/destino requerido"}, status_code=400)

    if not firma_dataurl or len(firma_dataurl) < 40:
        return JSONResponse({"error": "Firma no válida"}, status_code=400)
    
    # ================================
    # VALIDACIÓN EXTRA — COHERENCIA CON FRONTEND
    # ================================

    # Modelo debe ser año de 4 dígitos
    if not modelo.isdigit() or len(modelo) != 4:
        return JSONResponse({"error": "Modelo inválido (año requerido)"}, status_code=400)

    # Número de licencia mínimo 6 caracteres
    if len(licencia_num.strip()) < 6:
        return JSONResponse({"error": "Número de licencia inválido"}, status_code=400)

    # Validar JSON de aspectos
    try:
        asp_json = json.loads(aspectos)
    except:
        return JSONResponse({"error": "Aspectos inválidos"}, status_code=400)

    # Observaciones obligatorias si hay M
    if "M" in asp_json.values() and len(observaciones.strip()) < 6:
        return JSONResponse(
            {"error": "Debes agregar observaciones si algún aspecto está en M"},
            status_code=400
        )




    try:
        # =======================================
        # GUARDAR FIRMA
        # =======================================
        firma_filename = None
        if firma_dataurl:
            try:
                _, encoded = firma_dataurl.split(",", 1)
                data = base64.b64decode(encoded)
                firma_filename = f"firma_{timestamp}.png"
                path_firma = (PDF_DIR / firma_filename)
                path_firma.write_bytes(data)
            except:
                firma_filename = None

        # Parse seguro de aspectos
        if not isinstance(aspectos, str):
            aspectos = "{}"

        try:
            json.loads(aspectos)
        except:
            aspectos = "{}"

        # =======================================
        # GUARDAR EN BD
        # =======================================
        inspeccion = models.Inspeccion(
            fecha=datetime.now(),
            usuario_id=usuario_id,
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

        # =======================================
        # TOTAL INSPECCIONES DEL USUARIO
        # =======================================
        total_inspecciones = (
            db.query(models.Inspeccion)
            .filter(models.Inspeccion.usuario_id == usuario_id)
            .count()
        )

        # =======================================
        # PDF INDIVIDUAL
        # =======================================
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

        # =======================================
        # CONSOLIDADO EXACTAMENTE A 15
        # =======================================
        if total_inspecciones == 15:
            registros = (
                db.query(models.Inspeccion)
                .filter(models.Inspeccion.usuario_id == usuario_id)
                .order_by(models.Inspeccion.fecha.desc())
                .limit(15)
                .all()
            )

            registros = list(reversed([prepare_registro(r) for r in registros]))

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

            # GUARDAR HISTORIAL
            reporte = models.ReporteInspeccion(
                nombre_conductor=nombre_conductor,
                fecha_reporte=datetime.now(),
                archivo_pdf=str(reporte_path),
                total_incluidas=15,
            )
            db.add(reporte)
            db.commit()

            # BORRAR INSPECCIONES
            if DELETE_AFTER_CONSOLIDATION:
                for r in registros:
                    try:
                        if r.firma_file:
                            fpath = PDF_DIR / r.firma_file
                            if fpath.exists():
                                fpath.unlink()
                    except Exception as e:
                        print("⚠ Error borrando firma:", e)
                    try:
                        db.delete(r)
                    except:
                        pass
                db.commit()

            return safe_return_pdf(reporte_path, reporte_filename)

        # =======================================
        # RETORNAR PDF INDIVIDUAL
        # =======================================
        return safe_return_pdf(pdf_path, pdf_filename)

    finally:
        db.close()


# ===============================
#   ENDPOINT MANUAL
# ===============================

@router.get("/reporte15/{nombre_conductor}")
async def generar_pdf15(nombre_conductor: str):

    db = SessionLocal()
    nombre_conductor = normalize_name(nombre_conductor)

    try:
        registros = (
            db.query(models.Inspeccion)
            .filter(models.Inspeccion.nombre_conductor == nombre_conductor)
            .order_by(models.Inspeccion.fecha.desc())
            .limit(15)
            .all()
        )

        if not registros:
            return JSONResponse({"mensaje": "No hay inspecciones"}, status_code=404)

        registros = list(reversed([prepare_registro(r) for r in registros]))

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

        return safe_return_pdf(pdf_path, pdf_filename)

    finally:
        db.close()
