#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════
#  MISIONALES · Incubant SST
#  Script de verificación de fonts Futura
#  Ejecutar desde la raíz del proyecto: bash check_fonts.sh
# ═══════════════════════════════════════════════════════

set -e

# Colores
GREEN='\033[0;32m'
AMBER='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo "══════════════════════════════════════════"
echo "  Verificación de fonts para WeasyPrint"
echo "══════════════════════════════════════════"
echo ""

FONTS_DIR="./app/static/fonts"
ERRORS=0
OK=0

declare -A FONTS=(
  ["1_Futura_Md_Bt_negrilla.ttf"]="Futura Medium (negrilla)"
  ["2_Futura_M_Bt_light.ttf"]="Futura Light"
  ["3_Futura_book_bt_parrafos.ttf"]="Futura Book (párrafos)"
  ["4_Futura_book_italic_bt_parrafoss.ttf"]="Futura Book Italic"
)

# Verificar que existe el directorio
if [ ! -d "$FONTS_DIR" ]; then
  echo -e "${RED}❌ Directorio $FONTS_DIR no existe${NC}"
  echo ""
  echo "Solución:"
  echo "  mkdir -p $FONTS_DIR"
  echo "  # Luego copiar los 4 archivos .ttf"
  exit 1
fi

echo "Directorio: $FONTS_DIR"
echo ""

for filename in "${!FONTS[@]}"; do
  path="$FONTS_DIR/$filename"
  label="${FONTS[$filename]}"

  if [ -f "$path" ]; then
    size=$(du -h "$path" | cut -f1)
    echo -e "${GREEN}  ✅ $filename${NC}"
    echo -e "     $label · $size"
    ((OK++))
  else
    echo -e "${RED}  ❌ $filename — FALTA${NC}"
    echo -e "     $label"
    ((ERRORS++))
  fi
  echo ""
done

# Verificar que el logo existe
LOGO="./app/static/img/logotipo_01.png"
echo "══ Logo ══"
if [ -f "$LOGO" ]; then
  size=$(du -h "$LOGO" | cut -f1)
  echo -e "${GREEN}  ✅ logotipo_01.png — $size${NC}"
else
  echo -e "${RED}  ❌ logotipo_01.png — FALTA${NC}"
  echo -e "     Ruta esperada: $LOGO"
  echo -e "${AMBER}     ⚠ Los PDFs generarán sin logo${NC}"
  ((ERRORS++))
fi

echo ""
echo "══ Resultado ══"

if [ $ERRORS -eq 0 ]; then
  echo -e "${GREEN}  ✅ Todo OK — $OK fonts + logo listos${NC}"
  echo ""
  echo "Verificando que WeasyPrint puede leer los fonts..."
  python3 - <<PYEOF
from pathlib import Path
import sys

fonts_dir = Path("./app/static/fonts")
ok = 0
for f in fonts_dir.glob("*.ttf"):
    try:
        data = f.read_bytes()
        if data[:4] in (b'\x00\x01\x00\x00', b'OTTO', b'true', b'ttcf'):
            print(f"  ✅ {f.name} — TTF válido ({len(data)//1024}kb)")
            ok += 1
        else:
            print(f"  ⚠️  {f.name} — formato no reconocido")
    except Exception as e:
        print(f"  ❌ {f.name} — {e}")

if ok == 4:
    print("\n  ✅ Todos los fonts son TTF válidos y legibles")
else:
    print(f"\n  ⚠️  Solo {ok}/4 fonts válidos")
    sys.exit(1)
PYEOF
else
  echo -e "${RED}  ❌ Faltan $ERRORS archivos${NC}"
  echo ""
  echo "Pasos para solucionar:"
  echo "  1. Copiar los .ttf desde tu máquina local al VPS:"
  echo "     scp ./app/static/fonts/*.ttf usuario@IP_VPS:/ruta/proyecto/app/static/fonts/"
  echo ""
  echo "  2. O usando rsync (copia solo lo que falta):"
  echo "     rsync -av ./app/static/fonts/ usuario@IP_VPS:/ruta/proyecto/app/static/fonts/"
  exit 1
fi

echo ""
echo "══════════════════════════════════════════"
echo "  Listo para generar PDFs"
echo "══════════════════════════════════════════"
echo ""