# app/utils_pdf.py

import logging
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
from pathlib import Path

# ==========================
# Configuración logging
# ==========================
logger = logging.getLogger("utils_pdf")

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
    """

    try:
        # Render HTML desde Jinja
        template = env.get_template(template_name)
        html_content = template.render(**context)

        # Generar PDF
        HTML(
            string=html_content,
            base_url=str(TEMPLATES_DIR)
        ).write_pdf(output_path)

        logger.info("PDF generado correctamente: %s", output_path)

    except Exception as e:
        logger.exception(
            "Error generando PDF. Template=%s Output=%s",
            template_name,
            output_path
        )
        raise
