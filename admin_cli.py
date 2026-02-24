#!/usr/bin/env python3
# app/admin_cli.py
"""
CLI de administración de usuarios para la app Misionales.

Versión: 2.0 (con soporte para ROL)

Ubicación: app/admin_cli.py
Uso (desde el repo raíz):
  python -m app.admin_cli
o
  python app/admin_cli.py

Acciones:
 - crear usuario (con rol)
 - listar usuarios (con rol)
 - borrar usuario
 - cambiar PIN
 - editar nombre_visible
 - cambiar rol

Registra en: app/logs/admin.log
"""

import os
import sys
import logging
import re
from getpass import getpass
from typing import Optional

from passlib.context import CryptContext

# Importar la DB y modelos
from app.database import SessionLocal
from app.models import Usuario


# =======================
# Configuración seguridad
# =======================

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# =======================
# Logging
# =======================

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "admin.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ],
)

logger = logging.getLogger("admin_cli")


# =======================
# Helpers DB
# =======================

def create_user_db(
    nombre: str, 
    nombre_visible: Optional[str], 
    pin: str,
    rol: str = "user"
) -> Optional[Usuario]:
    """
    Crea un usuario en la base de datos.
    
    Args:
        nombre: Login del usuario (único)
        nombre_visible: Nombre completo para mostrar
        pin: PIN en texto plano (se hasheará)
        rol: 'user' o 'admin'
    
    Returns:
        Usuario creado o None si falla
    """
    db = SessionLocal()
    try:
        # Verificar si existe
        existing = db.query(Usuario).filter(Usuario.nombre == nombre).first()
        if existing:
            logger.warning(
                "❌ Usuario ya existe: nombre='%s' (id=%s, rol=%s)",
                nombre, existing.id, existing.rol
            )
            return None

        # Hash del PIN
        pin_hash = pwd_context.hash(pin)
        
        # Crear usuario
        nuevo = Usuario(
            nombre=nombre,
            nombre_visible=nombre_visible or nombre,
            pin_hash=pin_hash,
            rol=rol  # ← NUEVO: Soporte para rol
        )

        db.add(nuevo)
        db.commit()
        db.refresh(nuevo)

        logger.info(
            "✅ Usuario creado: id=%s, nombre=%s, nombre_visible=%s, rol=%s",
            nuevo.id, nuevo.nombre, nuevo.nombre_visible, nuevo.rol
        )
        return nuevo

    except Exception as e:
        db.rollback()
        logger.exception("❌ Error creando usuario: %s", e)
        return None
    finally:
        db.close()


def list_users_db():
    """Lista todos los usuarios ordenados por ID"""
    db = SessionLocal()
    try:
        return db.query(Usuario).order_by(Usuario.id).all()
    except Exception as e:
        logger.exception("❌ Error listando usuarios: %s", e)
        return []
    finally:
        db.close()


def delete_user_db(user_id: int) -> bool:
    """Elimina un usuario por ID"""
    db = SessionLocal()
    try:
        u = db.query(Usuario).filter(Usuario.id == user_id).first()
        if not u:
            logger.warning("⚠️ Intento de borrar usuario inexistente id=%s", user_id)
            return False

        nombre_borrado = u.nombre
        db.delete(u)
        db.commit()
        logger.info("✅ Usuario borrado: id=%s, nombre=%s", user_id, nombre_borrado)
        return True

    except Exception as e:
        db.rollback()
        logger.exception("❌ Error borrando usuario id=%s: %s", user_id, e)
        return False
    finally:
        db.close()


def update_pin_db(user_id: int, new_pin: str) -> bool:
    """Actualiza el PIN de un usuario"""
    db = SessionLocal()
    try:
        u = db.query(Usuario).filter(Usuario.id == user_id).first()
        if not u:
            logger.warning("⚠️ Usuario no existe para cambio PIN id=%s", user_id)
            return False

        u.pin_hash = pwd_context.hash(new_pin)
        db.commit()
        logger.info("✅ PIN actualizado para usuario id=%s (%s)", user_id, u.nombre)
        return True

    except Exception as e:
        db.rollback()
        logger.exception("❌ Error actualizando PIN id=%s: %s", user_id, e)
        return False
    finally:
        db.close()


def update_nombre_visible_db(user_id: int, nombre_visible: str) -> bool:
    """Actualiza el nombre visible de un usuario"""
    db = SessionLocal()
    try:
        u = db.query(Usuario).filter(Usuario.id == user_id).first()
        if not u:
            logger.warning("⚠️ Usuario no existe para nombre_visible id=%s", user_id)
            return False

        u.nombre_visible = nombre_visible
        db.commit()
        logger.info(
            "✅ nombre_visible actualizado id=%s (%s) → %s",
            user_id, u.nombre, nombre_visible
        )
        return True

    except Exception as e:
        db.rollback()
        logger.exception("❌ Error actualizando nombre_visible id=%s: %s", user_id, e)
        return False
    finally:
        db.close()


def update_rol_db(user_id: int, nuevo_rol: str) -> bool:
    """
    Actualiza el rol de un usuario.
    
    Args:
        user_id: ID del usuario
        nuevo_rol: 'user' o 'admin'
    
    Returns:
        True si se actualizó, False si falla
    """
    db = SessionLocal()
    try:
        u = db.query(Usuario).filter(Usuario.id == user_id).first()
        if not u:
            logger.warning("⚠️ Usuario no existe para cambio de rol id=%s", user_id)
            return False

        rol_anterior = u.rol
        u.rol = nuevo_rol
        db.commit()
        logger.info(
            "✅ Rol actualizado id=%s (%s): %s → %s",
            user_id, u.nombre, rol_anterior, nuevo_rol
        )
        return True

    except Exception as e:
        db.rollback()
        logger.exception("❌ Error actualizando rol id=%s: %s", user_id, e)
        return False
    finally:
        db.close()


# =======================
# Validadores
# =======================

def validate_pin(pin: str) -> bool:
    """Valida que el PIN sea de 4-6 dígitos"""
    return pin.isdigit() and 4 <= len(pin) <= 6


def validate_nombre_visible(nombre: str) -> bool:
    """
    Permite solo letras (incluye acentos) y espacios.
    """
    if not nombre:
        return False

    nombre = nombre.strip()
    patron = r"^[A-Za-zÁÉÍÓÚáéíóúÑñ ]+$"
    return bool(re.match(patron, nombre))


def validate_rol(rol: str) -> bool:
    """Valida que el rol sea 'user' o 'admin'"""
    return rol.lower() in ["user", "admin"]


# =======================
# Interfaz interactiva
# =======================

def prompt_create_user():
    """Flujo interactivo para crear usuario"""
    print("\n" + "="*50)
    print("📝 CREAR NUEVO USUARIO")
    print("="*50)
    
    # Nombre (login)
    nombre = input("👤 Usuario (login, único): ").strip()
    if not nombre:
        print("❌ Nombre obligatorio.")
        return

    # Verificar si ya existe
    db = SessionLocal()
    try:
        existing = db.query(Usuario).filter(Usuario.nombre == nombre).first()
        if existing:
            print(f"\n⚠️  El usuario '{nombre}' ya existe:")
            print(f"   ID: {existing.id}")
            print(f"   Nombre visible: {existing.nombre_visible}")
            print(f"   Rol: {existing.rol}")
            print("\n💡 Usa la opción de editar si quieres modificarlo.")
            return
    finally:
        db.close()

    # Nombre visible
    while True:
        nombre_visible = input(
            "📛 Nombre completo (solo letras, Enter = mismo que login): "
        ).strip() or nombre

        if not validate_nombre_visible(nombre_visible):
            print("❌ Nombre inválido. Usa solo letras y espacios.")
            logger.warning(
                "Intento nombre_visible inválido: '%s'",
                nombre_visible
            )
            continue

        nombre_visible = nombre_visible.title()
        break

    # PIN
    while True:
        pin = getpass("🔐 PIN (4-6 dígitos): ").strip()
        pin2 = getpass("🔐 Confirmar PIN: ").strip()

        if pin != pin2:
            print("❌ Los PIN no coinciden.")
            continue

        if not validate_pin(pin):
            print("❌ PIN inválido. Debe ser solo dígitos (4-6).")
            continue

        break

    # Rol
    print("\n👥 Selecciona el rol del usuario:")
    print("  1) 👤 user - Solo puede crear inspecciones")
    print("  2) 👑 admin - Puede gestionar usuarios")
    
    while True:
        rol_choice = input("Opción (1/2, Enter = user): ").strip() or "1"
        
        if rol_choice == "1":
            rol = "user"
            break
        elif rol_choice == "2":
            rol = "admin"
            break
        else:
            print("❌ Opción inválida. Usa 1 o 2.")

    # Crear usuario
    print(f"\n📋 Resumen:")
    print(f"   Usuario: {nombre}")
    print(f"   Nombre: {nombre_visible}")
    print(f"   Rol: {rol}")
    
    confirmar = input("\n¿Crear usuario? (S/n): ").strip().lower()
    if confirmar and confirmar != 's':
        print("❌ Operación cancelada.")
        return

    created = create_user_db(nombre, nombre_visible, pin, rol)
    if created:
        print(f"\n✅ Usuario creado exitosamente:")
        print(f"   ID: {created.id}")
        print(f"   Usuario: {created.nombre}")
        print(f"   Nombre: {created.nombre_visible}")
        print(f"   Rol: {created.rol}")
    else:
        print("\n❌ No se pudo crear el usuario (ver logs para detalles).")


def prompt_list_users():
    """Lista todos los usuarios"""
    print("\n" + "="*70)
    print("📋 LISTA DE USUARIOS")
    print("="*70)
    
    users = list_users_db()

    if not users:
        print("(No hay usuarios registrados)")
        return

    # Header
    print(f"{'ID':>4}  {'Login':15}  {'Nombre Visible':30}  {'Rol':8}")
    print("-" * 70)
    
    # Usuarios
    for u in users:
        rol_display = f"👑 {u.rol}" if u.rol == "admin" else f"👤 {u.rol}"
        print(
            f"{u.id:>4}  "
            f"{u.nombre:15}  "
            f"{(u.nombre_visible or '')[:30]:30}  "
            f"{rol_display:8}"
        )
    
    print("-" * 70)
    print(f"Total: {len(users)} usuarios")


def prompt_delete_user():
    """Elimina un usuario"""
    print("\n" + "="*50)
    print("🗑️  BORRAR USUARIO")
    print("="*50)
    
    # Mostrar usuarios
    prompt_list_users()
    
    try:
        uid = int(input("\nID del usuario a borrar: ").strip())
    except ValueError:
        print("❌ ID inválido.")
        return

    # Verificar que existe
    db = SessionLocal()
    try:
        u = db.query(Usuario).filter(Usuario.id == uid).first()
        if not u:
            print(f"❌ No existe usuario con ID {uid}")
            return
        
        print(f"\n⚠️  Vas a borrar:")
        print(f"   ID: {u.id}")
        print(f"   Usuario: {u.nombre}")
        print(f"   Nombre: {u.nombre_visible}")
        print(f"   Rol: {u.rol}")
    finally:
        db.close()

    confirm = input("\n¿Confirmas? Escribe 'BORRAR' para confirmar: ").strip()
    if confirm != "BORRAR":
        print("❌ Operación cancelada.")
        return

    ok = delete_user_db(uid)
    if ok:
        print("\n✅ Usuario borrado exitosamente.")
    else:
        print("\n❌ No se pudo borrar (ver logs).")


def prompt_change_pin():
    """Cambia el PIN de un usuario"""
    print("\n" + "="*50)
    print("🔐 CAMBIAR PIN")
    print("="*50)
    
    # Mostrar usuarios
    prompt_list_users()
    
    try:
        uid = int(input("\nID del usuario: ").strip())
    except ValueError:
        print("❌ ID inválido.")
        return

    # Verificar que existe
    db = SessionLocal()
    try:
        u = db.query(Usuario).filter(Usuario.id == uid).first()
        if not u:
            print(f"❌ No existe usuario con ID {uid}")
            return
        print(f"Usuario: {u.nombre} ({u.nombre_visible})")
    finally:
        db.close()

    # Nuevo PIN
    while True:
        pin = getpass("Nuevo PIN (4-6 dígitos): ").strip()
        pin2 = getpass("Confirmar PIN: ").strip()

        if pin != pin2:
            print("❌ Los PIN no coinciden.")
            continue

        if not validate_pin(pin):
            print("❌ PIN inválido.")
            continue

        break

    ok = update_pin_db(uid, pin)
    if ok:
        print("✅ PIN actualizado exitosamente.")
    else:
        print("❌ No se pudo actualizar (ver logs).")


def prompt_change_nombre_visible():
    """Cambia el nombre visible de un usuario"""
    print("\n" + "="*50)
    print("📛 CAMBIAR NOMBRE VISIBLE")
    print("="*50)
    
    # Mostrar usuarios
    prompt_list_users()
    
    try:
        uid = int(input("\nID del usuario: ").strip())
    except ValueError:
        print("❌ ID inválido.")
        return

    # Verificar que existe
    db = SessionLocal()
    try:
        u = db.query(Usuario).filter(Usuario.id == uid).first()
        if not u:
            print(f"❌ No existe usuario con ID {uid}")
            return
        print(f"Nombre actual: {u.nombre_visible}")
    finally:
        db.close()

    # Nuevo nombre
    nv = input("Nuevo nombre completo (solo letras y espacios): ").strip()
    if not nv:
        print("❌ Nombre vacío. Cancelado.")
        return

    if not validate_nombre_visible(nv):
        print("❌ Nombre inválido. Usa solo letras y espacios.")
        return

    nv = nv.title()
    ok = update_nombre_visible_db(uid, nv)
    if ok:
        print(f"✅ Nombre actualizado: {nv}")
    else:
        print("❌ No se pudo actualizar (ver logs).")


def prompt_change_rol():
    """
    Cambia el rol de un usuario (user ↔ admin)
    """
    print("\n" + "="*50)
    print("👥 CAMBIAR ROL DE USUARIO")
    print("="*50)
    
    # Mostrar usuarios
    prompt_list_users()
    
    try:
        uid = int(input("\nID del usuario: ").strip())
    except ValueError:
        print("❌ ID inválido.")
        return

    # Verificar que existe
    db = SessionLocal()
    try:
        u = db.query(Usuario).filter(Usuario.id == uid).first()
        if not u:
            print(f"❌ No existe usuario con ID {uid}")
            return
        
        print(f"\nUsuario: {u.nombre} ({u.nombre_visible})")
        print(f"Rol actual: {u.rol}")
    finally:
        db.close()

    # Nuevo rol
    print("\n👥 Selecciona el nuevo rol:")
    print("  1) 👤 user")
    print("  2) 👑 admin")
    
    while True:
        choice = input("Opción (1/2): ").strip()
        
        if choice == "1":
            nuevo_rol = "user"
            break
        elif choice == "2":
            nuevo_rol = "admin"
            break
        else:
            print("❌ Opción inválida.")

    # Confirmar
    print(f"\n⚠️  Cambiar rol de '{u.nombre}':")
    print(f"   De: {u.rol}")
    print(f"   A:  {nuevo_rol}")
    
    confirmar = input("\n¿Confirmar? (S/n): ").strip().lower()
    if confirmar and confirmar != 's':
        print("❌ Operación cancelada.")
        return

    ok = update_rol_db(uid, nuevo_rol)
    if ok:
        print(f"\n✅ Rol actualizado: {nuevo_rol}")
    else:
        print("\n❌ No se pudo actualizar (ver logs).")


# =======================
# Menú principal
# =======================

def main_menu():
    """Menú principal del CLI"""
    MENU = {
        "1": ("Crear usuario", prompt_create_user),
        "2": ("Listar usuarios", prompt_list_users),
        "3": ("Borrar usuario", prompt_delete_user),
        "4": ("Cambiar PIN", prompt_change_pin),
        "5": ("Cambiar nombre_visible", prompt_change_nombre_visible),
        "6": ("Cambiar rol", prompt_change_rol),  # ← NUEVO
        "0": ("Salir", None),
    }

    print("\n" + "="*50)
    print("🔧 ADMIN CLI - MISONALES v2.0")
    print("="*50)

    while True:
        print("\n=== MENÚ PRINCIPAL ===")
        for k, (label, _) in MENU.items():
            print(f" {k}) {label}")

        choice = input("\nSelecciona opción: ").strip()

        if choice == "0":
            print("\n👋 Saliendo...")
            break

        if choice in MENU:
            _, action = MENU[choice]
            if action:
                try:
                    action()
                except Exception as e:
                    logger.exception("❌ Error ejecutando acción: %s", e)
                    print(f"\n❌ Error: {e}")
        else:
            print("❌ Opción inválida.")


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrumpido por usuario. Saliendo...")
        sys.exit(0)
    except Exception as e:
        logger.exception("❌ Error fatal: %s", e)
        print(f"\n❌ Error fatal: {e}")
        sys.exit(1)
