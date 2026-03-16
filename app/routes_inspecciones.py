# app/routes_inspecciones.py - VERSIÓN CORREGIDA CON RUTAS DE FIRMA ARREGLADAS

from fastapi import APIRouter, Form, Depends, Request
from fastapi.responses import FileResponse, JSONResponse, Response, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import SessionLocal, get_db
from app import models
from app.security import get_current_user
from app.utils_pdf import render_pdf_from_template
from pathlib import Path
from datetime import datetime
import base64
import json
import mimetypes
import secrets

router = APIRouter()

# Templates — mismo directorio que usa main.py
_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

# ===============================
#   DIRECTORIOS PRINCIPALES
# ===============================

# ✅ FIX: Rutas absolutas basadas en la ubicación de este archivo
#    Evita roturas cuando uvicorn no corre desde la raíz del proyecto
_HERE = Path(__file__).resolve().parent

BASE_PDF_DIR = _HERE / "data" / "generated_pdfs"
BASE_PDF_DIR.mkdir(parents=True, exist_ok=True)

# Directorio de firmas separado
BASE_FIRMAS_DIR = _HERE / "data" / "firmas"
BASE_FIRMAS_DIR.mkdir(parents=True, exist_ok=True)

LEGACY_DIR = BASE_PDF_DIR

# ✅ FIX: logotipo_01.png (lowercase, archivo correcto)
LOGO_PATH = (_HERE / "static" / "img" / "logotipo_01.png").resolve()

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
#   RUTAS DE ARCHIVOS POR USUARIO - ✅ CORREGIDO
# ===============================

def get_user_paths(usuario_id: int):
    """
    Crea y retorna carpetas:
        generated_pdfs/usuarios/<id>/inspecciones
        generated_pdfs/usuarios/<id>/reportes
        firmas/usuarios/<id>/  ← ✅ CORREGIDO: firmas en directorio separado
    """
    # PDFs en generated_pdfs
    user_pdf_base = BASE_PDF_DIR / "usuarios" / str(usuario_id)
    inspecciones_dir = user_pdf_base / "inspecciones"
    reportes_dir = user_pdf_base / "reportes"
    
    # ✅ Firmas en directorio separado
    user_firmas_dir = BASE_FIRMAS_DIR / "usuarios" / str(usuario_id)

    # Crear directorios
    for p in (user_pdf_base, inspecciones_dir, reportes_dir, user_firmas_dir):
        p.mkdir(parents=True, exist_ok=True)

    return {
        "base": user_pdf_base,
        "inspecciones": inspecciones_dir,
        "firmas": user_firmas_dir,  # ✅ Ahora apunta a app/data/firmas/usuarios/<id>/
        "reportes": reportes_dir,
    }


def build_file_uri(path: Path):
    return "file:///" + path.as_posix()


def _guess_firma_path_for_record(r):
    """
    Busca firma en múltiples ubicaciones para compatibilidad
    """
    if not getattr(r, "firma_file", None):
        return None

    # ✅ PRIORIDAD 1: Nueva estructura (firmas separadas)
    try:
        nueva = BASE_FIRMAS_DIR / "usuarios" / str(r.usuario_id) / r.firma_file
        if nueva.exists():
            return nueva
    except:
        pass

    # PRIORIDAD 2: Estructura con duplicación (legacy de tus firmas actuales)
    try:
        duplicada = BASE_FIRMAS_DIR / "usuarios" / str(r.usuario_id) / "firmas" / r.firma_file
        if duplicada.exists():
            return duplicada
    except:
        pass

    # PRIORIDAD 3: Legacy en generated_pdfs
    try:
        legacy_user = BASE_PDF_DIR / "usuarios" / str(r.usuario_id) / "firmas" / r.firma_file
        if legacy_user.exists():
            return legacy_user
    except:
        pass

    # PRIORIDAD 4: Legacy root
    legacy = LEGACY_DIR / r.firma_file
    if legacy.exists():
        return legacy

    # PRIORIDAD 5: Ruta directa
    direct = Path(r.firma_file)
    if direct.exists():
        return direct

    return None


# Listas de aspectos por tipo de vehículo — fuente única de verdad
ASPECTOS_MOTO = [
    "Estado de llantas y presión de aire",
    "Encendido eléctrico y de crank",
    "Luces y pito",
    "Espejos retrovisores",
    "Manijas de freno y clutch",
    "Sistema de frenos",
    "Estado de freno de disco",
    "Nivel de líquido de freno",
    "Revisión sistema tablero",
    "Fugas de combustible y/o aceites",
    "Kit de arrastre",
    "Estado de suspensión",
    "Nivel de aceites",
]

ASPECTOS_CARRO = [
    "Estado de llantas y presión de aire",
    "Funcionamiento de luces y bocina",
    "Espejos retrovisores",
    "Sistema de frenos",
    "Nivel de líquido de freno",
    "Nivel de aceites",
    "Nivel de líquido refrigerante",
    "Fugas de combustible y/o aceites",
    "Revisión tablero e instrumentos",
    "Funcionamiento de limpiaparabrisas",
    "Estado de correas y mangueras",
    "Funcionamiento de puertas y seguros",
    "Estado de la dirección",
    "Cinturón de seguridad",
    "Estado de la carrocería / estructura",
]

ASPECTOS_POR_TIPO = {
    "Moto":  ASPECTOS_MOTO,
    "Carro": ASPECTOS_CARRO,
}


def prepare_registro(r):
    """
    Prepara campos para PDF y templates:
    - Normaliza aspectos_parsed al formato simple {"1": "B"/"M"}
      compatible con el viejo formato {"1":"B"} y el nuevo {"1":{"valor":"B","label":"..."}}
    - Inyecta aspectos_lista según tipo_vehiculo para que el template
      muestre la lista correcta (Moto o Carro) sin hardcodearla
    - Carga firma como base64 para WeasyPrint
    """
    # ── Parsear y normalizar aspectos ──────────────────────────────
    raw_parsed = {}
    try:
        if r.aspectos and r.aspectos not in ["null", "None"]:
            raw_parsed = json.loads(r.aspectos)
    except Exception:
        raw_parsed = {}

    # Normalizar: {"1": {"valor":"B","label":"..."}} → {"1": "B"}
    normalized = {}
    for k, v in raw_parsed.items():
        if isinstance(v, dict):
            normalized[k] = v.get("valor", "")
        else:
            normalized[k] = v  # formato viejo, ya es string

    r.aspectos_parsed = normalized

    # ── Lista de aspectos para el template ─────────────────────────
    tipo = getattr(r, "tipo_vehiculo", None) or "Moto"
    r.aspectos_lista = ASPECTOS_POR_TIPO.get(tipo, ASPECTOS_MOTO)

    # ── Título según tipo ──────────────────────────────────────────
    titulos = {
        "Moto":  "Inspección Pre Operacional Motocicleta",
        "Carro": "Inspección Pre Operacional Automóvil",
    }
    r.titulo_tipo = titulos.get(tipo, "Inspección Pre Operacional")

    r.firma_path = None
    r.firma_base64 = None
    if r.firma_file:
        try:
            path = _guess_firma_path_for_record(r)
            if path and path.exists():
                r.firma_path = build_file_uri(path)
                try:
                    # ✅ Cargar como base64 para WeasyPrint
                    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
                    r.firma_base64 = f"data:image/png;base64,{encoded}"
                except Exception as e:
                    print(f"⚠️ Error codificando firma: {e}")
                    pass
        except Exception as e:
            print(f"⚠️ Error buscando firma: {e}")
            pass

    return r


# ===============================
#   ENDPOINT SUBMIT - ✅ SEGURO
# ===============================

@router.post("/submit")
async def submit_inspeccion(
    usuario_actual: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),  # ✅ FIX: sin connection leak
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
    # ✅ FIX: db ya inyectada por FastAPI como dependency — sin connection leak
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    usuario_id = usuario_actual.id
    nombre_conductor = normalize_name(usuario_actual.nombre_visible or usuario_actual.nombre)
    placa = normalize_placa(placa)

    # Validaciones
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

    try:
        asp_json = json.loads(aspectos)
    except:
        return JSONResponse({"error": "Aspectos inválidos"}, status_code=400)

    # ✅ Compatibilidad: formato nuevo {"1": {"valor":"M","label":"..."}} y viejo {"1": "M"}
    def _asp_valor(v):
        return v.get("valor") if isinstance(v, dict) else v

    if "M" in [_asp_valor(v) for v in asp_json.values()] and len(observaciones.strip()) < 6:
        return JSONResponse(
            {"error": "Debes agregar observaciones si algún aspecto está en M"},
            status_code=400
        )

    user_paths = get_user_paths(usuario_id)

    try:
        # Guardar firma
        firma_filename = None
        if firma_dataurl:
            try:
                _, b64 = firma_dataurl.split(",", 1)
                data = base64.b64decode(b64)
                rnd = secrets.token_hex(4)
                firma_filename = f"firma_{timestamp}_{rnd}.png"
                firma_path = user_paths["firmas"] / firma_filename  # ✅ Ruta corregida
                firma_path.write_bytes(data)
                print(f"✅ Firma guardada en: {firma_path}")
            except Exception as e:
                print(f"❌ Error guardando firma: {e}")
                firma_filename = None

        # Guardar registro DB
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

        # ── Advertencia licencia vencida ──────────────────────────────
        _licencia_advertencia = None
        if licencia_venc:
            try:
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%Y"):
                    try:
                        from datetime import datetime as _dt
                        _venc = _dt.strptime(licencia_venc.strip(), fmt)
                        if _venc.date() < _dt.now().date():
                            _licencia_advertencia = f"⚠️ Licencia de conducción vencida desde {licencia_venc}"
                        break
                    except ValueError:
                        continue
            except Exception:
                pass

        total = (
            db.query(models.Inspeccion)
            .filter(models.Inspeccion.usuario_id == usuario_id)
            .count()
        )

        # PDF individual
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
                # ✅ Lista correcta según tipo_vehiculo para el template
                "aspectos_lista": inspeccion.aspectos_lista,
                "titulo_tipo": inspeccion.titulo_tipo,
            },
            output_path=str(pdf_path),
        )

        # Consolidado a 15
        if total == 15:
            registros = (
                db.query(models.Inspeccion)
                .filter(models.Inspeccion.usuario_id == usuario_id)
                .order_by(models.Inspeccion.fecha.desc())
                .limit(15)
                .all()
            )
            
            # ✅ Preparar TODOS los registros
            registros = list(reversed([prepare_registro(r) for r in registros]))

            fecha_desde = registros[0].fecha.strftime("%d-%m-%Y")
            fecha_hasta = registros[-1].fecha.strftime("%d-%m-%Y")

            reporte_filename = (
                f"reporte15_{usuario_id}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
            )
            reporte_path = user_paths["reportes"] / reporte_filename

            # ✅ FIX #6: generar PDF ANTES de tocar la BD
            # Si render_pdf_from_template falla, la excepción sube y
            # no se llega nunca al delete — los datos quedan intactos
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
                    # ✅ Lista y título según tipo del primer registro
                    "aspectos_lista": registros[0].aspectos_lista,
                    "titulo_tipo": registros[0].titulo_tipo,
                },
                output_path=str(reporte_path),
            )

            # ✅ Verificar que el PDF existe y tiene contenido antes de borrar BD
            if not reporte_path.exists() or reporte_path.stat().st_size < 1000:
                raise RuntimeError(f"PDF consolidado inválido: {reporte_path}")

            # Solo si el PDF es válido → guardar historial
            hist = models.ReporteInspeccion(
                nombre_conductor=nombre_conductor,
                fecha_reporte=datetime.now(),
                archivo_pdf=str(reporte_path),
                total_incluidas=15,
            )
            db.add(hist)
            db.commit()

            # Solo si el PDF es válido → borrar inspecciones + firmas
            if DELETE_AFTER_CONSOLIDATION:
                for r in registros:
                    try:
                        if r.firma_file:
                            path = _guess_firma_path_for_record(r)
                            if path and path.exists():
                                path.unlink()
                                print(f"🗑️ Firma eliminada: {path}")
                    except Exception as e:
                        print(f"⚠️ Error eliminando firma: {e}")

                    try:
                        db.delete(r)
                    except Exception as e:
                        print(f"⚠️ Error eliminando registro: {e}")
                        
                db.commit()

            return safe_return_pdf(reporte_path, reporte_filename)

        # Construir respuesta con advertencias en header
        _pdf_response = safe_return_pdf(pdf_path, safe_pdf_name)
        if _licencia_advertencia:
            from urllib.parse import quote
            _pdf_response.headers["X-Advertencias"] = quote(_licencia_advertencia)
            _pdf_response.headers["Access-Control-Expose-Headers"] = "X-Advertencias"
        return _pdf_response

    except Exception:
        raise  # FastAPI devuelve HTTP 500 automáticamente


# ===============================
#   ENDPOINT MANUAL REPORTE 15
# ===============================

@router.get("/reporte15/{nombre_conductor}")
async def generar_pdf15(
    nombre_conductor: str,
    usuario_actual: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # ✅ FIX: db inyectada por FastAPI
    nombre_conductor = normalize_name(nombre_conductor)

    try:
        registros = (
            db.query(models.Inspeccion)
            .filter(
                models.Inspeccion.nombre_conductor == nombre_conductor,
                models.Inspeccion.usuario_id == usuario_actual.id
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
                # ✅ Lista y título según tipo del primer registro
                "aspectos_lista": registros[0].aspectos_lista,
                "titulo_tipo": registros[0].titulo_tipo,
            },
            output_path=str(pdf_path),
        )

        return safe_return_pdf(pdf_path, pdf_filename)

    except Exception:
        raise  # FastAPI devuelve HTTP 500 automáticamente

# ==========================================================
#   RUTA: MIS INSPECCIONES (historial del conductor)
# ==========================================================

@router.get("/mis-inspecciones", response_class=HTMLResponse)
async def mis_inspecciones(
    request: Request,
    usuario_actual: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Muestra el historial de inspecciones del conductor autenticado.
    Sirve el template lista_inspecciones.html con sus KPIs y tabla.
    """
    nombre_conductor = normalize_name(
        usuario_actual.nombre_visible or usuario_actual.nombre
    )

    registros = (
        db.query(models.Inspeccion)
        .filter(models.Inspeccion.nombre_conductor == nombre_conductor)
        .order_by(models.Inspeccion.fecha.asc())
        .all()
    )

    return _TEMPLATES.TemplateResponse(
        "lista_inspecciones.html",
        {
            "request":           request,
            "nombre_conductor":  nombre_conductor,
            "registros":         registros,
            "puede_generar_pdf15": len(registros) >= 15,
        },
    )