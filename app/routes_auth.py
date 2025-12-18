from fastapi import APIRouter, HTTPException, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import secrets
import bcrypt

from app.database import SessionLocal
from app import models

router = APIRouter(tags=["Auth"])


# ============================
# REGISTRO (solo si lo necesitas)
# ============================
@router.post("/register")
def registrar_usuario(
    nombre: str = Form(...),
    pin: str = Form(...)
):
    db: Session = SessionLocal()
    try:
        nombre_clean = " ".join(nombre.strip().split()).capitalize()

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

        pin_hash = bcrypt.hashpw(
            pin.encode(),
            bcrypt.gensalt()
        ).decode()

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

    finally:
        db.close()


# ============================
# LOGIN SEGURO
# ============================
@router.post("/login")
def login(
    nombre: str = Form(...),
    pin: str = Form(...)
):
    db: Session = SessionLocal()
    try:
        nombre_clean = " ".join(nombre.strip().split()).capitalize()

        usuario = (
            db.query(models.Usuario)
            .filter(models.Usuario.nombre == nombre_clean)
            .first()
        )

        if not usuario:
            raise HTTPException(
                status_code=400,
                detail="Usuario no encontrado"
            )

        if not bcrypt.checkpw(
            pin.encode(),
            usuario.pin_hash.encode()
        ):
            raise HTTPException(
                status_code=401,
                detail="PIN incorrecto"
            )

        # 🔐 Generar token seguro
        token = secrets.token_hex(32)

        usuario.token = token
        usuario.token_expira = datetime.utcnow() + timedelta(hours=12)

        db.commit()

        return {
            "mensaje": "Login exitoso",
            "token": token,
            "usuario_id": usuario.id,
            "nombre": usuario.nombre
        }

    finally:
        db.close()
