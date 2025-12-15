#!/usr/bin/env python3
# app/admin_cli.py
"""
CLI de administración de usuarios para la app Misionales.

Ubicación: app/admin_cli.py
Uso (desde el repo raíz):
  python -m app.admin_cli
o
  python app/admin_cli.py

Acciones:
 - crear usuario
 - listar usuarios
 - borrar usuario
 - cambiar PIN
 - editar nombre_visible

Registra en: app/logs/admin.log
"""

import os
import sys
import logging
from getpass import getpass
from typing import Optional

from passlib.context import CryptContext

# Importar la DB y modelos (script debe estar en paquete app/)
from app.database import SessionLocal
from app.models import Usuario

# Configuración hashing (igual que tu app)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Log file
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


# -----------------------
# Helpers DB
# -----------------------
def create_user_db(nombre: str, nombre_visible: Optional[str], pin: str) -> Optional[Usuario]:
    db = SessionLocal()
    try:
        # evitar duplicados en 'nombre' (campo unique en modelo)
        existing = db.query(Usuario).filter(Usuario.nombre == nombre).first()
        if existing:
            logger.warning("No se creó: ya existe un usuario con nombre '%s' (id=%s).", nombre, existing.id)
            return None

        pin_hash = pwd_context.hash(pin)
        nuevo = Usuario(nombre=nombre, nombre_visible=nombre_visible or nombre, pin_hash=pin_hash)
        db.add(nuevo)
        db.commit()
        db.refresh(nuevo)
        logger.info("Usuario creado: id=%s, nombre=%s, nombre_visible=%s", nuevo.id, nuevo.nombre, nuevo.nombre_visible)
        return nuevo
    except Exception as e:
        db.rollback()
        logger.exception("Error creando usuario: %s", e)
        return None
    finally:
        db.close()


def list_users_db():
    db = SessionLocal()
    try:
        users = db.query(Usuario).order_by(Usuario.id).all()
        return users
    finally:
        db.close()


def find_user_by_name(name: str) -> Optional[Usuario]:
    db = SessionLocal()
    try:
        return db.query(Usuario).filter(Usuario.nombre == name).first()
    finally:
        db.close()


def delete_user_db(user_id: int) -> bool:
    db = SessionLocal()
    try:
        u = db.query(Usuario).filter(Usuario.id == user_id).first()
        if not u:
            logger.warning("No existe usuario id=%s", user_id)
            return False
        db.delete(u)
        db.commit()
        logger.info("Usuario borrado: id=%s, nombre=%s", user_id, u.nombre)
        return True
    except Exception as e:
        db.rollback()
        logger.exception("Error borrando usuario id=%s: %s", user_id, e)
        return False
    finally:
        db.close()


def update_pin_db(user_id: int, new_pin: str) -> bool:
    db = SessionLocal()
    try:
        u = db.query(Usuario).filter(Usuario.id == user_id).first()
        if not u:
            logger.warning("No existe usuario id=%s", user_id)
            return False
        u.pin_hash = pwd_context.hash(new_pin)
        db.add(u)
        db.commit()
        logger.info("PIN actualizado para usuario id=%s", user_id)
        return True
    except Exception as e:
        db.rollback()
        logger.exception("Error actualizando PIN para id=%s: %s", user_id, e)
        return False
    finally:
        db.close()


def update_nombre_visible_db(user_id: int, nombre_visible: str) -> bool:
    db = SessionLocal()
    try:
        u = db.query(Usuario).filter(Usuario.id == user_id).first()
        if not u:
            logger.warning("No existe usuario id=%s", user_id)
            return False
        u.nombre_visible = nombre_visible
        db.add(u)
        db.commit()
        logger.info("nombre_visible actualizado para usuario id=%s -> %s", user_id, nombre_visible)
        return True
    except Exception as e:
        db.rollback()
        logger.exception("Error actualizando nombre_visible para id=%s: %s", user_id, e)
        return False
    finally:
        db.close()


# -----------------------
# Validadores
# -----------------------
def validate_pin(pin: str) -> bool:
    return pin.isdigit() and 4 <= len(pin) <= 6


# -----------------------
# Interfaz interactiva
# -----------------------
def prompt_create_user():
    print("\n== Crear usuario ==")
    nombre = input("Usuario (login corto, único): ").strip()
    if not nombre:
        print("Nombre obligatorio.")
        return
    nombre_visible = input("Nombre completo para informes (enter = mismo que login): ").strip() or nombre

    while True:
        pin = getpass("PIN (4-6 dígitos): ").strip()
        pin2 = getpass("Confirmar PIN: ").strip()
        if pin != pin2:
            print("Los PIN no coinciden. Intentar de nuevo.")
            continue
        if not validate_pin(pin):
            print("PIN inválido. Debe ser sólo dígitos y 4-6 caracteres.")
            continue
        break

    created = create_user_db(nombre, nombre_visible, pin)
    if created:
        print(f"✔ Usuario creado: id={created.id}, nombre={created.nombre}")
    else:
        print("✖ No se pudo crear el usuario (revisar logs).")


def prompt_list_users():
    print("\n== Lista de usuarios ==")
    users = list_users_db()
    if not users:
        print("(No hay usuarios registrados)")
        return
    print(f"{'ID':>4}  {'login':20}  {'nombre_visible'}")
    print("-" * 60)
    for u in users:
        print(f"{u.id:>4}  {u.nombre:20}  {u.nombre_visible or ''}")


def prompt_delete_user():
    print("\n== Borrar usuario ==")
    try:
        uid = int(input("ID del usuario a borrar: ").strip())
    except Exception:
        print("ID inválido.")
        return
    confirm = input(f"Confirma borrar usuario id={uid}? (type 'SI' to confirm): ").strip()
    if confirm != "SI":
        print("Operación cancelada.")
        return
    ok = delete_user_db(uid)
    print("Borrado." if ok else "No borrado.")


def prompt_change_pin():
    print("\n== Cambiar PIN ==")
    try:
        uid = int(input("ID del usuario: ").strip())
    except Exception:
        print("ID inválido.")
        return
    while True:
        pin = getpass("Nuevo PIN (4-6 dígitos): ").strip()
        pin2 = getpass("Confirmar PIN: ").strip()
        if pin != pin2:
            print("Los PIN no coinciden. Intentar de nuevo.")
            continue
        if not validate_pin(pin):
            print("PIN inválido. Debe ser sólo dígitos y 4-6 caracteres.")
            continue
        break
    ok = update_pin_db(uid, pin)
    print("PIN actualizado." if ok else "No actualizado.")


def prompt_change_nombre_visible():
    print("\n== Cambiar nombre_visible ==")
    try:
        uid = int(input("ID del usuario: ").strip())
    except Exception:
        print("ID inválido.")
        return
    nv = input("Nuevo nombre completo (nombre_visible): ").strip()
    if not nv:
        print("nombre_visible vacío. Cancelado.")
        return
    ok = update_nombre_visible_db(uid, nv)
    print("Nombre actualizado." if ok else "No actualizado.")


def main_menu():
    MENU = {
        "1": ("Crear usuario", prompt_create_user),
        "2": ("Listar usuarios", prompt_list_users),
        "3": ("Borrar usuario", prompt_delete_user),
        "4": ("Cambiar PIN", prompt_change_pin),
        "5": ("Cambiar nombre_visible", prompt_change_nombre_visible),
        "0": ("Salir", None),
    }

    while True:
        print("\n=== ADMIN CLI — Usuarios ===")
        for k, (label, _) in MENU.items():
            print(f" {k} ) {label}")
        choice = input("Selecciona opción: ").strip()
        if choice == "0":
            print("Saliendo.")
            break
        if choice in MENU:
            _, action = MENU[choice]
            try:
                action()
            except Exception as e:
                logger.exception("Error ejecutando acción del menú: %s", e)
        else:
            print("Opción inválida.")


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\nInterrumpido. Saliendo.")
        sys.exit(0)
