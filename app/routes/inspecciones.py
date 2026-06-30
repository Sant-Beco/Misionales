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
 
# ✅ CORREGIDO: templates está en app/templates, no en app/routes/templates
# Path(__file__).resolve().parent = app/routes/
# Path(__file__).resolve().parent.parent = app/
# Entonces: app/ + "templates" = app/templates ✅
_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
 
# ===============================
#   DIRECTORIOS PRINCIPALES
# ===============================
 
# ✅ FIX: Rutas absolutas basadas en la ubicación de este archivo
#    Evita roturas cuando uvicorn no corre desde la raíz del proyecto
_HERE = Path(__file__).resolve().parent.parent  # app/
 
BASE_PDF_DIR = _HERE / "data" / "generated_pdfs"
BASE_PDF_DIR.mkdir(parents=True, exist_ok=True)
 
# Directorio de firmas separado
BASE_FIRMAS_DIR = _HERE / "data" / "firmas"
BASE_FIRMAS_DIR.mkdir(parents=True, exist_ok=True)
 
LEGACY_DIR = BASE_PDF_DIR
 
# ✅ FIX: logotipo_01.png (lowercase, archivo correcto)
LOGO_PATH = (_HERE / "static" / "img" / "logotipo_01.png").resolve()
 
DELETE_AFTER_CONSOLIDATION = False  # ✅ Mantener inspecciones después de consolidar
 
 
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
    "Llantas — estado y presión de aire (delantera y trasera)",
    "Llanta de repuesto o kit de pinchazo",
    "Encendido eléctrico y arranque (crank)",
    "Faro delantero — enciende y funciona correctamente",
    "Luces traseras y stop — encienden y funcionan correctamente",
    "Direccionales — encienden y funcionan correctamente",
    "Pito / bocina — funciona correctamente",
    "Espejos retrovisores — estado y ajuste",
    "Manijas de freno y clutch — estado y recorrido",
    "Sistema de frenos delantero — estado del frenado",
    "Sistema de frenos trasero — estado del frenado",
    "Nivel de líquido de freno",
    "Cadena o correa de transmisión — estado y tensión",
    "Estado de suspensión delantera y trasera",
    "Fugas de combustible y/o aceites",
    "Nivel de aceite de motor",
    "Revisión tablero e instrumentos",
    "Kit de arrastre (herramienta básica)"
]
 
ASPECTOS_CARRO = [
    "Llantas — estado y presión de aire (4 ruedas)",
    "Llanta de repuesto — estado y presión de aire",
    "Luces altas y bajas — encienden y funcionan correctamente",
    "Luces de stop — encienden y funcionan correctamente",
    "Direccionales — encienden y funcionan correctamente",
    "Luces de parqueo y reversa — encienden y funcionan",
    "Bocina / pito — funciona correctamente",
    "Espejos retrovisores y laterales — estado y ajuste",
    "Sistema de frenos — estado del frenado",
    "Nivel de líquido de freno",
    "Nivel de aceite de motor",
    "Nivel de líquido refrigerante",
    "Nivel de líquido de dirección hidráulica",
    "Fugas de combustible, aceites o líquidos",
    "Estado de correas y mangueras",
    "Revisión tablero e instrumentos",
    "Funcionamiento de limpiaparabrisas",
    "Funcionamiento de puertas, seguros y vidrios",
    "Estado de la dirección",
    "Cinturones de seguridad (todos los puestos)",
    "Estado de la carrocería / estructura",
    "Extintor — vigente y en buen estado"
]
 
ASPECTOS_CAMION = [
    "Llantas delanteras — estado y presión de aire",
    "Llantas traseras — estado y presión de aire",
    "Llanta de repuesto — estado y presión de aire",
    "Estado de carrocería y pintura — golpes y deterioros",
    "Niveles de aceite y refrigerante — fugas",
    "Frenos — fugas de aire o líquido, estado del frenado",
    "Motor — ruidos anormales",
    "Dirección — normal o dura anormal",
    "Luces altas — encienden y funcionan correctamente",
    "Luces bajas — encienden y funcionan correctamente",
    "Direccional delantera derecha",
    "Direccional delantera izquierda",
    "Direccional trasera derecha",
    "Direccional trasera izquierda",
    "Luces de parqueo delanteras",
    "Luces de parqueo traseras",
    "Stop de freno",
    "Batería — estado y funcionamiento",
    "Plumillas — las tiene y funcionan correctamente",
    "Pito — funciona correctamente",
    "Sillas — apoya cabezas, estado general",
    "Sillas delanteras y traseras — estado",
    "Cinturones de seguridad",
    "Botiquín — vigente y en buen estado",
    "Caja de herramientas — vigente y en buen estado",
    "Cruceta — vigente y en buen estado",
    "Tacos de parqueo — vigentes y en buen estado",
    "Triángulo de parqueo — vigente y en buen estado",
    "Gato — vigente y en buen estado",
    "Chaleco reflectivo — vigente y en buen estado",
    "Espejo lateral derecho",
    "Espejo lateral izquierdo",
    "Espejo retrovisor",
    "Extintor ABC — fecha de vencimiento vigente",
    "Extintor ABC — manómetro en zona verde",
    "Extintor ABC — sello de seguridad intacto",
    "Extintor ABC — pasador de seguridad",
    "Extintor ABC — boquilla en buen estado",
    "Extintor ABC — etiqueta legible",
    "Extintor ABC — sin óxido, golpes ni averías",
    "Documento de identidad — vigente",
    "Licencia de tránsito — vigente",
    "Licencia de conducción — vigente",
    "SOAT — vigente",
    "Revisión tecnomecánica — vigente",
    "Último cambio de aceite — fecha al día",
    "Última sincronización — fecha al día",
    "Última alineación y balanceo — fecha al día",
    "Último cambio de batería — fecha al día",
    "Último cambio de llantas — fecha al día"
]
 
ASPECTOS_POR_TIPO = {
    "Moto":   ASPECTOS_MOTO,
    "Carro":  ASPECTOS_CARRO,
    "Camion": ASPECTOS_CAMION,
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
        "Moto":   "Inspección Pre Operacional Motocicleta",
        "Carro":  "Inspección Pre Operacional Automóvil",
        "Camion": "Inspección Pre Operacional Camión",
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
#   ENDPOINT SUBMIT - ✅ CON VALIDACIONES CRÍTICAS
# ===============================
 
@router.post("/submit")
async def submit_inspeccion(
    usuario_actual: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
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
    ✅ VALIDACIÓN 1-15: Críticas para producción
    Todos los errores retornan HTTP 422 (Unprocessable Entity)
    """
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    usuario_id = usuario_actual.id
    nombre_conductor = normalize_name(usuario_actual.nombre_visible or usuario_actual.nombre)
    placa = normalize_placa(placa)
 
    # ========== VALIDACIÓN 1: PLACA ==========
    if not placa or len(placa) < 5:
        return JSONResponse(
            {"error": "Placa inválida. Ejemplo: GSZ34F"},
            status_code=422
        )
 
    # ========== VALIDACIÓN 2: PROCESO ==========
    if not proceso.strip():
        return JSONResponse(
            {"error": "Proceso es requerido"},
            status_code=422
        )
 
    # ========== VALIDACIÓN 3: ORIGEN/DESTINO ==========
    if not desde.strip() or not hasta.strip():
        return JSONResponse(
            {"error": "Origen y destino son requeridos"},
            status_code=422
        )
 
    # ========== VALIDACIÓN 4: MARCA ==========
    if not marca or len(marca.strip()) < 2:
        return JSONResponse(
            {"error": "Marca es requerida (mínimo 2 caracteres)"},
            status_code=422
        )
 
    # ========== VALIDACIÓN 5: GASOLINA ==========
    if not gasolina.strip():
        return JSONResponse(
            {"error": "Nivel de gasolina es requerido"},
            status_code=422
        )
 
    # ========== VALIDACIÓN 6: MODELO (año) ==========
    if modelo:
        if not modelo.isdigit() or len(modelo) != 4:
            return JSONResponse(
                {"error": "Modelo debe ser año (ej: 2021)"},
                status_code=422
            )
 
    # ========== VALIDACIÓN 7: MOTOR ==========
    if motor:
        if not motor.isdigit() or not (2 <= len(motor) <= 4):
            return JSONResponse(
                {"error": "Motor inválido. Ejemplos: 125, 1400, 6000"},
                status_code=422
            )
 
    # ========== VALIDACIÓN 8: LÍNEA ==========
    if not linea or len(linea.strip()) < 2:
        return JSONResponse(
            {"error": "Línea es requerida"},
            status_code=422
        )
 
    # ========== VALIDACIÓN 9: LICENCIA ==========
    if licencia_num and len(licencia_num.strip()) < 6:
        return JSONResponse(
            {"error": "Número de licencia inválido (mínimo 6 caracteres)"},
            status_code=422
        )
 
    # ========== VALIDACIÓN 10: FECHA VENCIMIENTO > HOY ==========
    if licencia_venc:
        try:
            venc_date = None
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                try:
                    venc_date = datetime.strptime(licencia_venc.strip(), fmt).date()
                    break
                except ValueError:
                    continue
            
            if venc_date is None:
                return JSONResponse(
                    {"error": "Formato de fecha inválido. Use YYYY-MM-DD"},
                    status_code=422
                )
            
            if venc_date < datetime.now().date():
                return JSONResponse(
                    {"error": f"Licencia vencida desde {licencia_venc}. Debe estar vigente."},
                    status_code=422
                )
        except Exception as e:
            return JSONResponse(
                {"error": f"Error validando fecha: {str(e)}"},
                status_code=422
            )
 
    # ========== VALIDACIÓN 11: DOCUMENTOS REQUERIDOS ==========
    if not porte_propiedad.strip():
        return JSONResponse(
            {"error": "Tarjeta de propiedad es requerida"},
            status_code=422
        )
 
    if not soat.strip():
        return JSONResponse(
            {"error": "SOAT es requerido"},
            status_code=422
        )
 
    if not poliza_seguro.strip():
        return JSONResponse(
            {"error": "Póliza de seguro es requerida"},
            status_code=422
        )
 
    # Para Carro/Camión, emisión de gases es obligatoria
    if tipo_vehiculo in ["Carro", "Camion"]:
        if not certificado_emision.strip():
            return JSONResponse(
                {"error": "Certificado de emisión de gases es requerido para Carros y Camiones"},
                status_code=422
            )
 
    # ========== VALIDACIÓN 12: ASPECTOS COMPLETOS ==========
    try:
        asp_json = json.loads(aspectos)
    except json.JSONDecodeError:
        return JSONResponse(
            {"error": "Aspectos JSON inválido"},
            status_code=422
        )
 
    # Contar aspectos esperados según tipo
    aspectos_esperados = {
        "Moto": 18,
        "Carro": 22,
        "Camion": 50
    }
    num_esperados = aspectos_esperados.get(tipo_vehiculo, 18)
 
    # Función auxiliar para extraer valor de aspecto
    def _asp_valor(v):
        return v.get("valor") if isinstance(v, dict) else v
 
    # Validar que todos los aspectos tengan B o M
    aspectos_validos = [
        v for v in asp_json.values()
        if _asp_valor(v) in ["B", "M"]
    ]
 
    if len(aspectos_validos) != num_esperados:
        return JSONResponse(
            {
                "error": f"Debes revisar todos los {num_esperados} aspectos. "
                         f"Solo {len(aspectos_validos)} completados."
            },
            status_code=422
        )
 
    # ========== VALIDACIÓN 13: FIRMA NO VACÍA ==========
    if not firma_dataurl or len(firma_dataurl) < 100:  # data-URI mínimo ~100 chars
        return JSONResponse(
            {"error": "Firma es obligatoria. Dibuja o carga una imagen."},
            status_code=422
        )
 
    # ========== VALIDACIÓN 14: TAMAÑO FIRMA < 2MB ==========
    try:
        if "," not in firma_dataurl:
            return JSONResponse(
                {"error": "Formato de firma inválido"},
                status_code=422
            )
        
        _, b64_data = firma_dataurl.split(",", 1)
        decoded_size = len(base64.b64decode(b64_data))
        MAX_FIRMA_SIZE = 2 * 1024 * 1024  # 2MB
        
        if decoded_size > MAX_FIRMA_SIZE:
            size_mb = decoded_size / (1024 * 1024)
            return JSONResponse(
                {"error": f"Firma muy grande ({size_mb:.2f}MB). Máximo 2MB."},
                status_code=422
            )
    except ValueError:
        return JSONResponse(
            {"error": "Formato de firma inválido (no es base64)"},
            status_code=422
        )
 
    # ========== VALIDACIÓN 15: OBSERVACIONES SI HAY M ==========
    has_m = any(_asp_valor(v) == "M" for v in asp_json.values())
    if has_m:
        obs_len = len(observaciones.strip())
        if obs_len < 10:
            return JSONResponse(
                {
                    "error": f"Observaciones obligatorias si hay aspectos en M. "
                             f"Mínimo 10 caracteres ({obs_len}/10)."
                },
                status_code=422
            )
 
    # ========== TODO VALIDADO: PROCEDER CON GUARDADO ==========
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
                firma_path = user_paths["firmas"] / firma_filename
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
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                    try:
                        _venc = datetime.strptime(licencia_venc.strip(), fmt)
                        if _venc.date() < datetime.now().date():
                            _licencia_advertencia = f"⚠️ Licencia vencida desde {licencia_venc}"
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
 
            # ✅ FIX: generar PDF ANTES de tocar la BD
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
                    "aspectos_lista": registros[0].aspectos_lista,
                    "titulo_tipo": registros[0].titulo_tipo,
                },
                output_path=str(reporte_path),
            )
 
            # ✅ Verificar que el PDF existe y tiene contenido antes de guardar historial
            if not reporte_path.exists() or reporte_path.stat().st_size < 1000:
                raise RuntimeError(f"PDF consolidado inválido: {reporte_path}")
 
            # ✅ Guardar historial del consolidado
            hist = models.ReporteInspeccion(
                nombre_conductor=nombre_conductor,
                fecha_reporte=datetime.now(),
                archivo_pdf=str(reporte_path),
                total_incluidas=15,
            )
            db.add(hist)
            db.commit()
 
            # ✅ COMENTADO: No borrar inspecciones después de consolidar
            # Las inspecciones se MANTIENEN en el historial para auditoría
            # Si en el futuro necesitas borrarlas, descomentar el bloque abajo
            """
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
            """
 
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
    """Genera PDF consolidado de 15 inspecciones manualmente"""
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
                "aspectos_lista": registros[0].aspectos_lista,
                "titulo_tipo": registros[0].titulo_tipo,
            },
            output_path=str(pdf_path),
        )
 
        return safe_return_pdf(pdf_path, pdf_filename)
 
    except Exception:
        raise
 
 
# ==========================================================
#   RUTA: MIS INSPECCIONES (historial del conductor)
#   ✅ OPTIMIZADA: Solo últimas 15 activas + historial consolidado
# ==========================================================
 
@router.get("/mis-inspecciones")
async def mis_inspecciones(
    request: Request,
    formato: str = "html",
    usuario_actual: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Historial de inspecciones del conductor autenticado.
    
    OPTIMIZACIÓN PARA SOSTENIBILIDAD:
    - Muestra solo las ÚLTIMAS 15 inspecciones sin consolidar (ciclo actual)
    - Si hay 90 inspecciones, muestra solo las últimas 15 (ciclo 6)
    - Los ciclos anteriores están en "Historial de consolidados"
    
    Soporta dos formatos:
    - ?formato=html (defecto) → devuelve template lista_inspecciones.html
    - ?formato=json → devuelve JSON con registros + reportes
    """
    nombre_conductor = normalize_name(
        usuario_actual.nombre_visible or usuario_actual.nombre
    )
 
    # ✅ OPTIMIZACIÓN: Solo últimas 15 inspecciones (ciclo actual)
    # Ordenar DESC, limitar 15, luego invertir para mostrar cronológicamente
    registros_raw = (
        db.query(models.Inspeccion)
        .filter(models.Inspeccion.usuario_id == usuario_actual.id)
        .order_by(models.Inspeccion.fecha.desc())
        .limit(15)  # ✅ MÁXIMO 15 en la vista principal
        .all()
    )
    # Invertir para mostrar más antigua a más nueva
    registros = list(reversed(registros_raw))
 
    # Reportes consolidados (historial de PDFs generados)
    reportes_consolidados = (
        db.query(models.ReporteInspeccion)
        .filter(models.ReporteInspeccion.nombre_conductor == nombre_conductor)
        .order_by(models.ReporteInspeccion.fecha_reporte.desc())
        .all()
    )
 
    # ✅ Contador correcto: len(registros) será siempre <= 15
    # Si hay 90 inspecciones totales (6 ciclos), muestra 15 del ciclo actual
    total_activas = len(registros)
    puede_generar_pdf15 = total_activas >= 15
 
    # ✅ NUEVO: Soporte para JSON
    if formato.lower() == "json":
        return JSONResponse({
            "nombre_conductor": nombre_conductor,
            "total_en_ciclo": total_activas,  # 0-15
            "puede_generar_pdf15": puede_generar_pdf15,
            "registros": [
                {
                    "id": r.id,
                    "fecha": r.fecha.strftime("%Y-%m-%d"),
                    "placa": r.placa,
                    "tipo_vehiculo": r.tipo_vehiculo or "Moto",
                    "proceso": r.proceso,
                    "desde": r.desde,
                    "hasta": r.hasta,
                    "condiciones_optimas": r.condiciones_optimas,
                    "observaciones": r.observaciones or "",
                }
                for r in registros
            ],
            "reportes_consolidados": [
                {
                    "id": rep.id,
                    "fecha_reporte": rep.fecha_reporte.strftime("%Y-%m-%d %H:%M"),
                    "total_incluidas": rep.total_incluidas,
                }
                for rep in reportes_consolidados
            ],
        })
 
    # Formato HTML (original)
    return _TEMPLATES.TemplateResponse(
        "lista_inspecciones.html",
        {
            "request": request,
            "nombre_conductor": nombre_conductor,
            "registros": registros,
            "puede_generar_pdf15": puede_generar_pdf15,
            "reportes_consolidados": reportes_consolidados,
        },
    )
 
 
# ==========================================================
#   RUTA: DESCARGA PDF CONSOLIDADO (por id de reporte)
# ==========================================================
 
@router.get("/reporte-consolidado/{reporte_id}")
async def descargar_reporte_consolidado(
    reporte_id: int,
    usuario_actual: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Descarga un PDF consolidado del historial.
    El conductor solo puede descargar sus propios reportes.
    El admin puede descargar cualquiera.
    """
    reporte = db.query(models.ReporteInspeccion).filter_by(id=reporte_id).first()
    if not reporte:
        return JSONResponse({"error": "Reporte no encontrado"}, status_code=404)
 
    nombre_conductor = normalize_name(
        usuario_actual.nombre_visible or usuario_actual.nombre
    )
    if usuario_actual.rol != "admin" and reporte.nombre_conductor != nombre_conductor:
        return JSONResponse({"error": "Sin acceso a este reporte"}, status_code=403)
 
    pdf_path = Path(reporte.archivo_pdf)
    if not pdf_path.exists():
        return JSONResponse(
            {"error": "El archivo PDF ya no existe en el servidor"},
            status_code=404
        )
 
    filename = pdf_path.name
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"
 
    return safe_return_pdf(pdf_path, filename)
 
 
# ==========================================================
#   RUTA: DETALLE + DESCARGA PDF DE INSPECCIÓN INDIVIDUAL
# ==========================================================
 
@router.get("/detalle/{inspeccion_id}")
async def detalle_inspeccion(
    inspeccion_id: int,
    formato: str = "json",
    usuario_actual: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Devuelve el detalle de una inspección individual.
    ?formato=json → datos en JSON (para modal del frontend)
    ?formato=pdf  → regenera y descarga el PDF individual
    El conductor solo puede ver/descargar sus propias inspecciones.
    El admin puede acceder a cualquiera.
    """
    inspeccion = db.query(models.Inspeccion).filter_by(id=inspeccion_id).first()
    if not inspeccion:
        return JSONResponse({"error": "Inspección no encontrada"}, status_code=404)
 
    if usuario_actual.rol != "admin" and inspeccion.usuario_id != usuario_actual.id:
        return JSONResponse({"error": "Sin acceso a esta inspección"}, status_code=403)
 
    inspeccion = prepare_registro(inspeccion)
 
    if formato == "pdf":
        timestamp  = inspeccion.fecha.strftime("%Y%m%d_%H%M%S")
        pdf_filename = f"inspeccion_{inspeccion.nombre_conductor.replace(' ','_')}_{timestamp}.pdf"
        user_paths = get_user_paths(inspeccion.usuario_id)
        pdf_path   = user_paths["inspecciones"] / pdf_filename
 
        render_pdf_from_template(
            "pdf_template.html",
            {
                "registro":       inspeccion,
                "fecha":          inspeccion.fecha.strftime("%d - %m - %Y"),
                "codigo":         "FO-SST-063",
                "version":        "01",
                "logo_path":      build_file_uri(LOGO_PATH),
                "aspectos_lista": inspeccion.aspectos_lista,
                "titulo_tipo":    inspeccion.titulo_tipo,
            },
            output_path=str(pdf_path),
        )
        return safe_return_pdf(pdf_path, pdf_filename)
 
    # Formato JSON — datos completos para el modal
    asp   = inspeccion.aspectos_parsed or {}
    lista = inspeccion.aspectos_lista  or []
 
    aspectos_detalle = [
        {"num": i, "label": label, "valor": asp.get(str(i), "B")}
        for i, label in enumerate(lista, 1)
    ]
 
    return JSONResponse({
        "id":                  inspeccion.id,
        "fecha":               inspeccion.fecha.strftime("%d/%m/%Y %H:%M"),
        "nombre_conductor":    inspeccion.nombre_conductor,
        "placa":               inspeccion.placa,
        "tipo_vehiculo":       inspeccion.tipo_vehiculo or "Moto",
        "proceso":             inspeccion.proceso,
        "desde":               inspeccion.desde,
        "hasta":               inspeccion.hasta,
        "marca":               inspeccion.marca,
        "modelo":              inspeccion.modelo,
        "motor":               inspeccion.motor,
        "gasolina":            inspeccion.gasolina,
        "licencia_num":        inspeccion.licencia_num,
        "licencia_venc":       inspeccion.licencia_venc,
        "porte_propiedad":     inspeccion.porte_propiedad,
        "soat":                inspeccion.soat,
        "certificado_emision": inspeccion.certificado_emision,
        "poliza_seguro":       inspeccion.poliza_seguro,
        "condiciones_optimas": inspeccion.condiciones_optimas,
        "observaciones":       inspeccion.observaciones or "",
        "aspectos":            aspectos_detalle,
    })