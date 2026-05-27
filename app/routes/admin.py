# app/routes_admin.py
"""
Panel de administración web para gestionar usuarios
 
Funcionalidades:
- Listar usuarios
- Crear usuarios
- Editar usuarios (cambiar PIN, rol)
- Eliminar usuarios
- Ver logs de auditoría
"""
 
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime
 
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
 
 
# ===============================
# DASHBOARD
# ===============================
 
@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    usuario_admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    templates = _templates_admin
    total_usuarios     = db.query(models.Usuario).count()
    total_inspecciones = db.query(models.Inspeccion).count()
 
    from sqlalchemy import func, desc
    usuarios_activos = (
        db.query(
            models.Usuario.nombre_visible,
            func.count(models.Inspeccion.id).label("total")
        )
        .join(models.Inspeccion)
        .group_by(models.Usuario.id)
        .order_by(desc("total"))
        .limit(5)
        .all()
    )
 
    from datetime import date, timedelta
    from sqlalchemy import cast, Date as SADate
    hoy     = date.today()
    primera = db.query(func.min(cast(models.Inspeccion.fecha, SADate))).scalar()
 
    if primera:
        delta = (hoy - primera).days + 1
        rows  = (
            db.query(
                cast(models.Inspeccion.fecha, SADate).label("dia"),
                func.count(models.Inspeccion.id).label("total")
            )
            .group_by("dia")
            .order_by("dia")
            .all()
        )
        totales_dia = {r.dia: r.total for r in rows}
        inspecciones_por_dia = [
            {
                "fecha":     (primera + timedelta(days=i)).strftime("%d/%m/%y"),
                "fecha_iso": (primera + timedelta(days=i)).isoformat(),
                "total":     totales_dia.get(primera + timedelta(days=i), 0)
            }
            for i in range(delta)
        ]
    else:
        inspecciones_por_dia = []
 
    from sqlalchemy import extract
    rows_anual = (
        db.query(
            extract("year",  models.Inspeccion.fecha).label("anio"),
            extract("month", models.Inspeccion.fecha).label("mes"),
            func.count(models.Inspeccion.id).label("total")
        )
        .group_by("anio", "mes")
        .order_by("anio", "mes")
        .all()
    )
 
    anual_dict: dict = {}
    for row in rows_anual:
        anio = int(row.anio)
        mes  = int(row.mes)
        if anio not in anual_dict:
            anual_dict[anio] = [0] * 12
        anual_dict[anio][mes - 1] = int(row.total)
 
    inspecciones_anual = [
        {"anio": anio, "meses": anual_dict[anio]}
        for anio in sorted(anual_dict.keys())
    ]
 
    return templates.TemplateResponse("admin/dashboard.html", {
        "request":             request,
        "admin":               usuario_admin,
        "total_usuarios":      total_usuarios,
        "total_inspecciones":  total_inspecciones,
        "usuarios_activos":    usuarios_activos,
        "inspecciones_por_dia": inspecciones_por_dia,
        "inspecciones_anual":  inspecciones_anual,
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
 
    from sqlalchemy import func
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
    if len(pin) < 4:
        raise HTTPException(400, "PIN debe tener al menos 4 dígitos")
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
    if pin and len(pin) >= 4:
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
    from sqlalchemy import desc
 
    logs = (
        db.query(models.LogAuditoria)
        .order_by(desc(models.LogAuditoria.fecha))
        .limit(100)
        .all()
    )
 
    for log in logs:
        admin = db.query(models.Usuario).filter_by(id=log.admin_id).first()
        # Mostrar nombre_visible si existe, si no la cédula
        log.admin_nombre = (
            (admin.nombre_visible or admin.cedula) if admin else "Desconocido"
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
    from datetime import datetime as _dt, timedelta
 
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
            q = q.filter(models.Inspeccion.fecha >= _dt.strptime(fecha_desde.strip(), "%Y-%m-%d"))
        except ValueError:
            pass
    if fecha_hasta.strip():
        try:
            limite = _dt.strptime(fecha_hasta.strip(), "%Y-%m-%d") + timedelta(days=1)
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
 
 
# ===============================
# API REST
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