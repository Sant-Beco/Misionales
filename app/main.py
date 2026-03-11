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
#   DIRECTORIOS - ✅ CORREGIDO
# ==========================================================
# Este archivo está en: app/main.py
# Entonces __file__ = .../app/main.py
# Y __file__.parent = .../app/

BASE_DIR = Path(__file__).resolve().parent  # .../app/

# Directorios de datos
DATA_DIR = BASE_DIR / "data"
PDF_DIR = DATA_DIR / "generated_pdfs"
os.makedirs(PDF_DIR, exist_ok=True)

# ✅ DIRECTORIO ESTÁTICO (dentro de app/)
STATIC_DIR = BASE_DIR / "static"

# ✅ DIRECTORIO TEMPLATES (dentro de app/)
TEMPLATES_DIR = BASE_DIR / "templates"

# Verificar que existen
if not STATIC_DIR.exists():
    print(f"⚠️  WARNING: {STATIC_DIR} no existe")
if not TEMPLATES_DIR.exists():
    print(f"⚠️  WARNING: {TEMPLATES_DIR} no existe")

# ==========================================================
#   FASTAPI APP
# ==========================================================
import os as _os

_DEBUG = _os.getenv("DEBUG", "false").lower() == "true"

app = FastAPI(
    title="Sistema Misionales - Formulario Inspección Vehicular",
    # Deshabilitar docs en producción (DEBUG=false por defecto)
    docs_url="/docs" if _DEBUG else None,
    redoc_url="/redoc" if _DEBUG else None,
    openapi_url="/openapi.json" if _DEBUG else None,
)

# ==========================================================
#   CORS (SEGURIDAD BÁSICA)
# ==========================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================================
#   STATIC FILES & TEMPLATES - ✅ CORREGIDO
# ==========================================================
try:
    app.mount(
        "/static",
        StaticFiles(directory=str(STATIC_DIR)),
        name="static"
    )
    print(f"✅ Static files montados desde: {STATIC_DIR}")
except Exception as e:
    print(f"❌ Error montando static files: {e}")

try:
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    print(f"✅ Templates cargados desde: {TEMPLATES_DIR}")
except Exception as e:
    print(f"❌ Error cargando templates: {e}")

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

# 🔧 ADMINISTRACIÓN (NUEVO)
from app.routes_admin import router as admin_router
app.include_router(admin_router, tags=["Admin"])

# ==========================================================
#   DEBUG: Mostrar rutas al iniciar
# ==========================================================
@app.on_event("startup")
async def startup_event():
    print("\n" + "="*60)
    print("🚀 MISONALES - Sistema iniciado")
    print("="*60)
    print(f"📂 BASE_DIR: {BASE_DIR}")
    print(f"📂 STATIC_DIR: {STATIC_DIR}")
    print(f"📂 TEMPLATES_DIR: {TEMPLATES_DIR}")
    print(f"📂 PDF_DIR: {PDF_DIR}")
    print("="*60)
    print("🌐 Rutas disponibles:")
    print("   http://127.0.0.1:8000/login")
    print("   http://127.0.0.1:8000/")
    print("   http://127.0.0.1:8000/docs")
    print("="*60 + "\n")