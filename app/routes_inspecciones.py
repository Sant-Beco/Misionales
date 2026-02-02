# app/routes_inspecciones.py - VERSIÓN CORREGIDA CON SEGURIDAD

from fastapi import APIRouter, Form, Depends
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app import models
from app.security import get_current_user  # ✅ IMPORTAR FUNCIÓN DE SEGURIDAD
from app.utils_pdf import render_pdf_from_template
from pathlib import Path
from datetime import datetime
import base64
import json
import mimetypes
import secrets

router = APIRouter()

# ===============================
#   DIRECTORIOS PRINCIPALES
# ===============================

BASE_PDF_DIR = Path("app/data/generated_pdfs")
BASE_PDF_DIR.mkdir(parents=True, exist_ok=True)

LEGACY_DIR = BASE_PDF_DIR

LOGO_PATH = Path("app/static/img/incubant.jpg").resolve()

DELETE_AFTER_CONSOLIDATION = True


# ===============================
#   UTILIDADES PDF
# ===============================

def safe_return_pdf(path: Path, filename: str):
    """ Retorna un PDF siempre con tipo correcto y evitando .pdf_ """
    path = path.resolve()

    if not path.exists():
        return Response("PDF no encontrado", status_code=500)

    mime = mimetypes.guess_type(path)[0] or "application/pdf"

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": mime,
        "X-Content-Type-Options": "nosniff",
    }

    return FileResponse(
        path,
        media_type=mime,
        filename=filename,
        headers=headers,
    )


# ===============================
#  NORMALIZACIÓN
# ===============================

def normalize_name(name: str):
    """
    Capitaliza correctamente nombre completo sin recortar.
    """
    if not name:
        return ""
    clean = " ".join(name.strip().split())
    return clean.title()


def normalize_placa(s: str):
    """ Limpia placa y evita valores corruptos """
    if not s:
        return ""
    s = s.upper().strip()
    return "".join([c for c in s if c.isalnum()])[:7]


# ===============================
#   RUTAS DE ARCHIVOS POR USUARIO
# ===============================

def get_user_paths(usuario_id: int):
    """
    Crea y retorna carpetas:
        generated_pdfs/usuarios/<id>/inspecciones
        generated_pdfs/usuarios/<id>/firmas
        generated_pdfs/usuarios/<id>/reportes
    """
    user_base = BASE_PDF_DIR / "usuarios" / str(usuario_id)
    inspecciones_dir = user_base / "inspecciones"
    firmas_dir = user_base / "firmas"
    reportes_dir = user_base / "reportes"

    for p in (user_base, inspecciones_dir, firmas_dir, reportes_dir):
        p.mkdir(parents=True, exist_ok=True)

    return {
        "base": user_base,
        "inspecciones": inspecciones_dir,
        "firmas": firmas_dir,
        "reportes": reportes_dir,
    }


def build_file_uri(path: Path):
    return "file:///" + path.as_posix()


def _guess_firma_path_for_record(r):
    """
    Permite 3 estilos de localización:
    - Nuevo: /usuarios/<id>/firmas/xxx.png
    - Legacy: generated_pdfs/xxx.png
    - Ruta absoluta guardada en DB
    """
    if not getattr(r, "firma_file", None):
        return None

    try:
        u = get_user_paths(r.usuario_id)["firmas"] / r.firma_file
        if u.exists():
            return u
    except:
        pass

    legacy = LEGACY_DIR / r.firma_file
    if legacy.exists():
        return legacy

    direct = Path(r.firma_file)
    if direct.exists():
        return direct

    return None


def prepare_registro(r):
    """
    Prepara campos para PDF y templates.
    """
    try:
        if r.aspectos and r.aspectos not in ["null", "None"]:
            r.aspectos_parsed = json.loads(r.aspectos)
        else:
            r.aspectos_parsed = {}
    except:
        r.aspectos_parsed = {}

    r.firma_path = None
    r.firma_base64 = None
    if r.firma_file:
        try:
            path = _guess_firma_path_for_record(r)
            if path and path.exists():
                r.firma_path = build_file_uri(path)
                try:
                    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
                    r.firma_base64 = f"data:image/png;base64,{encoded}"
                except:
                    pass
        except:
            pass

    return r


# ===============================
#   ENDPOINT SUBMIT - ✅ CORREGIDO
# ===============================

@router.post("/submit")
async def submit_inspeccion(
    # ✅ CAMBIO CRÍTICO: Usuario viene del token, NO del Form
    usuario_actual: models.Usuario = Depends(get_current_user),
    
    # Datos del formulario (ya NO incluye usuario_id)
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
    """
    ✅ SEGURIDAD IMPLEMENTADA:
    - usuario_actual viene de get_current_user (validación de token)
    - El cliente NO puede falsificar el usuario_id
    - Token validado en cada request
    """
    
    db = SessionLocal()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ✅ Usuario ya validado por Depends
    usuario_id = usuario_actual.id
    nombre_conductor = normalize_name(usuario_actual.nombre_visible or usuario_actual.nombre)
    placa = normalize_placa(placa)

    # ============================
    # Validaciones de seguridad
    # ============================
    if not placa or len(placa) < 5:
        return JSONResponse({"error": "Placa inválida"}, status_code=400)

    if not proceso.strip():
        return JSONResponse({"error": "Proceso requerido"}, status_code=400)

    if not desde.strip() or not hasta.strip():
        return JSONResponse({"error": "Origen/destino requerido"}, status_code=400)

    if not firma_dataurl or len(firma_dataurl) < 40:
        return JSONResponse({"error": "Firma inválida"}, status_code=400)

    if modelo and (not modelo.isdigit() or len(modelo) != 4):
        return JSONResponse({"error": "Modelo inválido"}, status_code=400)

    if licencia_num and len(licencia_num) < 6:
        return JSONResponse({"error": "Licencia inválida"}, status_code=400)

    # Aspectos
    try:
        asp_json = json.loads(aspectos)
    except:
        return JSONResponse({"error": "Aspectos inválidos"}, status_code=400)

    if "M" in asp_json.values() and len(observaciones.strip()) < 6:
        return JSONResponse(
            {"error": "Debes agregar observaciones si algún aspecto está en M"},
            status_code=400
        )

    # ============================
    # Crear carpetas del usuario
    # ============================
    user_paths = get_user_paths(usuario_id)

    try:
        # -----------------------------------
        # Guardar firma
        # -----------------------------------
        firma_filename = None
        if firma_dataurl:
            try:
                _, b64 = firma_dataurl.split(",", 1)
                data = base64.b64decode(b64)
                rnd = secrets.token_hex(4)
                firma_filename = f"firma_{timestamp}_{rnd}.png"
                firma_path = user_paths["firmas"] / firma_filename
                firma_path.write_bytes(data)
            except Exception as e:
                print("Error guardando firma:", e)
                firma_filename = None

        # -----------------------------------
        # Guardar registro DB
        # -----------------------------------
        inspeccion = models.Inspeccion(
            fecha=datetime.now(),
            usuario_id=usuario_id,  # ✅ Del token verificado
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

        total = (
            db.query(models.Inspeccion)
            .filter(models.Inspeccion.usuario_id == usuario_id)
            .count()
        )

        # -----------------------------------
        # PDF individual
        # -----------------------------------
        safe_pdf_name = f"inspeccion_{timestamp}.pdf"
        pdf_path = user_paths["inspecciones"] / safe_pdf_name

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

        # -----------------------------------
        # Consolidado a 15
        # -----------------------------------
        if total == 15:
            registros = (
                db.query(models.Inspeccion)
                .filter(models.Inspeccion.usuario_id == usuario_id)
                .order_by(models.Inspeccion.fecha.desc())
                .limit(15)
                .all()
            )
            registros = list(reversed([prepare_registro(r) for r in registros]))

            fecha_desde = registros[0].fecha.strftime("%d-%m-%Y")
            fecha_hasta = registros[-1].fecha.strftime("%d-%m-%Y")

            reporte_filename = (
                f"reporte15_{usuario_id}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
            )
            reporte_path = user_paths["reportes"] / reporte_filename

            render_pdf_from_template(
                "pdf_template_multiple.html",
                {
                    "registros": registros,
                    "fecha": datetime.now().strftime("%d-%m-%Y"),
                    "codigo": "FO-SST-063",
                    "version": "01",
                    "desde": fecha_desde,
                    "hasta": fecha_hasta,
                    "logo_path": build_file_uri(LOGO_PATH),
                },
                output_path=str(reporte_path),
            )

            # Guardar en historial
            hist = models.ReporteInspeccion(
                nombre_conductor=nombre_conductor,
                fecha_reporte=datetime.now(),
                archivo_pdf=str(reporte_path),
                total_incluidas=15,
            )
            db.add(hist)
            db.commit()

            # Borrar inspecciones + firmas
            if DELETE_AFTER_CONSOLIDATION:
                for r in registros:
                    try:
                        if r.firma_file:
                            path = user_paths["firmas"] / r.firma_file
                            if path.exists():
                                path.unlink()
                    except:
                        pass

                    try:
                        db.delete(r)
                    except:
                        pass
                db.commit()

            return safe_return_pdf(reporte_path, reporte_filename)

        return safe_return_pdf(pdf_path, safe_pdf_name)

    finally:
        db.close()


# ===============================
#   ENDPOINT MANUAL REPORTE 15
#   ✅ PROTEGIDO CON AUTH
# ===============================

@router.get("/reporte15/{nombre_conductor}")
async def generar_pdf15(
    nombre_conductor: str,
    usuario_actual: models.Usuario = Depends(get_current_user)  # ✅ Requiere auth
):
    """
    Genera reporte de 15 inspecciones
    ✅ Solo el usuario autenticado puede generar SU reporte
    """
    
    db = SessionLocal()
    nombre_conductor = normalize_name(nombre_conductor)

    try:
        registros = (
            db.query(models.Inspeccion)
            .filter(
                models.Inspeccion.nombre_conductor == nombre_conductor,
                models.Inspeccion.usuario_id == usuario_actual.id  # ✅ Filtro de seguridad
            )
            .order_by(models.Inspeccion.fecha.desc())
            .limit(15)
            .all()
        )

        if not registros:
            return JSONResponse({"mensaje": "No hay inspecciones"}, status_code=404)

        registros = list(reversed([prepare_registro(r) for r in registros]))

        fecha_desde = registros[0].fecha.strftime("%d-%m-%Y")
        fecha_hasta = registros[-1].fecha.strftime("%d-%m-%Y")

        pdf_filename = (
            f"reporte15_{nombre_conductor}_{datetime.now().strftime('%Y%m%d%H%M')}.pdf"
        )

        user_paths = get_user_paths(usuario_actual.id)
        pdf_path = user_paths["reportes"] / pdf_filename

        render_pdf_from_template(
            "pdf_template_multiple.html",
            {
                "registros": registros,
                "fecha": datetime.now().strftime("%d-%m-%Y"),
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