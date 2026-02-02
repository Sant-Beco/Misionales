# app/routes_auth.py - VERSIÓN CORREGIDA

from fastapi import APIRouter, HTTPException, Form, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.database import SessionLocal, get_db
from app import models
from app.security import (
    hash_pin,
    verify_pin,
    generar_token,
    get_current_user,
    DEFAULT_TOKEN_EXPIRATION_HOURS
)

router = APIRouter(tags=["Auth"])


# ============================
# REGISTRO (opcional)
# ============================

@router.post("/register")
def registrar_usuario(
    nombre: str = Form(...),
    pin: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Registra un nuevo usuario
    
    Nota: En producción, este endpoint debería estar protegido
    o deshabilitado completamente. Solo administradores deberían
    crear usuarios (usar admin_cli.py)
    """
    try:
        nombre_clean = " ".join(nombre.strip().split()).capitalize()

        # Verificar si ya existe
        existente = (
            db.query(models.Usuario)
            .filter(models.Usuario.nombre == nombre_clean)
            .first()
        )
        if existente:
            return JSONResponse(
                {"mensaje": "Usuario ya existe"},
                status_code=400
            )

        # ✅ Usar helper centralizado
        pin_hash = hash_pin(pin)

        usuario = models.Usuario(
            nombre=nombre_clean,
            nombre_visible=nombre_clean,
            pin_hash=pin_hash
        )

        db.add(usuario)
        db.commit()
        db.refresh(usuario)

        return {
            "mensaje": "Usuario creado exitosamente",
            "usuario_id": usuario.id,
            "nombre": usuario.nombre
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error creando usuario: {str(e)}"
        )


# ============================
# LOGIN - ✅ CORREGIDO
# ============================

@router.post("/login")
def login(
    nombre: str = Form(...),
    pin: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Autentica un usuario y retorna token de sesión
    
    Returns:
        {
            "access_token": "...",
            "token_type": "bearer",
            "expires_in": 86400,  # segundos
            "usuario_id": 1,
            "nombre": "Juan Pérez"
        }
    """
    try:
        nombre_clean = " ".join(nombre.strip().split()).capitalize()

        # Buscar usuario
        usuario = (
            db.query(models.Usuario)
            .filter(models.Usuario.nombre == nombre_clean)
            .first()
        )

        if not usuario:
            raise HTTPException(
                status_code=401,
                detail="Usuario o PIN incorrecto"
            )

        # ✅ Verificar PIN con helper centralizado
        if not verify_pin(pin, usuario.pin_hash):
            raise HTTPException(
                status_code=401,
                detail="Usuario o PIN incorrecto"
            )

        # Generar token seguro
        token = generar_token()
        
        # Configurar expiración
        expiracion_horas = DEFAULT_TOKEN_EXPIRATION_HOURS
        token_expira = datetime.utcnow() + timedelta(hours=expiracion_horas)

        # Actualizar usuario
        usuario.token = token
        usuario.token_expira = token_expira
        
        db.commit()

        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": expiracion_horas * 3600,  # En segundos
            "usuario_id": usuario.id,
            "nombre": usuario.nombre
        }

    except HTTPException:
        # Re-lanzar excepciones HTTP
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error en login: {str(e)}"
        )


# ============================
# LOGOUT - ✅ NUEVO
# ============================

@router.post("/logout")
def logout(
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cierra la sesión del usuario invalidando su token
    
    Requiere:
        - Header Authorization: Bearer <token>
    
    Returns:
        {"mensaje": "Sesión cerrada exitosamente"}
    """
    try:
        # Invalidar token
        usuario.token = None
        usuario.token_expira = None
        
        db.commit()

        return {
            "mensaje": "Sesión cerrada exitosamente"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error cerrando sesión: {str(e)}"
        )


# ============================
# VERIFICAR TOKEN (útil para frontend)
# ============================

@router.get("/verify")
def verify_token(
    usuario: models.Usuario = Depends(get_current_user)
):
    """
    Verifica si el token actual es válido
    
    Útil para que el frontend verifique si la sesión sigue activa
    
    Returns:
        {
            "valid": true,
            "usuario_id": 1,
            "nombre": "Juan Pérez",
            "expires_at": "2026-01-28T10:30:00Z"
        }
    """
    return {
        "valid": True,
        "usuario_id": usuario.id,
        "nombre": usuario.nombre,
        "expires_at": usuario.token_expira.isoformat() if usuario.token_expira else None
    }


# ============================
# CAMBIAR PIN (protegido)
# ============================

@router.post("/cambiar-pin")
def cambiar_pin(
    pin_actual: str = Form(...),
    pin_nuevo: str = Form(...),
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Permite al usuario cambiar su PIN
    
    Args:
        pin_actual: PIN actual del usuario
        pin_nuevo: Nuevo PIN deseado
    
    Returns:
        {"mensaje": "PIN actualizado exitosamente"}
    """
    try:
        # Verificar PIN actual
        if not verify_pin(pin_actual, usuario.pin_hash):
            raise HTTPException(
                status_code=401,
                detail="PIN actual incorrecto"
            )
        
        # Validar nuevo PIN
        if not pin_nuevo.isdigit():
            raise HTTPException(
                status_code=400,
                detail="El PIN debe contener solo números"
            )
        
        if not (4 <= len(pin_nuevo) <= 6):
            raise HTTPException(
                status_code=400,
                detail="El PIN debe tener entre 4 y 6 dígitos"
            )
        
        # Actualizar PIN
        usuario.pin_hash = hash_pin(pin_nuevo)
        db.commit()

        return {
            "mensaje": "PIN actualizado exitosamente"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error actualizando PIN: {str(e)}"
        )