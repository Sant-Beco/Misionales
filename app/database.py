# app/database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DATA_DIR}/misionales.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    from fastapi import Depends
    from sqlalchemy.orm import Session
    def _get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    return Depends(_get_db)
