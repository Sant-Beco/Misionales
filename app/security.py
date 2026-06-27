# app/security.py
# ─────────────────────────────────────────────────────────────
#  Módulo de seguridad — Misionales Incubant  v3.1
#
#  SIN passlib. Usa bcrypt directo + prehash SHA-256.
#
#  COMPATIBILIDAD DUAL en verify_pin():
#    1. Formato nuevo  → SHA-256(PIN) → bcrypt   (admin_cli v3.1)
#    2. Formato antiguo → PIN directo → bcrypt   (passlib/admin_cli v3.0)
#  Los usuarios existentes entran sin resetear su PIN.
#  Al cambiar el PIN quedan en formato nuevo automáticamente.
#
#  PIN mínimo: 4 dígitos (compatibilidad con base de datos existente)
# ─────────────────────────────────────────────────────────────

import bcrypt
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import Header, HTTPException, Depends, Request
from fastapi.security.utils import get_authorization_scheme_param
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Usuario


# ══════════════════════════════════════════════════════════════
#  CONSTANTES
# ══════════════════════════════════════════════════════════════

MIN_PIN_LENGTH  = 4   # 4 para compatibilidad con PINs existentes en BD
MAX_PIN_LENGTH  = 20
BCRYPT_ROUNDS   = 12
DEFAULT_TOKEN_EXPIRATION_HOURS = 24

_PINES_PROHIBIDOS = {
    "0000","1234","4321","1111","2222","3333","4444","5555",
    "6666","7777","8888","9999",
    "000000","111111","222222","333333","444444","555555",
    "666666","777777","888888","999999","123456","654321",
    "112233","010203","123123","456789","789456","121212",
    "0000000","1234567","12345678","123456789","987654321",
}


# ══════════════════════════════════════════════════════════════
#  PREHASH SHA-256 (formato nuevo)
# ══════════════════════════════════════════════════════════════

def _prehash(plain: str) -> bytes:
    """SHA-256(PIN) → 64 bytes hex UTF-8. Elimina límite de 72 bytes de bcrypt."""
    return hashlib.sha256(plain.encode("utf-8")).hexdigest().encode("utf-8")


# ══════════════════════════════════════════════════════════════
#  VALIDACIÓN DE PIN
# ══════════════════════════════════════════════════════════════

def validar_pin(pin: str) -> tuple[bool, str]:
    """
    Valida requisitos mínimos de seguridad del PIN.

    Returns:
        (True, "")               → válido
        (False, "mensaje error") → inválido con motivo
    """
    if not pin or not pin.isdigit():
        return False, "El PIN solo debe contener dígitos (0-9)."
    if len(pin) < MIN_PIN_LENGTH:
        return False, f"El PIN debe tener al menos {MIN_PIN_LENGTH} dígitos."
    if len(pin) > MAX_PIN_LENGTH:
        return False, f"El PIN no puede superar {MAX_PIN_LENGTH} dígitos."
    if len(set(pin)) == 1:
        return False, "El PIN no puede tener todos los dígitos iguales."
    if pin in _PINES_PROHIBIDOS:
        return False, "El PIN es demasiado simple. Elige uno menos predecible."
    return True, ""


# ══════════════════════════════════════════════════════════════
#  HASH / VERIFY
# ══════════════════════════════════════════════════════════════

def hash_pin(plain_pin: str) -> str:
    """
    Genera hash bcrypt con prehash SHA-256.

    Flujo:
        PIN (str) → SHA-256 hex (64 bytes) → bcrypt ($2b$12$...)

    Compatibilidad: los hashes generados aquí son verificables
    por verify_pin() tanto en security.py como en admin_cli.py.

    Raises:
        ValueError: si el PIN es más corto que MIN_PIN_LENGTH.
    """
    if len(plain_pin) < MIN_PIN_LENGTH:
        raise ValueError(f"PIN demasiado corto. Mínimo {MIN_PIN_LENGTH} dígitos.")

    pre    = _prehash(plain_pin)
    salt   = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(pre, salt)
    return hashed.decode("utf-8")


def verify_pin(plain_pin: str, hashed_pin: str) -> bool:
    """
    Verifica el PIN contra su hash — modo de compatibilidad dual.

    Intento 1 — Formato nuevo (admin_cli v3.1 + security v3.1):
        SHA-256(PIN) → bcrypt.checkpw

    Intento 2 — Formato antiguo (passlib / admin_cli v3.0):
        PIN directo → bcrypt.checkpw
        (passlib pasaba el PIN directo a bcrypt sin prehash)

    Si el usuario tiene hash antiguo y su PIN directo coincide,
    puede entrar. La próxima vez que cambie el PIN quedará en
    formato nuevo automáticamente.

    Returns:
        True si coincide por cualquiera de los dos métodos.
        False en cualquier caso de error (nunca lanza excepción).
    """
    if not plain_pin or not hashed_pin:
        return False

    hashed_bytes = hashed_pin.encode("utf-8")

    # Intento 1: formato nuevo (SHA-256 + bcrypt)
    try:
        if bcrypt.checkpw(_prehash(plain_pin), hashed_bytes):
            return True
    except Exception:
        pass

    # Intento 2: formato antiguo (passlib, PIN directo a bcrypt)
    try:
        pin_bytes = plain_pin.encode("utf-8")
        if bcrypt.checkpw(pin_bytes, hashed_bytes):
            return True
    except Exception:
        pass

    return False


# ══════════════════════════════════════════════════════════════
#  TOKENS DE SESIÓN
# ══════════════════════════════════════════════════════════════

def generar_token(length: int = 48) -> str:
    """Token de sesión seguro. 48 bytes → 96 chars hex."""
    return secrets.token_hex(length)


def calcular_expiracion(horas: int = DEFAULT_TOKEN_EXPIRATION_HOURS) -> datetime:
    """Fecha de expiración UTC naive (compatible con datetime.utcnow())."""
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=horas)


# ══════════════════════════════════════════════════════════════
#  DEPENDENCIAS FASTAPI
# ══════════════════════════════════════════════════════════════

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    request: Request,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
) -> Usuario:
    """
    Valida el token y retorna el usuario autenticado.

    Prioridad de token:
      1. Cookie 'access_token'          → navegación directa
      2. Header 'Authorization: Bearer' → fetch/axios del frontend

    Raises:
        HTTPException 401: token ausente, inválido o expirado.
        HTTPException 403: usuario inactivo.
    """
    token = None

    # 1. Cookie
    cookie_value = request.cookies.get("access_token")
    if cookie_value:
        scheme, cookie_token = get_authorization_scheme_param(cookie_value)
        if scheme.lower() == "bearer" and cookie_token:
            token = cookie_token

    # 2. Header Authorization
    if not token and authorization:
        scheme, header_token = get_authorization_scheme_param(authorization)
        if scheme.lower() == "bearer" and header_token:
            token = header_token

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Se requiere autenticación. Inicia sesión para continuar."
        )

    usuario = db.query(Usuario).filter(Usuario.token == token).first()

    if not usuario:
        raise HTTPException(
            status_code=401,
            detail="Sesión no válida. Por favor inicia sesión nuevamente."
        )

    if not usuario.token_expira:
        raise HTTPException(
            status_code=401,
            detail="Token sin fecha de expiración. Contacta al administrador."
        )

    if usuario.token_expira < datetime.utcnow():
        raise HTTPException(
            status_code=401,
            detail="Sesión expirada. Por favor inicia sesión nuevamente."
        )

    if hasattr(usuario, "activo") and not usuario.activo:
        raise HTTPException(
            status_code=403,
            detail="Usuario inactivo. Contacta al administrador."
        )

    return usuario


# ══════════════════════════════════════════════════════════════
#  CONTROL DE ROLES
# ══════════════════════════════════════════════════════════════

def require_role(allowed_roles: list):
    """
    Dependencia de rol para proteger endpoints.

    Uso:
        @router.get("/admin/panel")
        def panel(usuario: Usuario = Depends(require_role(["admin"]))):
            ...
    """
    def role_checker(usuario: Usuario = Depends(get_current_user)) -> Usuario:
        if usuario.rol not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Permiso denegado. "
                    f"Roles permitidos: {', '.join(allowed_roles)}. "
                    f"Tu rol: {usuario.rol}."
                )
            )
        return usuario
    return role_checker