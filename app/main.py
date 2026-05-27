import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
 
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.exceptions import HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
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
#   CONFIGURACIÓN DE ENTORNO
# ==========================================================
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
HTTPS_ENABLED = os.getenv("HTTPS_ENABLED", "false").lower() == "true"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
 
# ✅ CORS: leer desde .env, con defaults seguros
CORS_ORIGINS_ENV = os.getenv("CORS_ORIGINS", "")
cors_origins = [o.strip() for o in CORS_ORIGINS_ENV.split(",") if o.strip()]
 
# Defaults seguros (localhost solo para desarrollo)
cors_origins_default = [
    "http://localhost",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
 
# En producción, CORS_ORIGINS debe estar en .env
# Ejemplo: CORS_ORIGINS=https://misionales.ejemplo.com,https://api.ejemplo.com
ALL_CORS_ORIGINS = list(dict.fromkeys(cors_origins + cors_origins_default))
 
# ==========================================================
#   LIFESPAN (reemplaza @app.on_event deprecado)
# ==========================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────
    print("\n" + "=" * 70)
    print("🚀 MISIONALES — Sistema iniciado")
    print("=" * 70)
    print(f"📂 BASE_DIR:        {BASE_DIR}")
    print(f"📂 STATIC_DIR:      {STATIC_DIR}")
    print(f"📂 TEMPLATES_DIR:   {TEMPLATES_DIR}")
    print(f"📂 PDF_DIR:         {PDF_DIR}")
    print(f"🔒 HTTPS_ENABLED:   {HTTPS_ENABLED}")
    print(f"🔧 DEBUG:           {DEBUG}")
    print(f"🌐 ALLOWED_HOSTS:   {ALLOWED_HOSTS}")
    print(f"🔗 CORS_ORIGINS:    {ALL_CORS_ORIGINS}")
    print("=" * 70 + "\n")
    
    # Warnings
    if DEBUG:
        print("⚠️  WARNING: DEBUG = True (no para producción)\n")
    if not HTTPS_ENABLED and not DEBUG:
        print("⚠️  WARNING: HTTPS_ENABLED = False en modo no-debug\n")
    
    yield
    # ── Shutdown ───────────────────────────────────────
    print("\n🛑 Sistema detenido\n")
 
 
# ==========================================================
#   FASTAPI APP
# ==========================================================
app = FastAPI(
    title="Sistema Misionales — Inspección Vehicular SST",
    version="1.0.0",
    lifespan=lifespan,
    # ✅ Deshabilitar docs en producción
    docs_url="/docs"         if DEBUG else None,
    redoc_url="/redoc"       if DEBUG else None,
    openapi_url="/openapi.json" if DEBUG else None,
)
 
# ==========================================================
#   MIDDLEWARE: SEGURIDAD
# ==========================================================
 
# ✅ 1. TrustedHost — prevenir Host Header Injection
#   Solo acepta requests con Host válido
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=ALLOWED_HOSTS,
    www_redirect=True if HTTPS_ENABLED else False,
)
 
# ✅ 2. CORS — Control de origen
#   allow_credentials=True permite enviar cookies con requests
#   expose_headers permite que el cliente lea X-Advertencias
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALL_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Advertencias", "Content-Disposition", "Content-Type"],
    max_age=86400,  # 24 horas
)
 
# ✅ 3. Headers de Seguridad (middleware personalizado)
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """
    Agrega headers de seguridad a TODAS las respuestas.
    """
    response = await call_next(request)
    
    # ✅ Prevenir clickjacking (no permite que el sitio se abra en iframe)
    response.headers["X-Frame-Options"] = "DENY"
    
    # ✅ Prevenir content-type sniffing (no permite que el navegador interprete MIME)
    response.headers["X-Content-Type-Options"] = "nosniff"
    
    # ✅ Habilitar XSS protection en navegadores antiguos
    response.headers["X-XSS-Protection"] = "1; mode=block"
    
    # ✅ Política de referrer (no envía referrer a otros sitios)
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # ✅ CSP (Content Security Policy) — solo en HTTPS (opcional en desarrollo)
    if HTTPS_ENABLED or DEBUG:
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self' "
        )
        response.headers["Content-Security-Policy"] = csp
    
    return response
 
 
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
#   ✅ Distingue requests de browser (HTML) de API (JSON)
#   - Browser GET sin auth → redirect /login
#   - Fetch/API sin auth → 401 JSON
# ==========================================================
@app.exception_handler(HTTPException)
async def auth_exception_handler(request: Request, exc: HTTPException):
    """
    Manejo personalizado de excepciones HTTP.
    
    - 401/403 en navegador: redirige a /login
    - 401/403 en API: devuelve JSON 401
    - Otros errores: devuelve JSON con estado apropiado
    """
    if exc.status_code in (401, 403):
        # Detectar si es una solicitud de navegador o API
        accept_header = request.headers.get("accept", "")
        is_browser_request = (
            request.method == "GET"
            and "text/html" in accept_header
            and not request.headers.get("authorization")
            and not request.headers.get("x-requested-with")
        )
        
        if is_browser_request:
            # ✅ Solicitud de navegador → redirigir a login
            next_url = str(request.url.path)
            if request.url.query:
                next_url += "?" + request.url.query
            
            from urllib.parse import quote
            redirect_url = f"/login?next={quote(next_url)}&status={exc.status_code}"
            
            response = RedirectResponse(url=redirect_url, status_code=302)
            response.delete_cookie("access_token")  # Limpiar cookie expirada
            return response
        else:
            # ✅ Solicitud de API → devolver JSON 401
            return JSONResponse(
                status_code=exc.status_code,
                content={"error": exc.detail or "Unauthorized"},
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    # Para otros errores HTTP → JSON
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail or "Error interno del servidor"},
    )
 
 
# ==========================================================
#   HANDLER GLOBAL: Excepciones no manejadas
#   ✅ Loguea el error y devuelve JSON seguro
# ==========================================================
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Atrapa excepciones no manejadas.
    
    - En desarrollo (DEBUG=true): incluye detalles del error
    - En producción: mensaje genérico (no expone internals)
    """
    import traceback
    
    error_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"\n❌ ERROR [{error_id}]: {str(exc)}")
    traceback.print_exc()
    
    if DEBUG:
        # Desarrollo: mostrar traceback completo
        return JSONResponse(
            status_code=500,
            content={
                "error": "Error interno del servidor",
                "detail": str(exc),
                "error_id": error_id,
                "traceback": traceback.format_exc(),
            },
        )
    else:
        # Producción: mensaje genérico (seguridad)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Error interno del servidor",
                "error_id": error_id,
            },
        )
 
 
# ==========================================================
#   RUTA: LOGIN
# ==========================================================
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: str = None, status: int = None):
    """
    Página de login.
    
    Parámetros:
    - next: URL a la que redirigir después del login
    - status: código de error (401, 403)
    """
    context = {
        "request": request,
        "next": next or "/",
        "error": None,
    }
    
    if status == 401:
        context["error"] = "Sesión expirada. Inicia sesión nuevamente."
    elif status == 403:
        context["error"] = "Acceso denegado. Verifica tus permisos."
    
    return templates.TemplateResponse("login.html", context)
 
 
# ==========================================================
#   RUTA PRINCIPAL — Formulario de inspección
#   ✅ Usa get_db via Depends (no SessionLocal directo)
# ==========================================================
@app.get("/", response_class=HTMLResponse)
async def form_page(request: Request, db: Session = Depends(get_db)):
    """
    Página principal: formulario de inspección preoperacional.
    
    Estadísticas:
    - Cuenta total de inspecciones realizadas
    - Determina si mostrar botón de generar reporte consolidado
    """
    fecha_hoy = datetime.now().strftime("%d - %m - %Y")
    total_inspecciones = db.query(models.Inspeccion).count()
 
    return templates.TemplateResponse(
        "form.html",
        {
            "request": request,
            "fecha": fecha_hoy,
            "total_inspecciones": total_inspecciones,
            "mostrar_reporte": total_inspecciones >= 15,
        },
    )
 
 
# ==========================================================
#   HEALTHCHECK (para monitoreo/load balancers)
# ==========================================================
@app.get("/health")
async def healthcheck():
    """
    Endpoint de salud para monitoreo.
    Load balancers y servicios de uptime usan esto.
    """
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "service": "misionales-inspecciones",
    }
 
 
# ==========================================================
#   MANEJO DE 404
# ==========================================================
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    """Ruta no encontrada."""
    return JSONResponse(
        status_code=404,
        content={"error": "Ruta no encontrada"},
    )