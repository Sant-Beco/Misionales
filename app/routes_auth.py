# app/routes/routes_auth.py
from fastapi import APIRouter, HTTPException, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app import models
import bcrypt
import secrets
import time

router = APIRouter(prefix="/auth", tags=["Auth"])


def generar_token(usuario_id: int) -> str:
    """
    Genera token simple a partir de usuario_id + timestamp + random.
    No se persiste en BD en esta versión; es un token temporal retornado al cliente.
    """
    payload = f"{usuario_id}|{int(time.time())}|{secrets.token_hex(16)}"
    token = bcrypt.hashpw(payload.encode(), bcrypt.gensalt()).decode()
    return token


@router.post("/register")
def registrar_usuario(
    nombre: str = Form(...),
    pin: str = Form(...)
):
    """
    Endpoint simple para crear usuario (usar solo por admin en etapa inicial).
    - nombre: texto (se deja sin espacios duplicados)
    - pin: string alfanumérico (se hashea con bcrypt)
    """
    db: Session = SessionLocal()
    try:
        # validar existencia
        nombre_clean = " ".join(nombre.strip().split()).capitalize()
        existente = db.query(models.Usuario).filter(models.Usuario.nombre == nombre_clean).first()
        if existente:
            return JSONResponse({"mensaje": "Usuario ya existe"}, status_code=400)

        pin_hash = bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()

        usuario = models.Usuario(
            nombre=nombre_clean,
            pin_hash=pin_hash
        )
        db.add(usuario)
        db.commit()
        db.refresh(usuario)

        return {"mensaje": "Usuario creado exitosamente", "usuario_id": usuario.id, "nombre": usuario.nombre}
    finally:
        db.close()


@router.post("/login")
def login(
    nombre: str = Form(...),
    pin: str = Form(...)
):
    """
    Login con nombre + pin.
    Retorna token, usuario_id y nombre.
    """
    db: Session = SessionLocal()
    try:
        nombre_clean = " ".join(nombre.strip().split()).capitalize()
        usuario = db.query(models.Usuario).filter(models.Usuario.nombre == nombre_clean).first()
        if not usuario:
            raise HTTPException(status_code=400, detail="Usuario no encontrado")

        if not bcrypt.checkpw(pin.encode(), usuario.pin_hash.encode()):
            raise HTTPException(status_code=401, detail="PIN incorrecto")

        token = generar_token(usuario.id)
        return {"mensaje": "Login exitoso", "token": token, "usuario_id": usuario.id, "nombre": usuario.nombre}
    finally:
        db.close()
