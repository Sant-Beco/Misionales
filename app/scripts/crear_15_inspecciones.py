#!/usr/bin/env python3
"""
Script para crear 15 inspecciones de prueba y generar PDF consolidado

Uso:
    python crear_15_inspecciones.py

Esto creará 15 inspecciones para el usuario autenticado y generará
automáticamente el PDF consolidado.
"""

import requests
import base64
import json
from datetime import datetime, timedelta
import random

# ===============================
# CONFIGURACIÓN
# ===============================

BASE_URL = "http://127.0.0.1:8000"

# Credenciales del usuario (cambiar según tu usuario)
LOGIN_USER = input("Usuario (ej: Santiago): ").strip() or "Santiago"
LOGIN_PIN = input("PIN: ").strip()

# ===============================
# DATOS DE PRUEBA
# ===============================

PLACAS = [
    "ABC123", "DEF456", "GHI789", "JKL012", "MNO345",
    "PQR678", "STU901", "VWX234", "YZA567", "BCD890",
    "EFG123", "HIJ456", "KLM789", "NOP012", "QRS345"
]

PROCESOS = ["Traslado", "Mandado", "Actividad misional"]
DESDE_HASTA = [
    ("La Esperanza", "La Planta"),
    ("La Fe", "La Esperanza"),
    ("La Planta", "Municipio"),
    ("Municipio", "La Fe"),
]

MARCAS = ["Yamaha", "Honda", "Suzuki", "Kawasaki", "AKT"]
MODELOS = ["2020", "2021", "2022", "2023"]

# ===============================
# FUNCIÓN: Crear firma dummy
# ===============================

def create_dummy_signature():
    """
    Crea una firma PNG dummy en base64
    (Un rectángulo simple con texto)
    """
    # PNG 1x1 transparente base64
    dummy_png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    return f"data:image/png;base64,{dummy_png}"


# ===============================
# FUNCIÓN: Login
# ===============================

def login(usuario, pin):
    """
    Hace login y retorna el token
    """
    print(f"\n🔐 Iniciando sesión como: {usuario}")
    
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={"nombre": usuario, "pin": pin}
    )
    
    if response.status_code != 200:
        print(f"❌ Error en login: {response.status_code}")
        print(response.text)
        return None
    
    data = response.json()
    token = data.get("access_token")
    print(f"✅ Login exitoso! Token: {token[:20]}...")
    return token


# ===============================
# FUNCIÓN: Crear inspección
# ===============================

def crear_inspeccion(token, numero, total=15):
    """
    Crea una inspección de prueba
    """
    idx = numero - 1
    
    # Datos variables
    placa = PLACAS[idx] if idx < len(PLACAS) else f"TEST{idx:03d}"
    proceso = random.choice(PROCESOS)
    desde, hasta = random.choice(DESDE_HASTA)
    marca = random.choice(MARCAS)
    modelo = random.choice(MODELOS)
    
    # Aspectos (todos buenos excepto algunos aleatorios en M)
    aspectos = {}
    for i in range(1, 14):
        # 80% probabilidad de B, 20% de M
        aspectos[i] = "B" if random.random() > 0.2 else "M"
    
    # Si hay M, agregar observación
    observaciones = ""
    if "M" in aspectos.values():
        observaciones = f"Inspeccion {numero}/{total}: Aspectos marcados requieren revisión"
    
    # Crear payload
    data = {
        "placa": placa,
        "proceso": proceso,
        "desde": desde,
        "hasta": hasta,
        "marca": marca,
        "gasolina": "si",
        "modelo": modelo,
        "motor": "110",
        "tipo_vehiculo": "Moto",
        "linea": "XYZ",
        "licencia_num": "1234567890",
        "licencia_venc": (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d"),
        "porte_propiedad": "ABC123",
        "soat": "DEF456",
        "certificado_emision": "GHI789",
        "poliza_seguro": "JKL012",
        "aspectos": json.dumps(aspectos),
        "firma_dataurl": create_dummy_signature(),
        "observaciones": observaciones,
        "condiciones_optimas": "SI"
    }
    
    print(f"📝 Creando inspección {numero}/{total} - Placa: {placa}")
    
    response = requests.post(
        f"{BASE_URL}/inspecciones/submit",
        data=data,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code == 200:
        # Si es la 15, descargará el PDF consolidado
        if numero == total:
            filename = f"reporte15_consolidado_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            with open(filename, "wb") as f:
                f.write(response.content)
            print(f"🎉 ¡PDF CONSOLIDADO GENERADO! → {filename}")
            return "consolidado"
        else:
            # PDF individual
            cd = response.headers.get("content-disposition", "")
            filename = "inspeccion.pdf"
            if "filename=" in cd:
                filename = cd.split("filename=")[-1].strip('"')
            
            with open(f"test_inspeccion_{numero}.pdf", "wb") as f:
                f.write(response.content)
            print(f"   ✅ PDF individual guardado: test_inspeccion_{numero}.pdf")
            return "individual"
    else:
        print(f"   ❌ Error: {response.status_code}")
        print(f"   {response.text[:200]}")
        return None


# ===============================
# MAIN
# ===============================

def main():
    print("="*60)
    print("🚀 GENERADOR DE 15 INSPECCIONES DE PRUEBA")
    print("="*60)
    
    # Login
    token = login(LOGIN_USER, LOGIN_PIN)
    if not token:
        print("\n❌ No se pudo hacer login. Verifica credenciales.")
        return
    
    # Crear 15 inspecciones
    print(f"\n📋 Creando 15 inspecciones...")
    print("-"*60)
    
    for i in range(1, 16):
        resultado = crear_inspeccion(token, i, total=15)
        
        if resultado == "consolidado":
            print("\n" + "="*60)
            print("🎉 ¡PROCESO COMPLETADO!")
            print("="*60)
            print("\n✅ Se crearon 15 inspecciones individuales")
            print("✅ Se generó el PDF consolidado automáticamente")
            print("\nRevisa los archivos:")
            print("   - test_inspeccion_1.pdf hasta test_inspeccion_14.pdf")
            print("   - reporte15_consolidado_*.pdf")
            print("\n💡 Verifica que la firma aparezca en el consolidado")
            break
        elif not resultado:
            print("\n⚠️ Error creando inspección. Deteniendo proceso.")
            break
    
    print("\n" + "="*60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Proceso interrumpido por el usuario")
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()