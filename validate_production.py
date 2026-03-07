#!/usr/bin/env python3
"""
Script de validación pre-despliegue para MISIONALES
Versión ajustada a la estructura real del proyecto
"""

import os
import sys
from pathlib import Path

class C:
    GREEN  = '\033[92m'
    RED    = '\033[91m'
    YELLOW = '\033[93m'
    BLUE   = '\033[94m'
    CYAN   = '\033[96m'
    RESET  = '\033[0m'

def ok(msg):    print(f"{C.GREEN}  ✅ {msg}{C.RESET}")
def err(msg):   print(f"{C.RED}  ❌ {msg}{C.RESET}")
def warn(msg):  print(f"{C.YELLOW}  ⚠️  {msg}{C.RESET}")
def tip(msg):   print(f"{C.CYAN}     → {msg}{C.RESET}")
def header(n, msg):
    print(f"\n{C.BLUE}{'='*62}")
    print(f"  {n}. {msg}")
    print(f"{'='*62}{C.RESET}\n")

PACKAGES = {
    "fastapi":     "fastapi==0.110.0",
    "uvicorn":     "uvicorn[standard]==0.30.1",
    "sqlalchemy":  "sqlalchemy==2.0.29",
    "pymysql":     "pymysql==1.1.2",
    "passlib":     "passlib[bcrypt]==1.7.4",
    "weasyprint":  "weasyprint==62.3",
    "jinja2":      "jinja2==3.1.3",
    "dotenv":      "python-dotenv==1.0.1",
    "multipart":   "python-multipart==0.0.20",
}

def check_dependencies():
    header(1, "Dependencias Python")
    missing = []
    for module, pkg in PACKAGES.items():
        try:
            __import__(module)
            ok(pkg)
        except ImportError:
            err(f"{pkg}  <- NO instalado")
            missing.append(pkg.split("=")[0])
    if missing:
        print()
        warn("Ejecuta para instalar todo:")
        tip("pip install -r requirements.txt")
        return False
    return True

def check_env():
    header(2, "Variables de entorno (.env)")
    if not Path(".env").exists():
        err(".env no existe")
        tip("Copia .env.example y rellena los valores:")
        tip("copy .env.example .env")
        return False
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        err("python-dotenv no instalado - instala dependencias primero (paso 1)")
        return False
    all_ok = True
    bd_vars = {
        "DB_HOST":     "localhost o IP del servidor MySQL",
        "DB_USER":     "usuario MySQL",
        "DB_PASSWORD": "contrasena MySQL",
        "DB_NAME":     "nombre de la BD (ej: misionales_db)",
    }
    for var, desc in bd_vars.items():
        val = os.getenv(var)
        if val:
            display = "*" * len(val) if "PASSWORD" in var else val
            ok(f"{var} = {display}")
        else:
            err(f"{var} no definida  ({desc})")
            all_ok = False
    secret = os.getenv("SECRET_KEY", "")
    if len(secret) >= 32:
        ok(f"SECRET_KEY = {'*' * len(secret)}  ({len(secret)} chars OK)")
    elif secret:
        warn(f"SECRET_KEY muy corta ({len(secret)} chars, minimo 32)")
        tip('Genera una: python -c "import secrets; print(secrets.token_urlsafe(32))"')
        all_ok = False
    else:
        err("SECRET_KEY no definida")
        tip('Genera una: python -c "import secrets; print(secrets.token_urlsafe(32))"')
        all_ok = False
    return all_ok

DIRS = [
    "app", "app/data", "app/data/generated_pdfs", "app/data/firmas",
    "app/logs", "app/static", "app/static/css", "app/static/fonts",
    "app/static/img", "app/static/js", "app/templates", "app/templates/admin",
]

def check_directories():
    header(3, "Estructura de directorios")
    missing = []
    for d in DIRS:
        if Path(d).exists():
            ok(d)
        else:
            err(f"{d}  <- falta")
            missing.append(d)
    if missing:
        print()
        warn("Crea los directorios faltantes (PowerShell):")
        for m in missing:
            tip(f'New-Item -ItemType Directory -Force -Path "{m}"')
        return False
    return True

FILES = {
    "app/main.py":                            "Aplicacion principal FastAPI",
    "app/database.py":                        "Conexion SQLAlchemy",
    "app/models.py":                          "Modelos ORM",
    "app/security.py":                        "Auth por cookie + token",
    "app/routes_auth.py":                     "Login / logout",
    "app/routes_inspecciones.py":             "Inspecciones + PDF",
    "app/routes_admin.py":                    "Panel de administracion",
    "app/utils_pdf.py":                       "Generacion PDFs WeasyPrint",
    "app/templates/login.html":               "Pantalla de login",
    "app/templates/form.html":                "Formulario de inspeccion",
    "app/templates/lista_inspecciones.html":  "Historial del conductor",
    "app/templates/pdf_template.html":        "PDF individual",
    "app/templates/pdf_template_multiple.html": "PDF consolidado 15 dias",
    "app/templates/admin/dashboard.html":     "Dashboard admin",
    "app/templates/admin/usuarios.html":      "Gestion de usuarios",
    "app/templates/admin/logs.html":          "Logs de auditoria",
    "app/templates/admin/usuario_form.html":  "Formulario usuario",
    "app/static/css/incubant-theme.css":      "Sistema de diseno Incubant",
    "requirements.txt":                       "Dependencias del proyecto",
    ".env":                                   "Variables de entorno",
    ".gitignore":                             "Archivos excluidos de git",
    "admin_cli.py":                           "CLI para gestion de usuarios",
}

def check_files():
    header(4, "Archivos criticos")
    missing = []
    for path, desc in FILES.items():
        p = Path(path)
        if p.exists():
            size = p.stat().st_size
            ok(f"{path}  ({size:,} B)")
        else:
            err(f"{path}  <- falta  [{desc}]")
            missing.append(path)
    if missing:
        print()
        warn(f"{len(missing)} archivo(s) faltante(s)")
        return False
    return True

def check_static_assets():
    header(5, "Assets estaticos (logo + fuentes)")
    all_ok = True
    logo_candidates = [
        "app/static/img/logotipo_01.png",
        "app/static/img/Logotipo_01.png",
        "app/static/img/incubant.jpg",
        "app/static/img/incubant.png",
    ]
    found = [p for p in logo_candidates if Path(p).exists()]
    if found:
        ok(f"Logo: {found[0]}")
        if len(found) > 1:
            warn(f"Hay {len(found)} logos - asegurate que los templates apunten al correcto")
            for f in found:
                tip(f)
    else:
        err("Logo no encontrado en app/static/img/")
        tip("Necesitas: logotipo_01.png  o  incubant.jpg")
        all_ok = False
    fonts = [
        "app/static/fonts/1_Futura_Md_Bt_negrilla.ttf",
        "app/static/fonts/2_Futura_M_Bt_light.ttf",
        "app/static/fonts/3_Futura_book_bt_parrafos.ttf",
        "app/static/fonts/4_Futura_book_italic_bt_parrafoss.ttf",
    ]
    missing_fonts = [f for f in fonts if not Path(f).exists()]
    if not missing_fonts:
        ok("Fuentes Futura (4 x .ttf) OK")
    else:
        warn(f"{len(missing_fonts)} fuente(s) Futura faltante(s) - usara fallback sans-serif")
        for f in missing_fonts:
            tip(f"Falta: {f}")
    return all_ok

def check_security():
    header(6, "Configuracion de seguridad")
    all_ok = True
    gitignore = Path(".gitignore")
    if gitignore.exists():
        content = gitignore.read_text(encoding="utf-8")
        if ".env" in content:
            ok(".env esta en .gitignore")
        else:
            err(".env NO esta en .gitignore - agrega la linea '.env'")
            all_ok = False
    else:
        warn(".gitignore no existe")
    main_py = Path("app/main.py")
    if main_py.exists():
        txt = main_py.read_text(encoding="utf-8")
        # Verificar si allow_origins contiene wildcard (no allow_methods/headers)
        import re as _re
        origins_block = _re.search(r'allow_origins\s*=\s*\[([^\]]*?)\]', txt, _re.DOTALL)
        if origins_block and '"*"' in origins_block.group(1):
            err("CORS usa allow_origins=['*'] - cambia al dominio real en produccion")
            tip("allow_origins=['https://tu-dominio.com']")
            all_ok = False
        else:
            ok("CORS allow_origins OK (sin wildcard)")
        if "echo=True" in txt:
            warn("SQLAlchemy echo=True - desactivalo en produccion (echo=False)")
        else:
            ok("SQLAlchemy echo=False OK")
    routes_auth = Path("app/routes_auth.py")
    if routes_auth.exists():
        txt = routes_auth.read_text(encoding="utf-8")
        if '"/register"' in txt or "'/register'" in txt:
            warn("/auth/register esta activo - desactivalo despues de crear los usuarios")
            tip("Comenta el endpoint /register en routes_auth.py")
    return all_ok

def check_database():
    header(7, "Conexion a base de datos")
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        err("python-dotenv no instalado")
        return False
    host = os.getenv("DB_HOST", "localhost")
    user = os.getenv("DB_USER", "")
    pwd  = os.getenv("DB_PASSWORD", "")
    name = os.getenv("DB_NAME", "")
    if not all([user, pwd, name]):
        err("Faltan DB_USER / DB_PASSWORD / DB_NAME en .env")
        return False
    try:
        from app.database import engine
        from sqlalchemy import text, inspect
        with engine.connect() as conn:
            version = conn.execute(text("SELECT VERSION()")).fetchone()[0]
            ok(f"MySQL conectado - version {version}")
        inspector = inspect(engine)
        existing  = set(inspector.get_table_names())
        expected  = {"usuarios", "inspecciones", "reportes_inspeccion", "logs_auditoria"}
        missing   = expected - existing
        if not missing:
            ok(f"Tablas: {', '.join(sorted(existing))}")
        else:
            warn(f"Tablas faltantes: {', '.join(sorted(missing))}")
            tip('Crea tablas: python -c "from app.database import Base, engine; from app import models; Base.metadata.create_all(bind=engine)"')
        from app.database import SessionLocal
        from app.models import Usuario
        db = SessionLocal()
        try:
            admin = db.query(Usuario).filter_by(rol="admin").first()
            if admin:
                ok(f"Admin encontrado: {admin.nombre} ({admin.nombre_visible})")
            else:
                err("No hay ningun usuario admin registrado")
                tip("Crea uno con:  python admin_cli.py")
        finally:
            db.close()
        return len(missing) == 0
    except Exception as e:
        err(f"Error de conexion: {e}")
        tip(f"Host: {host}  |  DB: {name}  |  User: {user}")
        tip("Verifica que MySQL este corriendo y los datos en .env sean correctos")
        return False

def check_weasyprint():
    header(8, "WeasyPrint - generacion de PDFs")
    try:
        from weasyprint import HTML
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        HTML(string="<html><body><p>Test Misionales</p></body></html>").write_pdf(str(tmp_path))
        size = tmp_path.stat().st_size
        tmp_path.unlink()
        if size > 0:
            ok(f"WeasyPrint genera PDFs correctamente ({size:,} bytes en test)")
            return True
        else:
            err("WeasyPrint genero un PDF vacio")
            return False
    except Exception as e:
        err(f"WeasyPrint fallo: {e}")
        if any(k in str(e).lower() for k in ("cairo", "pango", "gobject", "gtk")):
            warn("Faltan librerias GTK del sistema operativo")
            tip("Windows: instala GTK3 Runtime desde:")
            tip("https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases")
            tip("Despues de instalar GTK, reinicia la PC y activa el venv de nuevo")
        return False

def check_readme():
    header(9, "Consistencia del README")
    readme = Path("README.md")
    if not readme.exists():
        warn("README.md no existe - considera documentar el proyecto")
        return True
    content = readme.read_text(encoding="utf-8")
    issues = []
    if "DB_URL" in content:
        issues.append("README menciona DB_URL (formato antiguo) - el proyecto usa DB_HOST/USER/PASSWORD/NAME")
    if "create_user.py" in content and not Path("create_user.py").exists():
        issues.append("README referencia create_user.py pero el archivo es admin_cli.py")
    if "test_db.py" in content and not Path("test_db.py").exists():
        issues.append("README referencia test_db.py pero ese archivo no existe en el proyecto")
    if "utils_pdf/templates" in content:
        issues.append("README indica app/utils_pdf/templates/ pero las templates estan en app/templates/")
    if not issues:
        ok("README sin inconsistencias criticas")
        return True
    else:
        for issue in issues:
            warn(issue)
        tip("Actualiza el README para reflejar la estructura real del proyecto")
        return False

def main():
    print(f"\n{C.BLUE}")
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║       VALIDACIÓN PRE-DESPLIEGUE · MISIONALES INCUBANT       ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"{C.RESET}")

    checks = [
        ("Dependencias Python",        check_dependencies),
        ("Variables de entorno",       check_env),
        ("Estructura de directorios",  check_directories),
        ("Archivos criticos",          check_files),
        ("Assets estaticos",           check_static_assets),
        ("Seguridad",                  check_security),
        ("Base de datos",              check_database),
        ("WeasyPrint / PDFs",          check_weasyprint),
        ("Consistencia README",        check_readme),
    ]

    results = {}
    for name, fn in checks:
        try:
            results[name] = fn()
        except Exception as e:
            err(f"Error inesperado en '{name}': {e}")
            results[name] = False

    print(f"\n{C.BLUE}{'='*62}")
    print(f"  RESUMEN FINAL")
    print(f"{'='*62}{C.RESET}\n")

    passed = sum(results.values())
    total  = len(results)

    for name, result in results.items():
        color  = C.GREEN if result else C.RED
        symbol = "PASS" if result else "FAIL"
        mark   = "OK" if result else "XX"
        print(f"  {color}[{mark}] {symbol}{C.RESET}  {name}")

    print(f"\n{C.BLUE}{'─'*62}{C.RESET}")
    print(f"\n  Resultado: {passed}/{total} verificaciones pasaron\n")

    if passed == total:
        print(f"{C.GREEN}{'='*62}")
        print("  SISTEMA LISTO PARA DESPLEGAR!")
        print(f"{'='*62}{C.RESET}\n")
        return 0
    else:
        failed = [n for n, r in results.items() if not r]
        print(f"{C.RED}{'='*62}")
        print(f"  {total - passed} verificacion(es) fallaron:")
        for f in failed:
            print(f"       - {f}")
        print("\n  Corrige los errores antes de desplegar.")
        print(f"{'='*62}{C.RESET}\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())