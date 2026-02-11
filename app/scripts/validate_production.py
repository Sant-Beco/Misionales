#!/usr/bin/env python3
"""
Script de validación pre-despliegue para MISONALES

Verifica que todo esté listo para producción
"""

import os
import sys
from pathlib import Path

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def print_ok(msg):
    print(f"{Colors.GREEN}✅ {msg}{Colors.RESET}")

def print_error(msg):
    print(f"{Colors.RED}❌ {msg}{Colors.RESET}")

def print_warning(msg):
    print(f"{Colors.YELLOW}⚠️  {msg}{Colors.RESET}")

def print_header(msg):
    print(f"\n{Colors.BLUE}{'='*60}")
    print(f"{msg}")
    print(f"{'='*60}{Colors.RESET}\n")

def check_env():
    """Verificar variables de entorno"""
    print_header("Verificando variables de entorno")
    
    if not Path(".env").exists():
        print_error(".env no existe. Copia .env.example y configúralo")
        return False
    
    required_vars = ["DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME"]
    
    from dotenv import load_dotenv
    load_dotenv()
    
    all_ok = True
    for var in required_vars:
        if os.getenv(var):
            print_ok(f"{var} configurado")
        else:
            print_error(f"{var} faltante en .env")
            all_ok = False
    
    return all_ok

def check_directories():
    """Verificar estructura de directorios"""
    print_header("Verificando estructura de directorios")
    
    required_dirs = [
        "app/data",
        "app/data/generated_pdfs",
        "app/data/firmas",
        "app/logs",
        "app/static",
        "app/static/css",
        "app/static/js",
        "app/static/img",
        "app/templates",
    ]
    
    all_ok = True
    for dir_path in required_dirs:
        p = Path(dir_path)
        if p.exists():
            print_ok(f"{dir_path}")
        else:
            print_error(f"{dir_path} no existe")
            all_ok = False
    
    return all_ok

def check_files():
    """Verificar archivos críticos"""
    print_header("Verificando archivos críticos")
    
    required_files = [
        "app/main.py",
        "app/database.py",
        "app/models.py",
        "app/security.py",
        "app/routes_auth.py",
        "app/routes_inspecciones.py",
        "app/utils_pdf.py",
        "app/templates/login.html",
        "app/templates/form.html",
        "app/static/css/style.css",
        "app/static/js/firma.js",
        "requirements.txt",
    ]
    
    all_ok = True
    for file_path in required_files:
        p = Path(file_path)
        if p.exists():
            print_ok(f"{file_path}")
        else:
            print_error(f"{file_path} no existe")
            all_ok = False
    
    return all_ok

def check_dependencies():
    """Verificar dependencias de Python"""
    print_header("Verificando dependencias")
    
    try:
        import fastapi
        print_ok("FastAPI instalado")
    except ImportError:
        print_error("FastAPI no instalado")
        return False
    
    try:
        import passlib
        print_ok("passlib instalado")
    except ImportError:
        print_error("passlib no instalado")
        return False
    
    try:
        import pymysql
        print_ok("pymysql instalado")
    except ImportError:
        print_error("pymysql no instalado")
        return False
    
    try:
        import weasyprint
        print_ok("weasyprint instalado")
    except ImportError:
        print_error("weasyprint no instalado")
        return False
    
    return True

def check_security():
    """Verificar configuración de seguridad"""
    print_header("Verificando seguridad")
    
    # Verificar que .env no esté en git
    if Path(".env").exists():
        import subprocess
        result = subprocess.run(
            ["git", "check-ignore", ".env"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print_ok(".env está en .gitignore")
        else:
            print_error(".env NO está en .gitignore - ¡PELIGRO!")
            return False
    
    # Verificar SECRET_KEY
    from dotenv import load_dotenv
    load_dotenv()
    
    secret_key = os.getenv("SECRET_KEY", "")
    if len(secret_key) >= 32:
        print_ok(f"SECRET_KEY tiene longitud adecuada ({len(secret_key)} caracteres)")
    else:
        print_error(f"SECRET_KEY muy corta ({len(secret_key)} caracteres, mínimo 32)")
        return False
    
    return True

def check_database():
    """Verificar conexión a base de datos"""
    print_header("Verificando conexión a base de datos")
    
    try:
        from app.database import engine
        connection = engine.connect()
        connection.close()
        print_ok("Conexión a base de datos exitosa")
        return True
    except Exception as e:
        print_error(f"No se puede conectar a la base de datos: {e}")
        return False

def main():
    print(f"\n{Colors.BLUE}")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║     VALIDACIÓN PRE-DESPLIEGUE - MISONALES                 ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print(f"{Colors.RESET}\n")
    
    checks = [
        ("Variables de entorno", check_env),
        ("Estructura de directorios", check_directories),
        ("Archivos críticos", check_files),
        ("Dependencias Python", check_dependencies),
        ("Configuración de seguridad", check_security),
        ("Conexión a base de datos", check_database),
    ]
    
    results = {}
    
    for name, check_func in checks:
        try:
            results[name] = check_func()
        except Exception as e:
            print_error(f"Error en '{name}': {str(e)}")
            results[name] = False
    
    # Resumen
    print_header("RESUMEN")
    
    total = len(results)
    passed = sum(results.values())
    
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        color = Colors.GREEN if result else Colors.RED
        print(f"{color}{status}{Colors.RESET} - {name}")
    
    print(f"\n{Colors.BLUE}{'─'*60}{Colors.RESET}")
    print(f"\nResultado: {passed}/{total} verificaciones pasaron\n")
    
    if passed == total:
        print(f"{Colors.GREEN}{'='*60}")
        print("🎉 ¡SISTEMA LISTO PARA DESPLEGAR!")
        print(f"{'='*60}{Colors.RESET}\n")
        return 0
    else:
        print(f"{Colors.RED}{'='*60}")
        print("⚠️  SISTEMA NO ESTÁ LISTO")
        print("Por favor corrige los errores antes de desplegar")
        print(f"{'='*60}{Colors.RESET}\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())