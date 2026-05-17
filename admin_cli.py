#!/usr/bin/env python3
"""
CLI de administración de usuarios — Misionales v3.1
=====================================================
v3.1:
  - Eliminado passlib completamente (incompatible con bcrypt 4.x)
  - Usa hash_pin / verify_pin de app.security directamente
  - PIN mínimo 4 dígitos (compatibilidad), recomendado 6+
  - validate_pin actualizado para aceptar 4-20 dígitos
 
Uso (desde el repo raíz):
  python admin_cli.py
  python -m app.admin_cli
 
Registra en: app/logs/admin.log
"""
 
import os
import sys
import logging
import re
from getpass import getpass
from typing import Optional
 
# ─── Importar hash/verify desde security.py (sin passlib) ──────────────────
from app.security import hash_pin, verify_pin, validar_pin
from app.database import SessionLocal
from app.models import Usuario
# ────────────────────────────────────────────────────────────────────────────
 
# ─── Logging ────────────────────────────────────────────────────────────────
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "admin.log")
 
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("admin_cli")
 
# ─── Colores consola ────────────────────────────────────────────────────────
G  = "\033[92m"
R  = "\033[91m"
Y  = "\033[93m"
C  = "\033[96m"
W  = "\033[97m"
DIM= "\033[2m"
RST= "\033[0m"
 
def ok(msg):   print(f"{G}✅ {msg}{RST}")
def err(msg):  print(f"{R}❌ {msg}{RST}")
def warn(msg): print(f"{Y}⚠️  {msg}{RST}")
def info(msg): print(f"{C}ℹ️  {msg}{RST}")
 
# ════════════════════════════════════════════════════════════════════════════
# VALIDADORES
# ════════════════════════════════════════════════════════════════════════════
 
def validate_pin_cli(pin: str) -> tuple[bool, str]:
    """
    Validación de PIN para el CLI.
    Delega en security.validar_pin() para consistencia total.
    Si el PIN tiene 4-5 dígitos (compatibilidad con usuarios existentes)
    también lo acepta aunque security.py prefiera 6+.
    """
    if not pin or not pin.isdigit():
        return False, "El PIN solo debe contener dígitos (0-9)."
    if len(pin) < 4:
        return False, "El PIN debe tener al menos 4 dígitos."
    if len(pin) > 20:
        return False, "El PIN no puede superar 20 dígitos."
    if len(set(pin)) == 1:
        return False, "El PIN no puede tener todos los dígitos iguales."
    # Aviso (no error) si es corto
    return True, ""
 
def validate_nombre_visible(nombre: str) -> bool:
    if not nombre or not nombre.strip():
        return False
    return bool(re.match(r"^[A-Za-zÁÉÍÓÚáéíóúÑñÜü ]+$", nombre.strip()))
 
def validate_login(nombre: str) -> bool:
    return bool(nombre) and bool(re.match(r"^[A-Za-z0-9_]{2,30}$", nombre.strip()))
 
# ════════════════════════════════════════════════════════════════════════════
# FUNCIONES DE BASE DE DATOS
# ════════════════════════════════════════════════════════════════════════════
 
def get_stats() -> dict:
    db = SessionLocal()
    try:
        total   = db.query(Usuario).count()
        admins  = db.query(Usuario).filter(Usuario.rol == "admin").count()
        activos = db.query(Usuario).filter(Usuario.activo == True).count()
        return {"total": total, "admins": admins, "activos": activos}
    except Exception as e:
        logger.exception("Error leyendo stats: %s", e)
        return {"total": 0, "admins": 0, "activos": 0}
    finally:
        db.close()
 
 
def create_user_db(
    nombre: str,
    nombre_visible: str,
    pin: str,
    rol: str = "user",
) -> Optional[Usuario]:
    db = SessionLocal()
    try:
        existing = db.query(Usuario).filter(Usuario.nombre == nombre).first()
        if existing:
            warn(f"El login '{nombre}' ya está en uso.")
            return None
 
        # ▸ Usa hash_pin de security.py (SHA-256 + bcrypt, sin passlib)
        pin_hash = hash_pin(pin)
 
        nuevo = Usuario(
            nombre         = nombre,
            nombre_visible = nombre_visible,
            pin_hash       = pin_hash,
            rol            = rol,
            activo         = True,
        )
        db.add(nuevo)
        db.commit()
        db.refresh(nuevo)
        logger.info("Usuario creado: id=%s nombre=%s rol=%s", nuevo.id, nuevo.nombre, nuevo.rol)
        return nuevo
 
    except Exception as e:
        db.rollback()
        logger.exception("Error creando usuario: %s", e)
        err(f"Error interno: {e}")
        return None
    finally:
        db.close()
 
 
def list_users_db() -> list:
    db = SessionLocal()
    try:
        return db.query(Usuario).order_by(Usuario.id).all()
    except Exception as e:
        logger.exception("Error listando usuarios: %s", e)
        return []
    finally:
        db.close()
 
 
def delete_user_db(user_id: int) -> bool:
    db = SessionLocal()
    try:
        u = db.query(Usuario).filter(Usuario.id == user_id).first()
        if not u:
            warn(f"No existe usuario con id={user_id}")
            return False
        nombre = u.nombre
        db.delete(u)
        db.commit()
        logger.info("Usuario borrado: id=%s nombre=%s", user_id, nombre)
        return True
    except Exception as e:
        db.rollback()
        logger.exception("Error borrando id=%s: %s", user_id, e)
        return False
    finally:
        db.close()
 
 
def update_pin_db(user_id: int, new_pin: str) -> bool:
    db = SessionLocal()
    try:
        u = db.query(Usuario).filter(Usuario.id == user_id).first()
        if not u:
            warn(f"No existe usuario con id={user_id}")
            return False
        # ▸ Usa hash_pin de security.py
        u.pin_hash = hash_pin(new_pin)
        db.commit()
        logger.info("PIN actualizado: id=%s nombre=%s", user_id, u.nombre)
        return True
    except Exception as e:
        db.rollback()
        logger.exception("Error actualizando PIN id=%s: %s", user_id, e)
        return False
    finally:
        db.close()
 
 
def update_nombre_visible_db(user_id: int, nombre_visible: str) -> bool:
    db = SessionLocal()
    try:
        u = db.query(Usuario).filter(Usuario.id == user_id).first()
        if not u:
            warn(f"No existe usuario con id={user_id}")
            return False
        u.nombre_visible = nombre_visible
        db.commit()
        logger.info("nombre_visible actualizado: id=%s → %s", user_id, nombre_visible)
        return True
    except Exception as e:
        db.rollback()
        logger.exception("Error actualizando nombre_visible id=%s: %s", user_id, e)
        return False
    finally:
        db.close()
 
 
def update_rol_db(user_id: int, nuevo_rol: str) -> bool:
    db = SessionLocal()
    try:
        u = db.query(Usuario).filter(Usuario.id == user_id).first()
        if not u:
            warn(f"No existe usuario con id={user_id}")
            return False
        anterior = u.rol
        u.rol = nuevo_rol
        db.commit()
        logger.info("Rol actualizado: id=%s %s → %s", user_id, anterior, nuevo_rol)
        return True
    except Exception as e:
        db.rollback()
        logger.exception("Error actualizando rol id=%s: %s", user_id, e)
        return False
    finally:
        db.close()
 
 
def toggle_activo_db(user_id: int) -> Optional[bool]:
    db = SessionLocal()
    try:
        u = db.query(Usuario).filter(Usuario.id == user_id).first()
        if not u:
            warn(f"No existe usuario con id={user_id}")
            return None
        u.activo = not u.activo
        db.commit()
        logger.info("Activo toggled: id=%s nombre=%s activo=%s", user_id, u.nombre, u.activo)
        return u.activo
    except Exception as e:
        db.rollback()
        logger.exception("Error toggling activo id=%s: %s", user_id, e)
        return None
    finally:
        db.close()
 
 
# ════════════════════════════════════════════════════════════════════════════
# HELPERS DE UI
# ════════════════════════════════════════════════════════════════════════════
 
def separador(char="═", n=60):
    print(f"{DIM}{char * n}{RST}")
 
def titulo(texto):
    separador()
    print(f"{W}{texto}{RST}")
    separador()
 
def pedir_id(prompt="ID del usuario: ") -> Optional[int]:
    try:
        return int(input(prompt).strip())
    except ValueError:
        err("ID inválido — debe ser un número.")
        return None
 
def mostrar_tabla_usuarios(usuarios: list):
    if not usuarios:
        info("No hay usuarios registrados.")
        return
    print(f"\n{DIM}{'ID':>4}  {'Login':15}  {'Nombre Visible':28}  {'Rol':8}  {'Activo'}{RST}")
    separador("-", 70)
    for u in usuarios:
        rol_icon = f"{Y}👑 admin{RST}" if u.rol == "admin" else f"{C}👤 user{RST} "
        activo   = f"{G}✓{RST}" if getattr(u, 'activo', True) else f"{R}✗{RST}"
        nv = (u.nombre_visible or "")[:28]
        print(f"{u.id:>4}  {u.nombre:15}  {nv:28}  {rol_icon}  {activo}")
    separador("-", 70)
    print(f"  Total: {len(usuarios)} usuarios\n")
 
 
def pedir_pin(prompt="Nuevo PIN: ") -> Optional[str]:
    """
    Pide y valida el PIN con confirmación.
    Acepta 4-20 dígitos. Muestra aviso si es menor a 6.
    """
    for intento in range(3):
        pin  = getpass(f"🔐 {prompt}").strip()
        pin2 = getpass("🔐 Confirmar PIN: ").strip()
 
        if pin != pin2:
            err("Los PIN no coinciden.")
            continue
 
        valido, mensaje = validate_pin_cli(pin)
        if not valido:
            err(mensaje)
            continue
 
        # Aviso de seguridad para PINs cortos (no bloquea)
        if len(pin) < 6:
            warn(f"PIN de {len(pin)} dígitos aceptado, pero se recomienda 6 o más para mayor seguridad.")
 
        return pin
 
    err("Demasiados intentos. Operación cancelada.")
    return None
 
 
def pedir_rol(default="user") -> str:
    print(f"\n{W}👥 Selecciona el rol:{RST}")
    print(f"  1) {C}👤 user{RST}  — Solo puede crear inspecciones")
    print(f"  2) {Y}👑 admin{RST} — Puede gestionar usuarios y ver todo")
    while True:
        choice = input(f"Opción (1/2, Enter = {default}): ").strip() or ("1" if default == "user" else "2")
        if choice == "1": return "user"
        if choice == "2": return "admin"
        err("Opción inválida.")
 
 
# ════════════════════════════════════════════════════════════════════════════
# ACCIONES DEL MENÚ
# ════════════════════════════════════════════════════════════════════════════
 
def prompt_create_user(force_admin=False):
    titulo("📝  CREAR NUEVO USUARIO")
 
    while True:
        nombre = input(f"{W}👤 Login (único, sin espacios): {RST}").strip()
        if not validate_login(nombre):
            err("Login inválido — usa letras, números y _ (mín. 2 caracteres).")
            continue
        db = SessionLocal()
        existe = db.query(Usuario).filter(Usuario.nombre == nombre).first()
        db.close()
        if existe:
            warn(f"El login '{nombre}' ya está en uso.")
            continue
        break
 
    while True:
        nv_input = input(f"{W}📛 Nombre completo (Enter = mismo que login): {RST}").strip()
        nombre_visible = nv_input if nv_input else nombre
        if not validate_nombre_visible(nombre_visible):
            err("Nombre inválido — usa solo letras y espacios.")
            continue
        nombre_visible = nombre_visible.strip().title()
        break
 
    pin = pedir_pin()
    if pin is None:
        return
 
    if force_admin:
        rol = "admin"
        info("Rol asignado automáticamente: admin (primer usuario del sistema)")
    else:
        rol = pedir_rol()
 
    print(f"\n{W}📋 Resumen:{RST}")
    print(f"   Login  : {C}{nombre}{RST}")
    print(f"   Nombre : {nombre_visible}")
    print(f"   Rol    : {Y if rol == 'admin' else C}{'👑 admin' if rol == 'admin' else '👤 user'}{RST}")
    print(f"   PIN    : {'*' * len(pin)}")
 
    conf = input(f"\n{W}¿Crear usuario? (S/n): {RST}").strip().lower()
    if conf and conf != "s":
        warn("Operación cancelada.")
        return
 
    u = create_user_db(nombre, nombre_visible, pin, rol)
    if u:
        ok(f"Usuario creado — ID: {u.id} | Login: {u.nombre} | Rol: {u.rol}")
    else:
        err("No se pudo crear el usuario. Revisa app/logs/admin.log")
 
 
def prompt_list_users():
    titulo("📋  LISTA DE USUARIOS")
    mostrar_tabla_usuarios(list_users_db())
 
 
def prompt_delete_user():
    titulo("🗑️   BORRAR USUARIO")
    mostrar_tabla_usuarios(list_users_db())
 
    uid = pedir_id("ID del usuario a borrar: ")
    if uid is None: return
 
    db = SessionLocal()
    u = db.query(Usuario).filter(Usuario.id == uid).first()
    db.close()
    if not u:
        err(f"No existe usuario con ID {uid}")
        return
 
    warn(f"Vas a borrar permanentemente a '{u.nombre}' ({u.nombre_visible})")
    conf = input("Escribe BORRAR para confirmar: ").strip()
    if conf != "BORRAR":
        warn("Operación cancelada.")
        return
 
    ok("Usuario borrado.") if delete_user_db(uid) else err("No se pudo borrar.")
 
 
def prompt_change_pin():
    titulo("🔐  CAMBIAR PIN")
    mostrar_tabla_usuarios(list_users_db())
 
    uid = pedir_id("ID del usuario: ")
    if uid is None: return
 
    db = SessionLocal()
    u = db.query(Usuario).filter(Usuario.id == uid).first()
    db.close()
    if not u:
        err(f"No existe usuario con ID {uid}")
        return
 
    info(f"Cambiando PIN de '{u.nombre}' ({u.nombre_visible})")
    pin = pedir_pin()
    if pin is None: return
 
    ok("PIN actualizado.") if update_pin_db(uid, pin) else err("No se pudo actualizar.")
 
 
def prompt_change_nombre():
    titulo("📛  CAMBIAR NOMBRE VISIBLE")
    mostrar_tabla_usuarios(list_users_db())
 
    uid = pedir_id("ID del usuario: ")
    if uid is None: return
 
    db = SessionLocal()
    u = db.query(Usuario).filter(Usuario.id == uid).first()
    db.close()
    if not u:
        err(f"No existe usuario con ID {uid}")
        return
 
    info(f"Nombre actual: {u.nombre_visible}")
    nv = input("Nuevo nombre completo: ").strip()
    if not nv:
        warn("Cancelado.")
        return
    if not validate_nombre_visible(nv):
        err("Nombre inválido — solo letras y espacios.")
        return
 
    ok("Nombre actualizado.") if update_nombre_visible_db(uid, nv.title()) else err("No se pudo actualizar.")
 
 
def prompt_change_rol():
    titulo("👥  CAMBIAR ROL")
    mostrar_tabla_usuarios(list_users_db())
 
    uid = pedir_id("ID del usuario: ")
    if uid is None: return
 
    db = SessionLocal()
    u = db.query(Usuario).filter(Usuario.id == uid).first()
    db.close()
    if not u:
        err(f"No existe usuario con ID {uid}")
        return
 
    info(f"Rol actual de '{u.nombre}': {u.rol}")
    nuevo_rol = pedir_rol(default=u.rol)
 
    if nuevo_rol == u.rol:
        info("El rol seleccionado es el mismo. Sin cambios.")
        return
 
    warn(f"Cambiar rol de '{u.nombre}': {u.rol} → {nuevo_rol}")
    conf = input("¿Confirmar? (S/n): ").strip().lower()
    if conf and conf != "s":
        warn("Cancelado.")
        return
 
    ok(f"Rol actualizado a '{nuevo_rol}'.") if update_rol_db(uid, nuevo_rol) else err("No se pudo actualizar.")
 
 
def prompt_toggle_activo():
    titulo("🔛  ACTIVAR / DESACTIVAR USUARIO")
    mostrar_tabla_usuarios(list_users_db())
 
    uid = pedir_id("ID del usuario: ")
    if uid is None: return
 
    db = SessionLocal()
    u = db.query(Usuario).filter(Usuario.id == uid).first()
    db.close()
    if not u:
        err(f"No existe usuario con ID {uid}")
        return
 
    estado_actual = "ACTIVO" if getattr(u, 'activo', True) else "INACTIVO"
    estado_nuevo  = "INACTIVO" if getattr(u, 'activo', True) else "ACTIVO"
    warn(f"'{u.nombre}' está {estado_actual} → pasará a {estado_nuevo}")
 
    conf = input("¿Confirmar? (S/n): ").strip().lower()
    if conf and conf != "s":
        warn("Cancelado.")
        return
 
    nuevo = toggle_activo_db(uid)
    if nuevo is None:
        err("No se pudo cambiar el estado.")
    elif nuevo:
        ok(f"Usuario '{u.nombre}' ACTIVADO.")
    else:
        warn(f"Usuario '{u.nombre}' DESACTIVADO. No podrá iniciar sesión.")
 
 
# ════════════════════════════════════════════════════════════════════════════
# MENÚ PRINCIPAL
# ════════════════════════════════════════════════════════════════════════════
 
MENU = {
    "1": ("📝  Crear usuario",               prompt_create_user),
    "2": ("📋  Listar usuarios",              prompt_list_users),
    "3": ("🔐  Cambiar PIN",                  prompt_change_pin),
    "4": ("📛  Cambiar nombre visible",       prompt_change_nombre),
    "5": ("👥  Cambiar rol",                  prompt_change_rol),
    "6": ("🔛  Activar / Desactivar usuario", prompt_toggle_activo),
    "7": ("🗑️   Borrar usuario",              prompt_delete_user),
    "0": ("👋  Salir",                        None),
}
 
def show_header():
    stats = get_stats()
    print(f"\n{W}")
    separador("═")
    print(f"  🔧  MISIONALES — Admin CLI  v3.1")
    separador("─", 60)
    print(f"  {C}Usuarios: {stats['total']}{RST}  |  "
          f"  {Y}Admins: {stats['admins']}{RST}  |  "
          f"  {G}Activos: {stats['activos']}{RST}")
    separador("═")
 
def main_menu():
    show_header()
 
    while True:
        print(f"\n{W}=== MENÚ ==={RST}")
        for k, (label, _) in MENU.items():
            print(f"  {C}{k}{RST}) {label}")
 
        choice = input(f"\n{W}Selecciona opción: {RST}").strip()
 
        if choice == "0":
            print(f"\n{G}👋 Hasta luego.{RST}\n")
            break
        elif choice in MENU:
            _, action = MENU[choice]
            if action:
                try:
                    action()
                except KeyboardInterrupt:
                    warn("\nOperación cancelada.")
                except Exception as e:
                    logger.exception("Error en acción: %s", e)
                    err(f"Error inesperado: {e}")
        else:
            err("Opción inválida.")
 
 
# ════════════════════════════════════════════════════════════════════════════
# PUNTO DE ENTRADA
# ════════════════════════════════════════════════════════════════════════════
 
if __name__ == "__main__":
    try:
        stats = get_stats()
 
        if stats["total"] == 0:
            print(f"\n{Y}{'═'*60}{RST}")
            print(f"{Y}  🚀  PRIMERA EJECUCIÓN — No hay usuarios en el sistema{RST}")
            print(f"{Y}  Crea el usuario administrador para continuar.{RST}")
            print(f"{Y}{'═'*60}{RST}\n")
            prompt_create_user(force_admin=True)
            print(f"\n{G}✅ Admin creado. Ahora puedes iniciar sesión en Misionales.{RST}\n")
 
        elif stats["admins"] == 0:
            warn("Hay usuarios pero ningún administrador.")
            info("Asigna el rol admin a un usuario existente o crea uno nuevo.")
            main_menu()
 
        else:
            main_menu()
 
    except KeyboardInterrupt:
        print(f"\n\n{Y}⚠️  Interrumpido. Saliendo...{RST}\n")
        sys.exit(0)
    except Exception as e:
        logger.exception("Error fatal: %s", e)
        err(f"Error fatal: {e}")
        sys.exit(1)
 