import os
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

# SQLAlchemy
from app.database import Base, engine, SessionLocal
from app import models

# ==========================================================
#   BASE DE DATOS
# ==========================================================
# Crear tablas si no existen (válido para este proyecto)
Base.metadata.create_all(bind=engine)

# ==========================================================
#   DIRECTORIOS
# ==========================================================
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "app" / "data"
PDF_DIR = DATA_DIR / "generated_pdfs"
os.makedirs(PDF_DIR, exist_ok=True)

# ==========================================================
#   FASTAPI APP
# ==========================================================
app = FastAPI(
    title="Sistema Misionales - Formulario Inspección Vehicular"
)

# ==========================================================
#   CORS (SEGURIDAD BÁSICA)
# ==========================================================
# Permite frontend local y evita bloqueos del navegador
# En producción se debe restringir al dominio real
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        # "https://misionales.com"  # Producción
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================================
#   STATIC FILES & TEMPLATES
# ==========================================================
app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "static"),
    name="static"
)

templates = Jinja2Templates(directory=BASE_DIR / "templates")

# ==========================================================
#   RUTA: LOGIN
# ==========================================================
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {"request": request}
    )

# ==========================================================
#   RUTA PRINCIPAL (FORMULARIO)
# ==========================================================
@app.get("/", response_class=HTMLResponse)
async def form_page(request: Request):
    fecha_hoy = datetime.now().strftime("%d - %m - %Y")

    db = SessionLocal()
    total_inspecciones = db.query(models.Inspeccion).count()
    db.close()

    return templates.TemplateResponse(
        "form.html",
        {
            "request": request,
            "fecha": fecha_hoy,
            "mostrar_reporte": total_inspecciones >= 15,
        },
    )

# ==========================================================
#   ROUTERS
# ==========================================================

# 🔒 AUTENTICACIÓN
from app.routes_auth import router as auth_router
app.include_router(auth_router, prefix="/auth", tags=["Auth"])

# 📄 INSPECCIONES
from app.routes_inspecciones import router as inspecciones_router
app.include_router(
    inspecciones_router,
    prefix="/inspecciones",
    tags=["Inspecciones"],
)
