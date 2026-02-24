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

from fastapi import APIRouter, Depends, HTTPException, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import SessionLocal
from app import models
from app.security import get_current_user, hash_pin

router = APIRouter()

# ===============================
# DEPENDENCY: Solo administradores
# ===============================

def require_admin(usuario_actual: models.Usuario = Depends(get_current_user)):
    """
    Verifica que el usuario sea administrador
    Uso: usuario_admin = Depends(require_admin)
    """
    if usuario_actual.rol != "admin":
        raise HTTPException(
            status_code=403,
            detail="No tienes permisos de administrador"
        )
    return usuario_actual


def get_db():
    """Dependency para sesión de BD"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ===============================
# MODELO: Log de Auditoría
# ===============================

def registrar_accion(db: Session, admin_id: int, accion: str, detalles: str):
    """
    Registra acción administrativa en log de auditoría
    
    Args:
        admin_id: ID del admin que realizó la acción
        accion: Tipo de acción (CREAR_USUARIO, EDITAR_USUARIO, etc)
        detalles: Descripción de lo que se hizo
    """
    log = models.LogAuditoria(
        admin_id=admin_id,
        accion=accion,
        detalles=detalles,
        fecha=datetime.now()
    )
    db.add(log)
    db.commit()


# ===============================
# RUTAS: Panel de Administración
# ===============================

@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    usuario_admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Dashboard principal del admin
    """
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="app/templates")
    
    # Estadísticas
    total_usuarios = db.query(models.Usuario).count()
    total_inspecciones = db.query(models.Inspeccion).count()
    
    # Usuarios activos (con inspecciones recientes)
    from sqlalchemy import func, desc
    usuarios_activos = (
        db.query(
            models.Usuario.nombre,
            func.count(models.Inspeccion.id).label("total")
        )
        .join(models.Inspeccion)
        .group_by(models.Usuario.id)
        .order_by(desc("total"))
        .limit(5)
        .all()
    )
    
    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "admin": usuario_admin,
        "total_usuarios": total_usuarios,
        "total_inspecciones": total_inspecciones,
        "usuarios_activos": usuarios_activos,
    })


@router.get("/admin/usuarios", response_class=HTMLResponse)
async def admin_usuarios_list(
    request: Request,
    usuario_admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Lista todos los usuarios del sistema
    """
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="app/templates")
    
    usuarios = db.query(models.Usuario).all()
    
    # Contar inspecciones por usuario
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
        "request": request,
        "admin": usuario_admin,
        "usuarios": usuarios,
        "stats": stats,
    })


@router.get("/admin/usuarios/nuevo", response_class=HTMLResponse)
async def admin_usuario_nuevo_form(
    request: Request,
    usuario_admin: models.Usuario = Depends(require_admin)
):
    """
    Formulario para crear nuevo usuario
    """
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="app/templates")
    
    return templates.TemplateResponse("admin/usuario_form.html", {
        "request": request,
        "admin": usuario_admin,
        "modo": "crear",
        "usuario": None,
    })


@router.post("/admin/usuarios/crear")
async def admin_usuario_crear(
    usuario_admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
    nombre: str = Form(...),
    nombre_visible: str = Form(...),
    pin: str = Form(...),
    rol: str = Form("user")
):
    """
    Crea un nuevo usuario
    """
    # Validaciones
    if len(nombre.strip()) < 2:
        raise HTTPException(400, "Nombre muy corto")
    
    if len(pin) < 4:
        raise HTTPException(400, "PIN debe tener al menos 4 dígitos")
    
    if rol not in ["user", "admin"]:
        raise HTTPException(400, "Rol inválido")
    
    # Verificar que no exista
    existe = db.query(models.Usuario).filter_by(nombre=nombre).first()
    if existe:
        raise HTTPException(400, f"Usuario '{nombre}' ya existe")
    
    # Crear usuario
    nuevo_usuario = models.Usuario(
        nombre=nombre.strip(),
        nombre_visible=nombre_visible.strip(),
        pin_hash=hash_pin(pin),
        rol=rol
    )
    
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)
    
    # Log de auditoría
    registrar_accion(
        db,
        admin_id=usuario_admin.id,
        accion="CREAR_USUARIO",
        detalles=f"Usuario '{nombre}' creado con rol '{rol}'"
    )
    
    return RedirectResponse(
        url="/admin/usuarios?mensaje=Usuario creado exitosamente",
        status_code=303
    )


@router.get("/admin/usuarios/{usuario_id}/editar", response_class=HTMLResponse)
async def admin_usuario_editar_form(
    request: Request,
    usuario_id: int,
    usuario_admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Formulario para editar usuario
    """
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="app/templates")
    
    usuario = db.query(models.Usuario).filter_by(id=usuario_id).first()
    
    if not usuario:
        raise HTTPException(404, "Usuario no encontrado")
    
    return templates.TemplateResponse("admin/usuario_form.html", {
        "request": request,
        "admin": usuario_admin,
        "modo": "editar",
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
    """
    Actualiza un usuario existente
    """
    usuario = db.query(models.Usuario).filter_by(id=usuario_id).first()
    
    if not usuario:
        raise HTTPException(404, "Usuario no encontrado")
    
    # No permitir que un admin se quite permisos a sí mismo
    if usuario.id == usuario_admin.id and rol != "admin":
        raise HTTPException(400, "No puedes quitarte permisos de admin")
    
    # Actualizar datos
    cambios = []
    
    if nombre_visible.strip() != usuario.nombre_visible:
        usuario.nombre_visible = nombre_visible.strip()
        cambios.append("nombre_visible")
    
    if rol != usuario.rol:
        usuario.rol = rol
        cambios.append(f"rol → {rol}")
    
    # Cambiar PIN solo si se proporciona uno nuevo
    if pin and len(pin) >= 4:
        usuario.pin_hash = hash_pin(pin)
        cambios.append("PIN")
    
    db.commit()
    
    # Log de auditoría
    if cambios:
        registrar_accion(
            db,
            admin_id=usuario_admin.id,
            accion="EDITAR_USUARIO",
            detalles=f"Usuario '{usuario.nombre}': {', '.join(cambios)}"
        )
    
    return RedirectResponse(
        url="/admin/usuarios?mensaje=Usuario actualizado",
        status_code=303
    )


@router.post("/admin/usuarios/{usuario_id}/eliminar")
async def admin_usuario_eliminar(
    usuario_id: int,
    usuario_admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Elimina un usuario (solo si no tiene inspecciones)
    """
    usuario = db.query(models.Usuario).filter_by(id=usuario_id).first()
    
    if not usuario:
        raise HTTPException(404, "Usuario no encontrado")
    
    # No permitir eliminar al admin actual
    if usuario.id == usuario_admin.id:
        raise HTTPException(400, "No puedes eliminarte a ti mismo")
    
    # Verificar si tiene inspecciones
    tiene_inspecciones = db.query(models.Inspeccion).filter_by(
        usuario_id=usuario_id
    ).first()
    
    if tiene_inspecciones:
        raise HTTPException(
            400,
            "No se puede eliminar: el usuario tiene inspecciones registradas"
        )
    
    # Eliminar tokens de sesión
    db.query(models.Token).filter_by(usuario_id=usuario_id).delete()
    
    # Eliminar usuario
    nombre_eliminado = usuario.nombre
    db.delete(usuario)
    db.commit()
    
    # Log de auditoría
    registrar_accion(
        db,
        admin_id=usuario_admin.id,
        accion="ELIMINAR_USUARIO",
        detalles=f"Usuario '{nombre_eliminado}' eliminado"
    )
    
    return RedirectResponse(
        url="/admin/usuarios?mensaje=Usuario eliminado",
        status_code=303
    )


@router.get("/admin/logs", response_class=HTMLResponse)
async def admin_logs(
    request: Request,
    usuario_admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Muestra logs de auditoría
    """
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="app/templates")
    
    # Obtener logs recientes (últimos 100)
    from sqlalchemy import desc
    
    logs = (
        db.query(models.LogAuditoria)
        .order_by(desc(models.LogAuditoria.fecha))
        .limit(100)
        .all()
    )
    
    # Cargar nombres de admins
    for log in logs:
        admin = db.query(models.Usuario).filter_by(id=log.admin_id).first()
        log.admin_nombre = admin.nombre if admin else "Desconocido"
    
    return templates.TemplateResponse("admin/logs.html", {
        "request": request,
        "admin": usuario_admin,
        "logs": logs,
    })


# ===============================
# API REST (opcional)
# ===============================

@router.get("/api/admin/usuarios")
async def api_usuarios_list(
    usuario_admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    API REST: Lista usuarios (formato JSON)
    Útil para scripts o integraciones
    """
    usuarios = db.query(models.Usuario).all()
    
    return {
        "ok": True,
        "usuarios": [
            {
                "id": u.id,
                "nombre": u.nombre,
                "nombre_visible": u.nombre_visible,
                "rol": u.rol
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
    """
    API REST: Crear usuario vía JSON
    
    Body:
    {
        "nombre": "Juan",
        "nombre_visible": "Juan Pérez",
        "pin": "1234",
        "rol": "user"
    }
    """
    # ... similar a admin_usuario_crear pero con JSON
    pass