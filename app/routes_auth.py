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

# ============================
# RATE LIMITING EN MEMORIA
# ============================
# Estructura: { ip: [(timestamp, nombre), ...] }
_intentos_fallidos: dict = defaultdict(list)
_VENTANA_SEG   = 300   # 5 minutos
_MAX_INTENTOS  = 5     # máximo intentos fallidos por IP en esa ventana

def _ip(request: Request) -> str:
    """Extrae IP real respetando proxies (nginx/cloudflare)."""
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

def _check_rate_limit(ip: str):
    """Lanza 429 si la IP superó el límite de intentos fallidos."""
    ahora = time.time()
    # Limpiar intentos fuera de ventana
    _intentos_fallidos[ip] = [
        t for t in _intentos_fallidos[ip]
        if ahora - t < _VENTANA_SEG
    ]
    if len(_intentos_fallidos[ip]) >= _MAX_INTENTOS:
        restante = int(_VENTANA_SEG - (ahora - _intentos_fallidos[ip][0]))
        raise HTTPException(
            status_code=429,
            detail=f"Demasiados intentos fallidos. Espera {restante}s antes de intentar de nuevo."
        )

def _registrar_fallo(ip: str):
    _intentos_fallidos[ip].append(time.time())

def _limpiar_fallo(ip: str):
    """Limpia historial de la IP tras login exitoso."""
    _intentos_fallidos.pop(ip, None)


# ============================
# REGISTRO
# ✅ BLOQUEANTE #1: deshabilitado en producción
# Habilitar solo localmente con REGISTER_ENABLED=true en .env
# ============================

@router.post("/register")
def registrar_usuario(
    nombre: str = Form(...),
    pin: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Registro de usuario.
    DESHABILITADO EN PRODUCCIÓN — usar admin_cli.py para crear usuarios.
    Habilitar con REGISTER_ENABLED=true en .env solo para setup inicial.
    """
    if os.getenv("REGISTER_ENABLED", "false").lower() != "true":
        raise HTTPException(
            status_code=403,
            detail="Registro deshabilitado. Contacta al administrador."
        )

    nombre_clean = " ".join(nombre.strip().split())

    existente = db.query(models.Usuario).filter(
        models.Usuario.nombre == nombre_clean
    ).first()
    if existente:
        return JSONResponse({"mensaje": "Usuario ya existe"}, status_code=400)

    if not pin.isdigit() or not (4 <= len(pin) <= 6):
        raise HTTPException(status_code=400, detail="PIN debe ser 4-6 dígitos numéricos")

    try:
        usuario = models.Usuario(
            nombre=nombre_clean,
            nombre_visible=nombre_clean,
            pin_hash=hash_pin(pin)
        )
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
        return {"mensaje": "Usuario creado exitosamente", "usuario_id": usuario.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creando usuario: {str(e)}")


# ============================
# LOGIN
# ✅ BLOQUEANTE #4: rate limiting
# ✅ IMPORTANTE: verifica activo
# ✅ IMPORTANTE: cookie secure según HTTPS_ENABLED
# ============================

@router.post("/login")
def login(
    request: Request,
    response: Response,
    nombre: str = Form(...),
    pin: str = Form(...),
    db: Session = Depends(get_db)
):
    ip = _ip(request)

    # ── Rate limiting ANTES de tocar la BD ──────────────────────────
    _check_rate_limit(ip)

    # ── Validación básica del PIN (evita queries con inputs basura) ──
    if not pin or not pin.isdigit() or not (4 <= len(pin) <= 6):
        _registrar_fallo(ip)
        raise HTTPException(status_code=401, detail="Usuario o PIN incorrecto")

    try:
        nombre_clean = " ".join(nombre.strip().split())

        from sqlalchemy import func as _func
        usuario = (
            db.query(models.Usuario)
            .filter(_func.lower(models.Usuario.nombre) == nombre_clean.lower())
            .first()
        )

        if not usuario:
            _registrar_fallo(ip)
            raise HTTPException(status_code=401, detail="Usuario o PIN incorrecto")

        if not verify_pin(pin, usuario.pin_hash):
            _registrar_fallo(ip)
            raise HTTPException(status_code=401, detail="Usuario o PIN incorrecto")

        # ✅ IMPORTANTE: verificar que el usuario esté activo
        if not getattr(usuario, "activo", 1):
            raise HTTPException(
                status_code=403,
                detail="Usuario suspendido. Contacta al administrador."
            )

        # Login exitoso — limpiar historial de fallos
        _limpiar_fallo(ip)

        # Generar token y expiración
        token = generar_token()
        expiracion_horas = DEFAULT_TOKEN_EXPIRATION_HOURS
        token_expira = datetime.utcnow() + timedelta(hours=expiracion_horas)

        usuario.token = token
        usuario.token_expira = token_expira
        db.commit()

        # ✅ IMPORTANTE: secure=True cuando HTTPS_ENABLED=true
        _https = os.getenv("HTTPS_ENABLED", "false").lower() == "true"
        response.set_cookie(
            key="access_token",
            value=f"Bearer {token}",
            httponly=True,
            max_age=expiracion_horas * 3600,
            samesite="lax",
            secure=_https,
        )

        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": expiracion_horas * 3600,
            "usuario_id": usuario.id,
            "nombre": usuario.nombre_visible or usuario.nombre,
            "rol": usuario.rol,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        _log.exception("❌ Error inesperado en /auth/login")
        raise HTTPException(status_code=500, detail=f"Error en login: {type(e).__name__}: {str(e)}")


# ============================
# LOGOUT
# ============================

@router.post("/logout")
def logout(
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        usuario.token = None
        usuario.token_expira = None
        db.commit()
        return {"mensaje": "Sesión cerrada exitosamente"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error cerrando sesión: {str(e)}")


@router.get("/logout")
def logout_get():
    """Cierre de sesión vía GET — borra cookie y redirige al login."""
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie("access_token")
    return resp


# ============================
# VERIFICAR TOKEN
# ============================

@router.get("/verify")
def verify_token(
    usuario: models.Usuario = Depends(get_current_user)
):
    return {
        "valid": True,
        "usuario_id": usuario.id,
        "nombre": usuario.nombre_visible or usuario.nombre,
        "expires_at": usuario.token_expira.isoformat() if usuario.token_expira else None
    }


# ============================
# CAMBIAR PIN
# ============================

@router.post("/cambiar-pin")
def cambiar_pin(
    pin_actual: str = Form(...),
    pin_nuevo: str = Form(...),
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not verify_pin(pin_actual, usuario.pin_hash):
        raise HTTPException(status_code=401, detail="PIN actual incorrecto")

    if not pin_nuevo.isdigit() or not (4 <= len(pin_nuevo) <= 6):
        raise HTTPException(status_code=400, detail="El PIN debe tener entre 4 y 6 dígitos")

    try:
        usuario.pin_hash = hash_pin(pin_nuevo)
        db.commit()
        return {"mensaje": "PIN actualizado exitosamente"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error actualizando PIN: {str(e)}")        