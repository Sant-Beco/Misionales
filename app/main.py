import os
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# SQLAlchemy
from app.database import Base, engine, SessionLocal
from app import models

# Crear tablas si no existen
Base.metadata.create_all(bind=engine)

# Directorios
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "app" / "data"
PDF_DIR = DATA_DIR / "generated_pdfs"
os.makedirs(PDF_DIR, exist_ok=True)

# Inicializar app
app = FastAPI(title="Sistema Misionales - Formulario Inspección Vehicular")

# Archivos estáticos y plantillas
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


# ==========================================================
#   RUTA: LOGIN (NUEVA)
# ==========================================================
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


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
            "mostrar_reporte": total_inspecciones >= 15
        }
    )


# ==========================================================
#   IMPORTAR E INCLUIR ROUTERS
# ==========================================================

# 🔒 AUTENTICACIÓN (LOGIN + REGISTER)
from app.routes_auth import router as auth_router
app.include_router(auth_router, prefix="/auth", tags=["Auth"])

# 📄 INSPECCIONES (PDF + DB)
from app.routes_inspecciones import router as inspecciones_router
app.include_router(inspecciones_router, prefix="/inspecciones", tags=["Inspecciones"])



