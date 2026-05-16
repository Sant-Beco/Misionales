# app/security.py
# ─────────────────────────────────────────────────────────────
#  Módulo de seguridad centralizado — Misionales Incubant
#
#  CAMBIOS vs versión anterior (passlib):
#  • Eliminado passlib — incompatible con bcrypt ≥ 4.0
#    (AttributeError: module 'bcrypt' has no attribute '__about__'
#     + ValueError: password cannot be longer than 72 bytes)
#  • Usa bcrypt directamente con pre-hash SHA-256:
#      PIN → SHA-256 (64 bytes hex) → bcrypt
#    Esto elimina el límite de 72 bytes Y permite PINs largos.
#  • PIN mínimo 6 dígitos, máximo 20 (configurable).
#  • Validador de PINs débiles incluido.
#  • Toda la lógica de tokens, roles y dependencias FastAPI
#    se conserva igual que el original.
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
 
MIN_PIN_LENGTH  = 6   # mínimo recomendado para seguridad
MAX_PIN_LENGTH  = 20  # sin límite práctico gracias al prehash
BCRYPT_ROUNDS   = 12  # ~250 ms por hash; subir a 13 para más seguridad
DEFAULT_TOKEN_EXPIRATION_HOURS = 8
 
# PINs triviales bloqueados
_PINES_PROHIBIDOS = {
    "000000","111111","222222","333333","444444","555555",
    "666666","777777","888888","999999","123456","654321",
    "112233","010203","123123","456789","789456","121212",
    "0000000","1234567","12345678","123456789","987654321",
}
 
 
# ══════════════════════════════════════════════════════════════
#  UTILIDAD INTERNA: prehash SHA-256
# ══════════════════════════════════════════════════════════════
 
def _prehash(plain: str) -> bytes:
    """
    Convierte el PIN en 64 bytes hex mediante SHA-256.
    Elimina el límite de 72 bytes de bcrypt y permite PINs
    de cualquier longitud sin truncar ni perder entropía.
    """
    return hashlib.sha256(plain.encode("utf-8")).hexdigest().encode("utf-8")
 
 
# ══════════════════════════════════════════════════════════════
#  VALIDACIÓN DE PIN
# ══════════════════════════════════════════════════════════════
 
def validar_pin(pin: str) -> tuple[bool, str]:
    """
    Valida que un PIN cumple los requisitos mínimos de seguridad.
 
    Reglas:
        - Solo dígitos (0-9)
        - Longitud entre MIN_PIN_LENGTH y MAX_PIN_LENGTH
        - No todos los dígitos iguales
        - No está en la lista de PINs prohibidos
 
    Returns:
        (True, "")               → PIN válido
        (False, "mensaje error") → PIN inválido, motivo incluido
    """
    if not pin.isdigit():
        return False, "El PIN solo debe contener dígitos numéricos (0-9)."
 
    if len(pin) < MIN_PIN_LENGTH:
        return False, f"El PIN debe tener al menos {MIN_PIN_LENGTH} dígitos."
 
    if len(pin) > MAX_PIN_LENGTH:
        return False, f"El PIN no puede superar {MAX_PIN_LENGTH} dígitos."
 
    if len(set(pin)) == 1:
        return False, "El PIN no puede tener todos los dígitos iguales (ej: 111111)."
 
    if pin in _PINES_PROHIBIDOS:
        return False, "El PIN es demasiado simple. Elige uno menos predecible."
 
    return True, ""
 
 
# ══════════════════════════════════════════════════════════════
#  HASH / VERIFY PIN
# ══════════════════════════════════════════════════════════════
 
def hash_pin(plain_pin: str) -> str:
    """
    Genera el hash bcrypt de un PIN.
 
    Flujo interno:
        PIN (str)
          └─→ SHA-256 hex (64 bytes UTF-8)   [prehash]
                └─→ bcrypt ($2b$12$...)       [almacenable]
 
    Uso al crear / actualizar usuario:
        usuario.pin_hash = hash_pin("849273")
 
    Args:
        plain_pin: PIN en texto plano. Debe pasar validar_pin().
 
    Returns:
        Hash bcrypt como str, listo para guardar en BD.
 
    Raises:
        ValueError: Si el PIN no cumple la longitud mínima.
    """
    if len(plain_pin) < MIN_PIN_LENGTH:
        raise ValueError(
            f"PIN demasiado corto. Mínimo {MIN_PIN_LENGTH} dígitos, "
            f"recibido: {len(plain_pin)}."
        )
 
    pre    = _prehash(plain_pin)
    salt   = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(pre, salt)
    return hashed.decode("utf-8")
 
 
def verify_pin(plain_pin: str, hashed_pin: str) -> bool:
    """
    Verifica que un PIN en texto plano coincida con su hash.
 
    ⚠ Nota de migración:
        Si la BD contiene hashes generados con passlib SIN prehash,
        esos hashes NO coincidirán con esta función (porque passlib
        pasaba el PIN directamente a bcrypt, no el SHA-256).
        Solución: resetear el PIN de esos usuarios con admin_cli
        usando la nueva función hash_pin().
 
    Args:
        plain_pin:  PIN ingresado por el usuario.
        hashed_pin: Hash almacenado en BD ($2b$12$...).
 
    Returns:
        True si coincide, False en cualquier otro caso
        (nunca lanza excepción al llamador).
    """
    try:
        pre          = _prehash(plain_pin)
        hashed_bytes = hashed_pin.encode("utf-8")
        return bcrypt.checkpw(pre, hashed_bytes)
    except Exception:
        return False
 
 
# ══════════════════════════════════════════════════════════════
#  TOKENS DE SESIÓN
# ══════════════════════════════════════════════════════════════
 
def generar_token(length: int = 48) -> str:
    """
    Genera un token de sesión criptográficamente seguro.
 
    Args:
        length: Longitud en bytes (default 48 → 96 chars hex).
                Aumentado de 32→48 para mayor entropía.
 
    Returns:
        String hexadecimal de `length * 2` caracteres.
    """
    return secrets.token_hex(length)
 
 
def calcular_expiracion(horas: int = DEFAULT_TOKEN_EXPIRATION_HOURS) -> datetime:
    """
    Calcula la fecha/hora de expiración del token (UTC naive,
    compatible con datetime.utcnow() en las comparaciones).
 
    Returns:
        datetime sin tzinfo (UTC) con la hora de expiración.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=horas)
 
 
# ══════════════════════════════════════════════════════════════
#  DEPENDENCIAS FASTAPI
# ══════════════════════════════════════════════════════════════
 
def get_db():
    """Dependencia: sesión de base de datos."""
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
 
    Acepta el token desde dos fuentes (en orden de prioridad):
      1. Cookie 'access_token'          → navegación directa por URL
      2. Header 'Authorization: Bearer' → fetch/axios del frontend
 
    Raises:
        HTTPException(401): Token ausente, inválido o expirado.
        HTTPException(403): Usuario inactivo.
 
    Returns:
        Objeto Usuario autenticado.
    """
    token = None
 
    # 1. Cookie
    cookie_value = request.cookies.get("access_token")
    if cookie_value:
        scheme, cookie_token = get_authorization_scheme_param(cookie_value)
        if scheme.lower() == "bearer" and cookie_token:
            token = cookie_token
 
    # 2. Header Authorization (fallback)
    if not token and authorization:
        scheme, header_token = get_authorization_scheme_param(authorization)
        if scheme.lower() == "bearer" and header_token:
            token = header_token
 
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Se requiere autenticación. Inicia sesión para continuar."
        )
 
    # Buscar en BD
    usuario = db.query(Usuario).filter(Usuario.token == token).first()
 
    if not usuario:
        raise HTTPException(
            status_code=401,
            detail="Sesión no válida. Por favor inicia sesión nuevamente."
        )
 
    # Verificar expiración
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
 
    # Verificar que el usuario esté activo (si el modelo lo soporta)
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
        @router.post("/admin/accion")
        def accion(
            usuario: Usuario = Depends(require_role(["admin"]))
        ):
            ...
 
    Args:
        allowed_roles: Lista de roles permitidos,
                       ej. ["admin", "supervisor"]
 
    Returns:
        Función dependencia FastAPI que valida el rol.
 
    Raises:
        HTTPException(403): Si el usuario no tiene el rol requerido.
    """
    def role_checker(usuario: Usuario = Depends(get_current_user)) -> Usuario:
        if usuario.rol not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Permiso denegado. "
                    f"Roles permitidos: {', '.join(allowed_roles)}. "
                    f"Tu rol actual: {usuario.rol}."
                )
            )
        return usuario
    return role_checker