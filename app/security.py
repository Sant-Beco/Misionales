# app/security.py
from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import SessionLocal
from app.models import Usuario

def get_current_user(
    authorization: str = Header(...)
) -> Usuario:
    """
    Espera header:
    Authorization: Bearer <token>
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token inválido")

    token = authorization.replace("Bearer ", "").strip()

    db: Session = SessionLocal()
    try:
        usuario = (
            db.query(Usuario)
            .filter(Usuario.token == token)
            .first()
        )

        if not usuario:
            raise HTTPException(status_code=401, detail="Sesión no válida")

        if not usuario.token_expira or usuario.token_expira < datetime.utcnow():
            raise HTTPException(status_code=401, detail="Sesión expirada")

        return usuario
    finally:
        db.close()
