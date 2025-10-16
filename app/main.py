# app/main.py
import os
import base64
import json
from datetime import datetime
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from app.utils_pdf import render_pdf_from_template


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PDF_DIR = DATA_DIR / "generated_pdfs"
INSPECCIONES_FILE = DATA_DIR / "inspecciones.json"

os.makedirs(PDF_DIR, exist_ok=True)
if not INSPECCIONES_FILE.exists():
    INSPECCIONES_FILE.write_text("[]", encoding="utf-8")

app = FastAPI()
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.get("/", response_class=HTMLResponse)
async def form_get(request: Request):
    # fecha por defecto
    hoy = datetime.now().strftime("%d - %m - %Y")
    return templates.TemplateResponse("form.html", {"request": request, "fecha": hoy})


@app.post("/submit")
async def submit_inspeccion(
    request: Request,
    nombre_conductor: str = Form(...),
    placa: str = Form(""),
    proceso: str = Form(""),
    desde: str = Form(""),
    hasta: str = Form(""),
    marca: str = Form(""),
    gasolina: str = Form(""),
    modelo: str = Form(""),
    motor: str = Form(""),
    tipo_vehiculo: str = Form("Moto"),
    linea: str = Form(""),
    licencia_num: str = Form(""),
    licencia_venc: str = Form(""),
    porte_propiedad: str = Form(""),
    soat: str = Form(""),
    certificado_emision: str = Form(""),
    poliza_seguro: str = Form(""),
    aspectos: str = Form("{}"),  # JSON string de los aspectos B/M
    firma_dataurl: str = Form(None),
    observaciones: str = Form(""),
    condiciones_optimas: str = Form("SI")
):
    # parse aspectos (enviamos JSON desde el form)
    try:
        import json as _json
        aspectos_dict = _json.loads(aspectos)
    except Exception:
        aspectos_dict = {}

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    # guardar firma en png
    firma_filename = None
    if firma_dataurl:
        header, encoded = firma_dataurl.split(",", 1)
        data = base64.b64decode(encoded)
        firma_filename = f"firma_{timestamp}.png"
        (PDF_DIR / firma_filename).write_bytes(data)

    # guardar registro en inspecciones.json
    registro = {
        "id": timestamp,
        "fecha": datetime.now().isoformat(),
        "nombre_conductor": nombre_conductor,
        "placa": placa,
        "proceso": proceso,
        "desde": desde,
        "hasta": hasta,
        "marca": marca,
        "gasolina": gasolina,
        "modelo": modelo,
        "motor": motor,
        "tipo_vehiculo": tipo_vehiculo,
        "linea": linea,
        "licencia_num": licencia_num,
        "licencia_venc": licencia_venc,
        "porte_propiedad": porte_propiedad,
        "soat": soat,
        "certificado_emision": certificado_emision,
        "poliza_seguro": poliza_seguro,
        "aspectos": aspectos_dict,
        "observaciones": observaciones,
        "condiciones_optimas": condiciones_optimas,
        "firma_file": firma_filename
    }

    # append to JSON file
    with open(INSPECCIONES_FILE, "r+", encoding="utf-8") as f:
        data = json.load(f)
        data.append(registro)
        f.seek(0)
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.truncate()

    # Generar PDF (render template con datos)
    html_context = {
        "registro": registro,
        "fecha": datetime.now().strftime("%d - %m - %Y"),
        "codigo": "FO-SST-063",
        "version": "01",
    }
    pdf_filename = f"inspeccion_{timestamp}.pdf"
    pdf_path = PDF_DIR / pdf_filename
    render_pdf_from_template("pdf_template.html", html_context, output_path=str(pdf_path))

    # devolver PDF para descarga
    return FileResponse(path=str(pdf_path), media_type="application/pdf", filename=pdf_filename)
