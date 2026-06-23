# app/routes/admin.py
"""
Panel de administración web para gestionar usuarios
 
Funcionalidades:
- Listar usuarios
- Crear usuarios
- Editar usuarios (cambiar PIN, rol)
- Eliminar usuarios
- Ver logs de auditoría
- Dashboard con gráficas de inspecciones
"""
 
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, extract, and_, cast, Date as SADate, case
from datetime import datetime, date, timedelta
 
from app.database import SessionLocal
from app import models
from app.security import get_current_user, hash_pin
 
router = APIRouter()
 
from fastapi.templating import Jinja2Templates as _J2T
# ✅ CORREGIDO: apuntar a app/templates, no a routes/templates
_templates_admin = _J2T(directory=str(Path(__file__).resolve().parent.parent / "templates"))
 
 
# ===============================
# DEPENDENCY: Solo administradores
# ===============================
 
def require_admin(usuario_actual: models.Usuario = Depends(get_current_user)):
    if usuario_actual.rol != "admin":
        raise HTTPException(status_code=403, detail="No tienes permisos de administrador")
    return usuario_actual
 
 
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
 
 
# ===============================
# AUDITORÍA
# ===============================
 
def registrar_accion(db: Session, admin_id: int, accion: str, detalles: str):
    log = models.LogAuditoria(
        admin_id=admin_id,
        accion=accion,
        detalles=detalles,
        fecha=datetime.now()
    )
    db.add(log)
    db.commit()
 
 
# ═══════════════════════════════════════════════════════════════════
# DASHBOARD CON GRÁFICAS
# ═══════════════════════════════════════════════════════════════════
 
@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    usuario_admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Dashboard admin con gráficas:
    - KPIs: usuarios, inspecciones, promedio, activos
    - Gráfica de línea: inspecciones por día (últimos 90 días)
    - Gráfica de barras: top conductores
    - Tabla ranking: conductores con más inspecciones
    - Gráfica dona: distribución top 5 conductores
    - Gráfica anual: inspecciones por mes comparando años
    
    ✅ CORREGIDO:
    - Usa fecha (no fecha_creacion) ← CORRECCIÓN PRINCIPAL
    - Usa outerjoin en vez de join
    - Llena días vacíos con 0
    - Filtra solo usuarios activos
    - Muestra nombre completo (no cédula)
    """
    templates = _templates_admin
    
    # ✅ 1. KPIs GENERALES
    total_usuarios = db.query(models.Usuario).count()
    total_inspecciones = db.query(models.Inspeccion).count()
    
    # ✅ 2. TOP CONDUCTORES (para ranking, barras y dona)
    # MEJORADO: Prioridad nombre_visible > nombre > Conductor + cédula
    usuarios_activos = (
        db.query(
            case(
                # 1º nombre_visible si no es NULL ni vacío
                (func.trim(func.coalesce(models.Usuario.nombre_visible, '')) != '', 
                 models.Usuario.nombre_visible),
                # 2º nombre si no es NULL ni vacío  
                (func.trim(func.coalesce(models.Usuario.nombre, '')) != '',
                 models.Usuario.nombre),
                # 3º fallback: "Conductor " + cédula (nunca muestra el número crudo)
                else_="Conductor " + models.Usuario.cedula
            ).label("nombre"),
            func.count(models.Inspeccion.id).label("total")
        )
        .outerjoin(models.Inspeccion)  # ✅ CORREGIDO: outerjoin
        .filter(models.Usuario.activo == 1)  # ✅ Solo usuarios activos
        .group_by(models.Usuario.id)
        .having(func.count(models.Inspeccion.id) > 0)  # ✅ Solo con inspecciones
        .order_by(desc("total"))
        .limit(5)
        .all()
    )
    
    # ✅ 3. INSPECCIONES POR DÍA (últimos 90 días)
    hoy = date.today()
    hace_90_dias = hoy - timedelta(days=90)
    
    # Query: agrupar por fecha
    rows = (
        db.query(
            cast(models.Inspeccion.fecha, SADate).label("dia"),  # ✅ CORREGIDO: usa 'fecha' no 'fecha_creacion'
            func.count(models.Inspeccion.id).label("total")
        )
        .filter(models.Inspeccion.fecha >= hace_90_dias)  # ✅ CORREGIDO: usa 'fecha'
        .group_by("dia")
        .order_by("dia")
        .all()
    )
    
    # Convertir a dict para búsqueda rápida
    totales_dia = {r.dia: r.total for r in rows}
    
    # Llenar los 90 días (incluir días sin inspecciones como 0)
    inspecciones_por_dia = []
    for i in range(90):
        fecha = hace_90_dias + timedelta(days=i)
        inspecciones_por_dia.append({
            "fecha": fecha.strftime("%d/%m/%y"),
            "total": totales_dia.get(fecha, 0)  # ← 0 si no hay datos
        })
    
    # ✅ 4. INSPECCIONES POR MES/AÑO (comparativa anual)
    rows_anual = (
        db.query(
            extract("year", models.Inspeccion.fecha).label("anio"),  # ✅ CORREGIDO: usa 'fecha'
            extract("month", models.Inspeccion.fecha).label("mes"),  # ✅ CORREGIDO: usa 'fecha'
            func.count(models.Inspeccion.id).label("total")
        )
        .group_by("anio", "mes")
        .order_by("anio", "mes")
        .all()
    )
    
    # Estructurar como espera el template: {anio: [mes1, mes2, ...]}
    anual_dict = {}
    for row in rows_anual:
        anio = int(row.anio)
        mes = int(row.mes)
        if anio not in anual_dict:
            anual_dict[anio] = [0] * 12
        anual_dict[anio][mes - 1] = int(row.total)
    
    # Convertir a lista de dicts ordenados (años más recientes primero)
    inspecciones_anual = [
        {"anio": anio, "meses": anual_dict[anio]}
        for anio in sorted(anual_dict.keys(), reverse=True)
    ]
    
    # ✅ 5. RETORNAR TEMPLATE CON TODOS LOS DATOS
    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "admin": usuario_admin,
        "total_usuarios": total_usuarios,
        "total_inspecciones": total_inspecciones,
        "usuarios_activos": usuarios_activos,  # ← Para ranking, barras, dona (con nombres)
        "inspecciones_por_dia": inspecciones_por_dia,  # ← Para gráfica de línea
        "inspecciones_anual": inspecciones_anual,  # ← Para gráfica anual
    })
 
 
# ===============================
# USUARIOS — LISTAR
# ===============================
 
@router.get("/admin/usuarios", response_class=HTMLResponse)
async def admin_usuarios_list(
    request: Request,
    usuario_admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    templates = _templates_admin
    usuarios  = db.query(models.Usuario).all()
 
    stats = dict(
        db.query(
            models.Inspeccion.usuario_id,
            func.count(models.Inspeccion.id)
        )
        .group_by(models.Inspeccion.usuario_id)
        .all()
    )
 
    return templates.TemplateResponse("admin/usuarios.html", {
        "request":  request,
        "admin":    usuario_admin,
        "usuarios": usuarios,
        "stats":    stats,
    })
 
 
# ===============================
# USUARIOS — CREAR
# ===============================
 
@router.get("/admin/usuarios/nuevo", response_class=HTMLResponse)
async def admin_usuario_nuevo_form(
    request: Request,
    usuario_admin: models.Usuario = Depends(require_admin)
):
    return _templates_admin.TemplateResponse("admin/usuario_form.html", {
        "request": request,
        "admin":   usuario_admin,
        "modo":    "crear",
        "usuario": None,
    })
 
 
@router.post("/admin/usuarios/crear")
async def admin_usuario_crear(
    usuario_admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
    cedula: str = Form(...),
    nombre_visible: str = Form(...),
    pin: str = Form(...),
    rol: str = Form("user")
):
    cedula_clean = cedula.strip()
 
    if not cedula_clean.isdigit() or not (5 <= len(cedula_clean) <= 12):
        raise HTTPException(400, "Cédula inválida (5-12 dígitos numéricos)")
    # ✅ PIN mínimo 6 dígitos
    if len(pin) < 6:
        raise HTTPException(400, "PIN debe tener al menos 6 dígitos")
    if rol not in ["user", "admin"]:
        raise HTTPException(400, "Rol inválido")
 
    existe = db.query(models.Usuario).filter(
        models.Usuario.cedula == cedula_clean
    ).first()
    if existe:
        raise HTTPException(400, f"La cédula '{cedula_clean}' ya está registrada")
 
    nuevo_usuario = models.Usuario(
        cedula=cedula_clean,
        nombre_visible=nombre_visible.strip(),
        pin_hash=hash_pin(pin),
        rol=rol
    )
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)
 
    registrar_accion(
        db, admin_id=usuario_admin.id, accion="CREAR_USUARIO",
        detalles=f"Cédula '{cedula_clean}' creada con rol '{rol}'"
    )
 
    return RedirectResponse(url="/admin/usuarios?mensaje=Usuario creado exitosamente", status_code=303)
 
 
# ===============================
# USUARIOS — EDITAR
# ===============================
 
@router.get("/admin/usuarios/{usuario_id}/editar", response_class=HTMLResponse)
async def admin_usuario_editar_form(
    request: Request,
    usuario_id: int,
    usuario_admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    usuario = db.query(models.Usuario).filter_by(id=usuario_id).first()
    if not usuario:
        raise HTTPException(404, "Usuario no encontrado")
 
    return _templates_admin.TemplateResponse("admin/usuario_form.html", {
        "request": request,
        "admin":   usuario_admin,
        "modo":    "editar",
        "usuario": usuario,
    })
 
 
@router.post("/admin/usuarios/{usuario_id}/actualizar")
async def admin_usuario_actualizar(
    usuario_id: int,
    usuario_admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
    nombre_visible: str = Form(...),
    pin: str = Form(None),
    rol: str = Form(...)
):
    usuario = db.query(models.Usuario).filter_by(id=usuario_id).first()
    if not usuario:
        raise HTTPException(404, "Usuario no encontrado")
    if usuario.id == usuario_admin.id and rol != "admin":
        raise HTTPException(400, "No puedes quitarte permisos de admin")
 
    cambios = []
    if nombre_visible.strip() != usuario.nombre_visible:
        usuario.nombre_visible = nombre_visible.strip()
        cambios.append("nombre_visible")
    if rol != usuario.rol:
        usuario.rol = rol
        cambios.append(f"rol → {rol}")
    # ✅ PIN mínimo 6 dígitos
    if pin and len(pin) >= 6:
        usuario.pin_hash = hash_pin(pin)
        cambios.append("PIN")
 
    db.commit()
 
    if cambios:
        registrar_accion(
            db, admin_id=usuario_admin.id, accion="EDITAR_USUARIO",
            detalles=f"Cédula '{usuario.cedula}': {', '.join(cambios)}"
        )
 
    return RedirectResponse(url="/admin/usuarios?mensaje=Usuario actualizado", status_code=303)
 
 
# ===============================
# USUARIOS — ELIMINAR
# ===============================
 
@router.post("/admin/usuarios/{usuario_id}/eliminar")
async def admin_usuario_eliminar(
    usuario_id: int,
    usuario_admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    usuario = db.query(models.Usuario).filter_by(id=usuario_id).first()
    if not usuario:
        raise HTTPException(404, "Usuario no encontrado")
    if usuario.id == usuario_admin.id:
        raise HTTPException(400, "No puedes eliminarte a ti mismo")
 
    tiene_inspecciones = db.query(models.Inspeccion).filter_by(usuario_id=usuario_id).first()
    if tiene_inspecciones:
        raise HTTPException(400, "No se puede eliminar: el usuario tiene inspecciones registradas")
 
    cedula_eliminada    = usuario.cedula
    usuario.token       = None
    usuario.token_expira = None
    db.delete(usuario)
    db.commit()
 
    registrar_accion(
        db, admin_id=usuario_admin.id, accion="ELIMINAR_USUARIO",
        detalles=f"Cédula '{cedula_eliminada}' eliminada"
    )
 
    return RedirectResponse(url="/admin/usuarios?mensaje=Usuario eliminado", status_code=303)
 
 
# ===============================
# LOGS DE AUDITORÍA
# ===============================
 
@router.get("/admin/logs", response_class=HTMLResponse)
async def admin_logs(
    request: Request,
    usuario_admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    logs = (
        db.query(models.LogAuditoria)
        .order_by(desc(models.LogAuditoria.fecha))
        .limit(100)
        .all()
    )
 
    for log in logs:
        admin = db.query(models.Usuario).filter_by(id=log.admin_id).first()
        # ✅ MEJORADO: Prioridad nombre_visible > nombre > cédula
        log.admin_nombre = (
            (admin.nombre_visible or admin.nombre or admin.cedula) if admin else "Desconocido"
        )
 
    return _templates_admin.TemplateResponse("admin/logs.html", {
        "request": request,
        "admin":   usuario_admin,
        "logs":    logs,
    })
 
 
# ===============================
# SUSPENDER / REACTIVAR
# ===============================
 
@router.post("/admin/usuarios/{usuario_id}/suspender")
async def admin_usuario_suspender(
    usuario_id: int,
    usuario_admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    usuario = db.query(models.Usuario).filter_by(id=usuario_id).first()
    if not usuario:
        raise HTTPException(404, "Usuario no encontrado")
    if usuario.id == usuario_admin.id:
        raise HTTPException(400, "No puedes suspenderte a ti mismo")
 
    usuario.activo       = 0
    usuario.token        = None
    usuario.token_expira = None
    db.commit()
 
    registrar_accion(
        db, usuario_admin.id, "SUSPENDER_USUARIO",
        f"Cédula '{usuario.cedula}' suspendida"
    )
    return RedirectResponse(url="/admin/usuarios?mensaje=Usuario suspendido", status_code=303)
 
 
@router.post("/admin/usuarios/{usuario_id}/reactivar")
async def admin_usuario_reactivar(
    usuario_id: int,
    usuario_admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    usuario = db.query(models.Usuario).filter_by(id=usuario_id).first()
    if not usuario:
        raise HTTPException(404, "Usuario no encontrado")
 
    usuario.activo = 1
    db.commit()
 
    registrar_accion(
        db, usuario_admin.id, "REACTIVAR_USUARIO",
        f"Cédula '{usuario.cedula}' reactivada"
    )
    return RedirectResponse(url="/admin/usuarios?mensaje=Usuario reactivado", status_code=303)
 
 
# ===============================
# INSPECCIONES — VISTA GENERAL
# ===============================
 
@router.get("/admin/inspecciones", response_class=HTMLResponse)
async def admin_inspecciones(
    request: Request,
    usuario_admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
    conductor: str = "",
    placa: str = "",
    tipo: str = "",
    fecha_desde: str = "",
    fecha_hasta: str = "",
):
    q = (
        db.query(models.Inspeccion, models.Usuario)
        .join(models.Usuario, models.Inspeccion.usuario_id == models.Usuario.id)
    )
 
    if conductor.strip():
        q = q.filter(models.Inspeccion.nombre_conductor.ilike(f"%{conductor.strip()}%"))
    if placa.strip():
        q = q.filter(models.Inspeccion.placa.ilike(f"%{placa.strip()}%"))
    if tipo.strip():
        q = q.filter(models.Inspeccion.tipo_vehiculo == tipo.strip())
    if fecha_desde.strip():
        try:
            q = q.filter(models.Inspeccion.fecha >= datetime.strptime(fecha_desde.strip(), "%Y-%m-%d"))
        except ValueError:
            pass
    if fecha_hasta.strip():
        try:
            limite = datetime.strptime(fecha_hasta.strip(), "%Y-%m-%d") + timedelta(days=1)
            q = q.filter(models.Inspeccion.fecha < limite)
        except ValueError:
            pass
 
    resultados          = q.order_by(models.Inspeccion.fecha.desc()).limit(300).all()
    total_activas       = db.query(models.Inspeccion).count()
    conductores_unicos  = db.query(models.Inspeccion.usuario_id).distinct().count()
 
    def _tiene_malo(inspeccion):
        for v in (inspeccion.aspectos_dict or {}).values():
            val = v.get("valor") if isinstance(v, dict) else v
            if val == "M":
                return True
        return False
 
    con_malo = sum(1 for r, u in resultados if _tiene_malo(r))
 
    return _templates_admin.TemplateResponse("admin/inspecciones.html", {
        "request":            request,
        "admin":              usuario_admin,
        "resultados":         resultados,
        "total_activas":      total_activas,
        "con_malo":           con_malo,
        "conductores_unicos": conductores_unicos,
        "usuario_filtro":     None,
        "reportes":           [],
        "filtros": {
            "conductor":   conductor,
            "placa":       placa,
            "tipo":        tipo,
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
        },
    })
 
 
# ===============================
# INSPECCIONES — POR USUARIO
# ===============================
 
@router.get("/admin/usuarios/{usuario_id}/inspecciones", response_class=HTMLResponse)
async def admin_usuario_inspecciones(
    request: Request,
    usuario_id: int,
    usuario_admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
):
    usuario = db.query(models.Usuario).filter_by(id=usuario_id).first()
    if not usuario:
        raise HTTPException(404, "Usuario no encontrado")
 
    inspecciones = (
        db.query(models.Inspeccion)
        .filter(models.Inspeccion.usuario_id == usuario_id)
        .order_by(models.Inspeccion.fecha.desc())
        .all()
    )
 
    nombre_visible = usuario.nombre_visible or usuario.cedula
    reportes = (
        db.query(models.ReporteInspeccion)
        .filter(models.ReporteInspeccion.nombre_conductor == nombre_visible)
        .order_by(models.ReporteInspeccion.fecha_reporte.desc())
        .all()
    )
 
    def _tiene_malo(inspeccion):
        for v in (inspeccion.aspectos_dict or {}).values():
            val = v.get("valor") if isinstance(v, dict) else v
            if val == "M":
                return True
        return False
 
    con_malo   = sum(1 for i in inspecciones if _tiene_malo(i))
    resultados = [(i, usuario) for i in inspecciones]
 
    return _templates_admin.TemplateResponse("admin/inspecciones.html", {
        "request":            request,
        "admin":              usuario_admin,
        "resultados":         resultados,
        "total_activas":      db.query(models.Inspeccion).count(),
        "con_malo":           con_malo,
        "conductores_unicos": 1,
        "usuario_filtro":     usuario,
        "reportes":           reportes,
        "filtros": {
            "conductor":   nombre_visible,
            "placa":       "",
            "tipo":        "",
            "fecha_desde": "",
            "fecha_hasta": "",
        },
    })
 
 
# ==========================================================
#   API REST: VALIDAR CÉDULA EN TIEMPO REAL
# ==========================================================
 
@router.get("/api/admin/validar-cedula")
async def validar_cedula(
    cedula: str,
    usuario_admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Verifica si una cédula ya existe en la BD.
    Usado por el formulario de crear usuario para validación en tiempo real.
    
    Retorna: {"existe": true/false}
    """
    cedula_clean = cedula.strip()
    
    if not cedula_clean.isdigit() or not (5 <= len(cedula_clean) <= 12):
        return JSONResponse(
            {"error": "Cédula inválida"},
            status_code=400
        )
    
    existe = db.query(models.Usuario).filter(
        models.Usuario.cedula == cedula_clean
    ).first()
    
    return JSONResponse({
        "existe": existe is not None,
        "cedula": cedula_clean,
    })
 
 
# ===============================
# API REST: USUARIOS
# ===============================
 
@router.get("/api/admin/usuarios")
async def api_usuarios_list(
    usuario_admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    usuarios = db.query(models.Usuario).all()
    return {
        "ok": True,
        "usuarios": [
            {
                "id":             u.id,
                "cedula":         u.cedula,
                "nombre_visible": u.nombre_visible,
                "rol":            u.rol,
            }
            for u in usuarios
        ]
    }
 
 
@router.post("/api/admin/usuarios")
async def api_usuario_crear(
    usuario_admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
    datos: dict = None
):
    pass