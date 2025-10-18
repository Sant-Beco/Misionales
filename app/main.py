import os
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.database import SessionLocal
from app.models import Inspeccion

# SQLAlchemy
from app.database import Base, engine
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


# Vista principal (formulario)
@app.get("/", response_class=HTMLResponse)
async def form_get(request: Request):
    hoy = datetime.now().strftime("%d - %m - %Y")

    # Consultar cantidad actual de inspecciones
    db = SessionLocal()
    total_inspecciones = db.query(Inspeccion).count()
    db.close()

    return templates.TemplateResponse(
        "form.html",
        {"request": request, "fecha": hoy, "mostrar_reporte": total_inspecciones >= 15}
    )


# Incluir rutas del módulo de inspecciones
from app.routes_inspecciones import router as inspecciones_router
app.include_router(inspecciones_router, prefix="/inspecciones", tags=["Inspecciones"])
