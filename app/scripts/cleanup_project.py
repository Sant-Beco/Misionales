# cleanup_project.py
"""
Script para limpiar y organizar el proyecto MISONALES antes del despliegue

Acciones:
1. Mover scripts de prueba a /scripts
2. Limpiar archivos temporales
3. Organizar backups
4. Verificar .gitignore
5. Generar reporte de limpieza
"""

import os
import shutil
from pathlib import Path
from datetime import datetime

# ===============================
# CONFIGURACIÓN
# ===============================

PROJECT_ROOT = Path(".")
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
BACKUP_DIR = PROJECT_ROOT / "backups"
DOCS_DIR = PROJECT_ROOT / "docs"

# Archivos a mover a /scripts
FILES_TO_MOVE_TO_SCRIPTS = [
    "crear_15_inspecciones.py",
    "test_db.py",
    "test_firmas_debug.py",
    "test_pdf.py",
    "test_upsert.py",  # Si existe
]

# Archivos a mover a /backups (archivos _OLD, _BACKUP)
BACKUP_PATTERNS = [
    "*_OLD.*",
    "*_BACKUP.*",
    "*_old.*",
    "*_backup.*",
]

# Documentación a mover a /docs
DOCS_FILES = [
    "ANALISIS_SEGURIDAD_CRITICO.md",
    "GUIA_APLICACION.md",
    "GUIA_DESPLIEGUE_VPS.md",
    "CHECKLIST_FINAL.md",
    "RESUMEN_MEJORAS.md",
]

# Archivos temporales a eliminar
TEMP_PATTERNS = [
    "*.pyc",
    "__pycache__",
    "*.tmp",
    "*.log",
    ".pytest_cache",
    ".coverage",
]

# ===============================
# FUNCIONES
# ===============================

def create_directories():
    """Crear directorios de organización"""
    print("📁 Creando directorios...")
    SCRIPTS_DIR.mkdir(exist_ok=True)
    BACKUP_DIR.mkdir(exist_ok=True)
    DOCS_DIR.mkdir(exist_ok=True)
    print("   ✅ Directorios creados")

def move_scripts():
    """Mover scripts de prueba a /scripts"""
    print("\n📝 Moviendo scripts de prueba...")
    moved = 0
    
    for filename in FILES_TO_MOVE_TO_SCRIPTS:
        source = PROJECT_ROOT / filename
        if source.exists():
            dest = SCRIPTS_DIR / filename
            shutil.move(str(source), str(dest))
            print(f"   ✅ {filename} → scripts/")
            moved += 1
    
    if moved == 0:
        print("   ℹ️  No hay scripts que mover")
    else:
        print(f"   ✅ {moved} archivos movidos")

def move_backups():
    """Mover archivos de backup"""
    print("\n💾 Moviendo archivos de backup...")
    moved = 0
    
    for pattern in BACKUP_PATTERNS:
        for file in PROJECT_ROOT.rglob(pattern):
            if file.is_file() and "venv" not in str(file):
                relative = file.relative_to(PROJECT_ROOT)
                dest = BACKUP_DIR / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(file), str(dest))
                print(f"   ✅ {relative} → backups/")
                moved += 1
    
    if moved == 0:
        print("   ℹ️  No hay backups que mover")
    else:
        print(f"   ✅ {moved} archivos movidos")

def move_docs():
    """Mover documentación a /docs"""
    print("\n📚 Moviendo documentación...")
    moved = 0
    
    for filename in DOCS_FILES:
        source = PROJECT_ROOT / filename
        if source.exists():
            dest = DOCS_DIR / filename
            shutil.move(str(source), str(dest))
            print(f"   ✅ {filename} → docs/")
            moved += 1
    
    if moved == 0:
        print("   ℹ️  No hay documentos que mover")
    else:
        print(f"   ✅ {moved} archivos movidos")

def clean_temp_files():
    """Eliminar archivos temporales"""
    print("\n🗑️  Limpiando archivos temporales...")
    deleted = 0
    
    # Archivos __pycache__
    for pycache in PROJECT_ROOT.rglob("__pycache__"):
        if pycache.is_dir():
            shutil.rmtree(pycache)
            print(f"   🗑️  {pycache.relative_to(PROJECT_ROOT)}")
            deleted += 1
    
    # Archivos .pyc
    for pyc in PROJECT_ROOT.rglob("*.pyc"):
        if "venv" not in str(pyc):
            pyc.unlink()
            deleted += 1
    
    if deleted == 0:
        print("   ✅ No hay archivos temporales")
    else:
        print(f"   ✅ {deleted} archivos eliminados")

def verify_gitignore():
    """Verificar .gitignore"""
    print("\n🔒 Verificando .gitignore...")
    
    gitignore = PROJECT_ROOT / ".gitignore"
    if not gitignore.exists():
        print("   ⚠️  .gitignore no existe")
        return
    
    content = gitignore.read_text()
    
    required_patterns = [
        ".env",
        "*.db",
        "venv/",
        "__pycache__/",
        "*.pyc",
        "app/data/generated_pdfs/*.pdf",
        "app/data/firmas/*.png",
        "app/logs/*.log",
    ]
    
    missing = []
    for pattern in required_patterns:
        if pattern not in content:
            missing.append(pattern)
    
    if missing:
        print("   ⚠️  Faltan patrones en .gitignore:")
        for p in missing:
            print(f"      - {p}")
    else:
        print("   ✅ .gitignore completo")

def generate_structure_report():
    """Generar reporte de estructura del proyecto"""
    print("\n📊 Generando reporte de estructura...")
    
    report = []
    report.append("# ESTRUCTURA DEL PROYECTO MISONALES")
    report.append(f"\nGenerado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    report.append("```")
    
    def add_tree(path, prefix="", is_last=True):
        """Generar árbol de directorios"""
        if path.name in [".git", "venv", "__pycache__", "node_modules"]:
            return
        
        connector = "└── " if is_last else "├── "
        report.append(f"{prefix}{connector}{path.name}")
        
        if path.is_dir():
            children = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
            children = [c for c in children if c.name not in [".git", "venv", "__pycache__"]]
            
            for i, child in enumerate(children):
                is_last_child = i == len(children) - 1
                extension = "    " if is_last else "│   "
                add_tree(child, prefix + extension, is_last_child)
    
    add_tree(PROJECT_ROOT)
    report.append("```")
    
    report_file = PROJECT_ROOT / "ESTRUCTURA_PROYECTO.md"
    report_file.write_text("\n".join(report), encoding="utf-8")
    print(f"   ✅ Reporte guardado: {report_file}")

def final_summary():
    """Resumen final"""
    print("\n" + "="*60)
    print("✅ LIMPIEZA COMPLETADA")
    print("="*60)
    print("\n📁 Estructura organizada:")
    print("   /scripts    - Scripts de prueba y utilidades")
    print("   /backups    - Archivos de respaldo")
    print("   /docs       - Documentación del proyecto")
    print("   /app        - Código fuente principal")
    print("\n📋 Próximos pasos:")
    print("   1. Revisar ESTRUCTURA_PROYECTO.md")
    print("   2. Hacer commit de cambios")
    print("   3. Ejecutar validate_production.py")
    print("   4. Desplegar a VPS")
    print("\n" + "="*60)

# ===============================
# MAIN
# ===============================

def main():
    print("="*60)
    print("🧹 LIMPIEZA Y ORGANIZACIÓN DEL PROYECTO")
    print("="*60)
    
    try:
        create_directories()
        move_scripts()
        move_backups()
        move_docs()
        clean_temp_files()
        verify_gitignore()
        generate_structure_report()
        final_summary()
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error durante la limpieza: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())