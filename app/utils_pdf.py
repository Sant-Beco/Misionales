# app/utils_pdf.py
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"

env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

def render_pdf_from_template(template_name: str, context: dict, output_path: str):
    template = env.get_template(template_name)
    html_out = template.render(**context)
    HTML(string=html_out, base_url=str(TEMPLATES_DIR)).write_pdf(output_path)
