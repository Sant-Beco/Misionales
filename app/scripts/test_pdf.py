from app.utils_pdf import render_pdf_from_template
from datetime import datetime
from pathlib import Path

OUTPUT = Path("app/data/test_pdf_utils.pdf")

context = {
    "registro": {
        "nombre_conductor": "Juan Perez",
        "placa": "ABC123",
        "proceso": "Prueba",
        "desde": "Origen",
        "hasta": "Destino",
        "marca": "Yamaha",
        "modelo": "2022",
        "motor": "110",
        "tipo_vehiculo": "Moto",
        "licencia_num": "123456789",
        "observaciones": "Prueba de generación PDF",
        "condiciones_optimas": "SI",
        "aspectos_parsed": {},
        "firma_base64": None,
        "firma_path": None,
    },
    "fecha": datetime.now().strftime("%d-%m-%Y"),
    "codigo": "TEST-001",
    "version": "01",
    "logo_path": "",
}

render_pdf_from_template(
    "pdf_template.html",
    context,
    output_path=str(OUTPUT)
)

print("PDF generado en:", OUTPUT)
