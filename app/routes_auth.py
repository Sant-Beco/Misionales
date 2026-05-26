import os
import logging
from fastapi import APIRouter, HTTPException, Form, Depends, Response, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from collections import defaultdict
import time
 
from app.database import get_db
from app import models
from app.security import (
    hash_pin,
    verify_pin,
    generar_token,
    get_current_user,
    DEFAULT_TOKEN_EXPIRATION_HOURS
)
 
router = APIRouter(tags=["Auth"])
_log = logging.getLogger("routes_auth")
 
# ════════════════════════════════════════════════════════════════
# RATE LIMITING EN MEMORIA
# ════════════════════════════════════════════════════════════════
_intentos_fallidos: dict = defaultdict(list)
_VENTANA_SEG   = 300   # 5 minutos
_MAX_INTENTOS  = 5     # máximo intentos fallidos por IP
 
 
def _ip(request: Request) -> str:
    """Extrae IP real respetando proxies (nginx/cloudflare/nginx)."""
    # Orden de prioridad: X-Forwarded-For > X-Real-IP > client.host
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    
    return request.client.host if request.client else "unknown"
 
 
def _check_rate_limit(ip: str):
    """Lanza 429 si la IP superó el límite de intentos fallidos."""
    ahora = time.time()
    
    # Limpiar intentos antiguos
    _intentos_fallidos[ip] = [
        t for t in _intentos_fallidos[ip]
        if ahora - t < _VENTANA_SEG
    ]
    
    if len(_intentos_fallidos[ip]) >= _MAX_INTENTOS:
        restante = int(_VENTANA_SEG - (ahora - _intentos_fallidos[ip][0]))
        _log.warning(f"Rate limit exceeded for IP: {ip} ({len(_intentos_fallidos[ip])} intentos)")
        raise HTTPException(
            status_code=429,
            detail=f"Demasiados intentos fallidos. Espera {restante}s antes de intentar de nuevo."
        )
 
 
def _registrar_fallo(ip: str):
    """Registra un intento fallido."""
    _intentos_fallidos[ip].append(time.time())
    _log.info(f"Login fallido desde IP: {ip} (total: {len(_intentos_fallidos[ip])})")
 
 
def _limpiar_fallo(ip: str):
    """Limpia historial de la IP tras login exitoso."""
    if ip in _intentos_fallidos:
        del _intentos_fallidos[ip]
 
 
# ════════════════════════════════════════════════════════════════
# REGISTRO (DESHABILITADO EN PRODUCCIÓN)
# ════════════════════════════════════════════════════════════════
 
@router.post("/register")
def registrar_usuario(
    cedula: str = Form(...),
    pin: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Registro de usuario.
    ⚠️ DESHABILITADO EN PRODUCCIÓN — usar admin_cli.py
    """
    if os.getenv("REGISTER_ENABLED", "false").lower() != "true":
        raise HTTPException(
            status_code=403,
            detail="Registro deshabilitado. Contacta al administrador."
        )
 
    cedula_clean = cedula.strip()
 
    # Validación cédula
    if not cedula_clean.isdigit() or not (6 <= len(cedula_clean) <= 10):
        raise HTTPException(
            status_code=400,
            detail="Cédula inválida (6-10 dígitos numéricos)"
        )
 
    # Verificar si ya existe
    existente = db.query(models.Usuario).filter(
        models.Usuario.cedula == cedula_clean
    ).first()
    if existente:
        raise HTTPException(
            status_code=400,
            detail="Cédula ya registrada"
        )
 
    # Validación PIN
    if not pin.isdigit() or not (6 <= len(pin) <= 12):
        raise HTTPException(
            status_code=400,
            detail="PIN debe ser 6-12 dígitos numéricos"
        )
 
    try:
        usuario = models.Usuario(
            cedula=cedula_clean,
            nombre_visible=cedula_clean,
            pin_hash=hash_pin(pin),
            rol="user",
            activo=True
        )
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
        
        _log.info(f"Usuario registrado: cedula={cedula_clean} id={usuario.id}")
        
        return {
            "mensaje": "Usuario creado exitosamente",
            "usuario_id": usuario.id
        }
    except Exception as e:
        db.rollback()
        _log.exception("Error en registro de usuario")
        raise HTTPException(
            status_code=500,
            detail=f"Error creando usuario: {str(e)}"
        )
 
 
# ════════════════════════════════════════════════════════════════
# LOGIN — CON HTTPONLY COOKIE
# ════════════════════════════════════════════════════════════════
 
@router.post("/login")
def login(
    request: Request,
    response: Response,
    cedula: str = Form(...),
    pin: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Login con token en httpOnly cookie (más seguro que localStorage).
    
    Returns:
        JSON con metadata del usuario (sin token en body)
    """
    ip = _ip(request)
 
    # ── PASO 1: Rate limiting ──
    _check_rate_limit(ip)
 
    # ── PASO 2: Validación básica ──
    if not pin or not pin.isdigit() or not (4 <= len(pin) <= 12):
        _registrar_fallo(ip)
        raise HTTPException(
            status_code=401,
            detail="Cédula o PIN incorrecto"
        )
 
    try:
        cedula_clean = cedula.strip()
 
        # ── PASO 3: Buscar usuario por cédula ──
        usuario = (
            db.query(models.Usuario)
            .filter(models.Usuario.cedula == cedula_clean)
            .first()
        )
 
        if not usuario:
            _registrar_fallo(ip)
            _log.warning(f"Login fallido: cédula '{cedula_clean}' no existe (IP: {ip})")
            raise HTTPException(
                status_code=401,
                detail="Cédula o PIN incorrecto"
            )
 
        # ── PASO 4: Verificar PIN ──
        if not verify_pin(pin, usuario.pin_hash):
            _registrar_fallo(ip)
            _log.warning(f"Login fallido: PIN incorrecto para cédula '{cedula_clean}' (IP: {ip})")
            raise HTTPException(
                status_code=401,
                detail="Cédula o PIN incorrecto"
            )
 
        # ── PASO 5: Verificar que esté activo ──
        if not getattr(usuario, "activo", 1):
            _log.warning(f"Login bloqueado: usuario suspendido (cedula={cedula_clean})")
            raise HTTPException(
                status_code=403,
                detail="Usuario suspendido. Contacta al administrador."
            )
 
        # ── PASO 6: Login exitoso ──
        _limpiar_fallo(ip)
 
        # Generar token y expiración
        token = generar_token()
        expiracion_horas = DEFAULT_TOKEN_EXPIRATION_HOURS
        token_expira = datetime.utcnow() + timedelta(hours=expiracion_horas)
 
        usuario.token = token
        usuario.token_expira = token_expira
        db.commit()
 
        # ── PASO 7: Configurar cookie httpOnly ──
        _https = os.getenv("HTTPS_ENABLED", "false").lower() == "true"
        
        response.set_cookie(
            key="access_token",
            value=f"Bearer {token}",
            httponly=True,              # ✅ No accesible desde JS
            max_age=expiracion_horas * 3600,
            samesite="lax",             # ✅ Protección CSRF
            secure=_https,              # ✅ Solo HTTPS en producción
            path="/",                   # ✅ Válido en todo el sitio
        )
 
        _log.info(f"Login exitoso: cedula={cedula_clean} id={usuario.id} rol={usuario.rol} (IP: {ip})")
 
        # ── PASO 8: Response SIN token en body ──
        return {
            "success": True,
            "mensaje": "Login exitoso",
            "usuario_id": usuario.id,
            "nombre": usuario.nombre_visible or usuario.cedula,
            "rol": usuario.rol,
            "expires_in": expiracion_horas * 3600,
            # ❌ NO enviar "access_token" aquí — está en cookie
        }
 
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        _log.exception(f"Error inesperado en login (IP: {ip})")
        raise HTTPException(
            status_code=500,
            detail=f"Error en login: {type(e).__name__}"
        )
 
 
# ════════════════════════════════════════════════════════════════
# LOGOUT
# ════════════════════════════════════════════════════════════════
 
@router.post("/logout")
def logout(
    response: Response,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Logout — invalida token en BD y borra cookie."""
    try:
        # Invalidar token en BD
        usuario.token = None
        usuario.token_expira = None
        db.commit()
        
        # Borrar cookie
        response.delete_cookie(key="access_token", path="/")
        
        _log.info(f"Logout exitoso: usuario_id={usuario.id} cedula={usuario.cedula}")
        
        return {"mensaje": "Sesión cerrada exitosamente"}
    
    except Exception as e:
        db.rollback()
        _log.exception("Error en logout")
        raise HTTPException(
            status_code=500,
            detail=f"Error cerrando sesión: {str(e)}"
        )
 
 
@router.get("/logout")
def logout_get(response: Response):
    """Logout vía GET — borra cookie y redirige al login."""
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie(key="access_token", path="/")
    return resp
 
 
# ════════════════════════════════════════════════════════════════
# VERIFICAR TOKEN / OBTENER USUARIO ACTUAL
# ════════════════════════════════════════════════════════════════
 
@router.get("/verify")
def verify_token(
    usuario: models.Usuario = Depends(get_current_user)
):
    """Verifica si el token en la cookie es válido."""
    return {
        "valid": True,
        "usuario_id": usuario.id,
        "cedula": usuario.cedula,
        "nombre": usuario.nombre_visible or usuario.cedula,
        "rol": usuario.rol,
        "activo": bool(usuario.activo),
        "expires_at": usuario.token_expira.isoformat() if usuario.token_expira else None
    }
 
 
@router.get("/me")
def get_current_user_info(
    usuario: models.Usuario = Depends(get_current_user)
):
    """
    Obtiene información del usuario actual (desde cookie).
    Reemplaza localStorage.getItem() en frontend.
    """
    return {
        "usuario_id": usuario.id,
        "cedula": usuario.cedula,
        "nombre": usuario.nombre_visible or usuario.cedula,
        "nombre_visible": usuario.nombre_visible,
        "rol": usuario.rol,
        "activo": bool(usuario.activo),
    }
 
 
# ════════════════════════════════════════════════════════════════
# CAMBIAR PIN
# ════════════════════════════════════════════════════════════════
 
@router.post("/cambiar-pin")
def cambiar_pin(
    pin_actual: str = Form(...),
    pin_nuevo: str = Form(...),
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cambia el PIN del usuario autenticado."""
    
    # Verificar PIN actual
    if not verify_pin(pin_actual, usuario.pin_hash):
        _log.warning(f"Cambio PIN fallido: PIN actual incorrecto (usuario_id={usuario.id})")
        raise HTTPException(
            status_code=401,
            detail="PIN actual incorrecto"
        )
 
    # Validar nuevo PIN
    if not pin_nuevo.isdigit() or not (6 <= len(pin_nuevo) <= 12):
        raise HTTPException(
            status_code=400,
            detail="El nuevo PIN debe tener entre 6 y 12 dígitos"
        )
 
    # No permitir PIN igual al actual
    if verify_pin(pin_nuevo, usuario.pin_hash):
        raise HTTPException(
            status_code=400,
            detail="El nuevo PIN debe ser diferente al actual"
        )
 
    try:
        usuario.pin_hash = hash_pin(pin_nuevo)
        db.commit()
        
        _log.info(f"PIN actualizado: usuario_id={usuario.id} cedula={usuario.cedula}")
        
        return {"mensaje": "PIN actualizado exitosamente"}
    
    except Exception as e:
        db.rollback()
        _log.exception("Error actualizando PIN")
        raise HTTPException(
            status_code=500,
            detail=f"Error actualizando PIN: {str(e)}"
        )