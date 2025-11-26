from app.database import SessionLocal
from app.models import Usuario
from passlib.context import CryptContext

# Sistema de encriptación usado en tu app
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def crear_usuario(nombre: str, pin: str):
    db = SessionLocal()

    # Encriptar PIN
    pin_hash = pwd_context.hash(pin)

    # Crear usuario
    nuevo = Usuario(
        nombre=nombre,
        pin_hash=pin_hash
    )

    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    db.close()

    print(f"Usuario creado con éxito:")
    print(f"ID: {nuevo.id}")
    print(f"Nombre: {nuevo.nombre}")

if __name__ == "__main__":
    nombre = input("Ingrese nombre de usuario: ")
    pin = input("Ingrese PIN (4-6 dígitos): ")
    crear_usuario(nombre, pin)
