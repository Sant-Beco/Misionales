import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.exceptions import HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app import models

# ==========================================================
#   BASE DE DATOS — crear tablas al iniciar
# ==========================================================
Base.metadata.create_all(bind=engine)

# ==========================================================
#   DIRECTORIOS — rutas absolutas desde este archivo
# ==========================================================
BASE_DIR      = Path(__file__).resolve().parent   # .../app/
DATA_DIR      = BASE_DIR / "data"
PDF_DIR       = DATA_DIR / "generated_pdfs"
STATIC_DIR    = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

PDF_DIR.mkdir(parents=True, exist_ok=True)

# ==========================================================
#   LIFESPAN (reemplaza @app.on_event deprecado)
# ==========================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────
    print("\n" + "=" * 60)
    print("🚀 MISIONALES — Sistema iniciado")
    print("=" * 60)
    print(f"📂 BASE_DIR:      {BASE_DIR}")
    print(f"📂 STATIC_DIR:    {STATIC_DIR}")
    print(f"📂 TEMPLATES_DIR: {TEMPLATES_DIR}")
    print(f"📂 PDF_DIR:       {PDF_DIR}")
    _https = os.getenv("HTTPS_ENABLED", "false").lower() == "true"
    _debug = os.getenv("DEBUG", "false").lower() == "true"
    print(f"🔒 HTTPS_ENABLED: {_https}")
    print(f"🔧 DEBUG:         {_debug}")
    print("=" * 60 + "\n")
    yield
    # ── Shutdown (si se necesita limpieza futura) ─────────


# ==========================================================
#   FASTAPI APP
# ==========================================================
_DEBUG = os.getenv("DEBUG", "false").lower() == "true"

app = FastAPI(
    title="Sistema Misionales — Inspección Vehicular SST",
    lifespan=lifespan,
    # Deshabilitar docs en producción (DEBUG=false por defecto)
    docs_url="/docs"         if _DEBUG else None,
    redoc_url="/redoc"       if _DEBUG else None,
    openapi_url="/openapi.json" if _DEBUG else None,
)

# ==========================================================
#   CORS
#   ✅ BLOQUEANTE #2: incluir URL real del VPS / dominio
#   Leer de .env con fallback a localhost para desarrollo
# ==========================================================
_CORS_ORIGINS_ENV = os.getenv("CORS_ORIGINS", "")
_cors_origins = [o.strip() for o in _CORS_ORIGINS_ENV.split(",") if o.strip()]

# Siempre incluir localhost para desarrollo local
_cors_origins_default = [
    "http://localhost",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# Fusionar: los del .env tienen prioridad, los default siempre presentes
_all_origins = list(dict.fromkeys(_cors_origins + _cors_origins_default))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_all_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Advertencias", "Content-Disposition"],
)

# ==========================================================
#   STATIC FILES & TEMPLATES
# ==========================================================
if not STATIC_DIR.exists():
    print(f"⚠️  WARNING: {STATIC_DIR} no existe")
if not TEMPLATES_DIR.exists():
    print(f"⚠️  WARNING: {TEMPLATES_DIR} no existe")

try:
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    print(f"✅ Static files montados desde: {STATIC_DIR}")
except Exception as e:
    print(f"❌ Error montando static files: {e}")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# ==========================================================
#   ROUTERS
# ==========================================================
from app.routes_auth import router as auth_router
from app.routes_inspecciones import router as inspecciones_router
from app.routes_admin import router as admin_router

app.include_router(auth_router,         prefix="/auth",          tags=["Auth"])
app.include_router(inspecciones_router, prefix="/inspecciones",  tags=["Inspecciones"])
app.include_router(admin_router,                                  tags=["Admin"])

# ==========================================================
#   HANDLER GLOBAL: 401 / 403 → redirect al login
#   Distingue requests de browser (quieren HTML) de
#   requests fetch/API (quieren JSON).
#   - Browser sin sesión → redirect /login?next=<url>
#   - fetch/API sin sesión → 401 JSON (comportamiento actual)
# ==========================================================
@app.exception_handler(HTTPException)
async def auth_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code in (401, 403):
        # Detectar si el cliente espera HTML:
        # 1. Método GET (navegación directa)
        # 2. Accept header contiene text/html
        # 3. No es una llamada fetch con Authorization header
        accept = request.headers.get("accept", "")
        is_browser = (
            request.method == "GET"
            and "text/html" in accept
            and not request.headers.get("authorization")
            and not request.headers.get("x-requested-with")
        )
        if is_browser:
            # Guardar la URL destino para redirigir después del login
            next_url = str(request.url.path)
            if request.url.query:
                next_url += "?" + request.url.query
            from urllib.parse import quote
            redirect_url = f"/login?next={quote(next_url)}&razon={exc.status_code}"
            resp = RedirectResponse(url=redirect_url, status_code=302)
            # Limpiar cookie expirada/inválida para que el login parta limpio
            resp.delete_cookie("access_token")
            return resp

    # Para todo lo demás (fetch, POST, otros status) → JSON normal
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


# ==========================================================
#   RUTA: LOGIN
# ==========================================================
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


# ==========================================================
#   RUTA PRINCIPAL — formulario
#   ✅ IMPORTANTE: usa get_db via Depends en lugar de SessionLocal()
# ==========================================================
@app.get("/", response_class=HTMLResponse)
async def form_page(request: Request, db: Session = Depends(get_db)):
    fecha_hoy = datetime.now().strftime("%d - %m - %Y")
    total_inspecciones = db.query(models.Inspeccion).count()

    return templates.TemplateResponse(
        "form.html",
        {
            "request": request,
            "fecha": fecha_hoy,
            "mostrar_reporte": total_inspecciones >= 15,
        },
    )