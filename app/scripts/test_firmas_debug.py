# test_firmas_debug.py
"""
Script para debuggear problema de firmas en PDF consolidado
"""

from app.database import SessionLocal
from app import models
from pathlib import Path
import base64

def test_firma_loading():
    db = SessionLocal()
    
    # Obtener última inspección
    inspeccion = db.query(models.Inspeccion).order_by(models.Inspeccion.id.desc()).first()
    
    if not inspeccion:
        print("❌ No hay inspecciones en la BD")
        return
    
    print(f"✅ Inspección ID: {inspeccion.id}")
    print(f"   Usuario ID: {inspeccion.usuario_id}")
    print(f"   Placa: {inspeccion.placa}")
    print(f"   firma_file: {inspeccion.firma_file}")
    
    if not inspeccion.firma_file:
        print("⚠️  No tiene firma guardada")
        return
    
    # Intentar encontrar la firma
    print(f"\n🔍 Buscando firma en disco...")
    
    # Opción 1: Ruta nueva (por usuario)
    user_path = Path(f"app/data/generated_pdfs/usuarios/{inspeccion.usuario_id}/firmas/{inspeccion.firma_file}")
    print(f"   Opción 1 (usuario): {user_path}")
    print(f"   Existe: {user_path.exists()}")
    
    # Opción 2: Ruta legacy
    legacy_path = Path(f"app/data/generated_pdfs/{inspeccion.firma_file}")
    print(f"   Opción 2 (legacy): {legacy_path}")
    print(f"   Existe: {legacy_path.exists()}")
    
    # Opción 3: Ruta en data/firmas
    firmas_path = Path(f"app/data/firmas/{inspeccion.firma_file}")
    print(f"   Opción 3 (data/firmas): {firmas_path}")
    print(f"   Existe: {firmas_path.exists()}")
    
    # Buscar cualquier archivo con ese nombre
    print(f"\n🔎 Buscando en todo el proyecto...")
    base = Path("app/data")
    for firma in base.rglob(inspeccion.firma_file):
        print(f"   ✅ ENCONTRADA: {firma}")
        
        # Intentar cargar como base64
        try:
            encoded = base64.b64encode(firma.read_bytes()).decode("utf-8")
            print(f"   ✅ Base64 generado correctamente ({len(encoded)} caracteres)")
            print(f"   Preview: data:image/png;base64,{encoded[:50]}...")
        except Exception as e:
            print(f"   ❌ Error al codificar: {e}")
    
    db.close()

if __name__ == "__main__":
    test_firma_loading()