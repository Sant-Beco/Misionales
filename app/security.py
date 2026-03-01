# app/security.py - VERSIÓN MEJORADA
"""
Módulo de seguridad centralizado para MISONALES

Incluye:
- Validación de tokens
- Hash de PINs (usando passlib para consistencia con admin_cli)
- Generación de tokens seguros
- Helpers de autenticación
"""

from fastapi import Header, HTTPException, Depends, Request
from fastapi.security.utils import get_authorization_scheme_param
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from passlib.context import CryptContext
import secrets

from app.database import SessionLocal
from app.models import Usuario


# ======================
# CONTEXTO DE PASSWORDS
# ======================

# ✅ Usa passlib (igual que admin_cli.py)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ======================
# HELPERS DE HASH
# ======================

def hash_pin(pin: str) -> str:
    """
    Genera hash bcrypt de un PIN
    
    Args:
        pin: PIN en texto plano (4-6 dígitos)
    
    Returns:
        Hash bcrypt del PIN
    
    Ejemplo:
        >>> hash_pin("1234")
        '$2b$12$...'
    """
    return pwd_context.hash(pin)


def verify_pin(plain_pin: str, hashed_pin: str) -> bool:
    """
    Verifica si un PIN coincide con su hash
    
    Args:
        plain_pin: PIN en texto plano
        hashed_pin: Hash almacenado en BD
    
    Returns:
        True si coincide, False si no
    
    Ejemplo:
        >>> verify_pin("1234", stored_hash)
        True
    """
    return pwd_context.verify(plain_pin, hashed_pin)


# ======================
# GENERACIÓN DE TOKENS
# ======================

def generar_token(length: int = 32) -> str:
    """
    Genera un token seguro para sesiones
    
    Args:
        length: Longitud del token en bytes (default 32 = 64 chars hex)
    
    Returns:
        Token hexadecimal seguro
    
    Ejemplo:
        >>> generar_token()
        'a1b2c3d4e5f6...'  # 64 caracteres
    """
    return secrets.token_hex(length)


# ======================
# VALIDACIÓN DE TOKENS
# ======================

def get_db():
    """
    Dependencia para obtener sesión de base de datos
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> Usuario:
    """
    Valida token y retorna usuario autenticado.
    Acepta token desde:
      1. Cookie 'access_token' (navegación por URL desde el browser)
      2. Header 'Authorization: Bearer <token>' (peticiones fetch/axios)
    
    Raises:
        HTTPException(401): Si el token es inválido o ha expirado
    
    Returns:
        Usuario: Objeto del usuario autenticado
    """

    token = None

    # 1. Intentar obtener token desde cookie (navegación directa por URL)
    cookie_raw = request.cookies.get("access_token")
    if cookie_raw:
        scheme, credentials = get_authorization_scheme_param(cookie_raw)
        if scheme.lower() == "bearer" and credentials:
            token = credentials

    # 2. Si no hay cookie, intentar desde header Authorization (fetch/axios)
    if not token:
        authorization = request.headers.get("Authorization")
        if authorization:
            scheme, credentials = get_authorization_scheme_param(authorization)
            if scheme.lower() == "bearer" and credentials:
                token = credentials

    # 3. Si no se encontró token por ninguna vía, rechazar
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Se requiere autenticación. Inicia sesión para continuar."
        )
    
    # 4. Buscar usuario por token
    usuario = (
        db.query(Usuario)
        .filter(Usuario.token == token)
        .first()
    )
    
    if not usuario:
        raise HTTPException(
            status_code=401,
            detail="Sesión no válida. Por favor inicie sesión nuevamente."
        )
    
    # 5. Verificar expiración
    if not usuario.token_expira:
        raise HTTPException(
            status_code=401,
            detail="Token sin fecha de expiración. Contacte al administrador."
        )
    
    if usuario.token_expira < datetime.utcnow():
        raise HTTPException(
            status_code=401,
            detail="Sesión expirada. Por favor inicie sesión nuevamente."
        )
    
    # ✅ Todo OK - retornar usuario
    return usuario


# ======================
# OPCIONAL: Verificación de roles
# ======================

def require_role(allowed_roles: list):
    """
    Decorator para verificar que el usuario tiene un rol específico
    
    Uso:
        @router.post("/admin/action")
        def admin_action(
            usuario: Usuario = Depends(require_role(["admin", "supervisor"]))
        ):
            # Solo admins y supervisores pueden acceder
            ...
    
    Args:
        allowed_roles: Lista de roles permitidos
    
    Returns:
        Función que valida el rol del usuario
    """
    def role_checker(usuario: Usuario = Depends(get_current_user)) -> Usuario:
        if usuario.rol not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Permiso denegado. Se requiere uno de estos roles: {', '.join(allowed_roles)}"
            )
        return usuario
    
    return role_checker


# ======================
# CONSTANTES
# ======================

# Duración por defecto de tokens (en horas)
DEFAULT_TOKEN_EXPIRATION_HOURS = 24

# Longitud mínima y máxima de PIN
MIN_PIN_LENGTH = 4
MAX_PIN_LENGTH = 6