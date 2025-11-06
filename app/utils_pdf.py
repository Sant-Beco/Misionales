# app/utils_pdf.py

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
from pathlib import Path

# 📌 Ubicación base (carpeta app/utils_pdf.py)
BASE_DIR = Path(__file__).resolve().parent

# 📌 Carpeta de plantillas
TEMPLATES_DIR = BASE_DIR / "templates"

# ✅ Motor de plantillas Jinja2
env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=True
)

def render_pdf_from_template(template_name: str, context: dict, output_path: str):
    """
    Renderiza un PDF usando una plantilla HTML + contexto.
    Compatible 100% con WeasyPrint.

    :param template_name: Nombre de la plantilla (string)
    :param context: Diccionario con los valores
    :param output_path: Ruta del PDF final
    """

    try:
        # ✅ Render HTML desde Jinja
        template = env.get_template(template_name)
        html_content = template.render(**context)

        # ✅ Base URL obligatorio para imágenes locales
        HTML(
            string=html_content,
            base_url=str(TEMPLATES_DIR)
        ).write_pdf(output_path)

        print(f"✅ PDF generado: {output_path}")

    except Exception as e:
        print(f"❌ Error generando PDF desde {template_name}: {e}")
        raise

