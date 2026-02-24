Sistema de Inspecciones (FastAPI + MySQL + WeasyPrint)
📌 1. Requisitos previos

Antes de instalar el proyecto necesitas:

✔ Python 3.11.9 (obligatorio)

WeasyPrint + SQLAlchemy + bcrypt funcionan sin errores en esta versión.

Descarga:
https://www.python.org/downloads/release/python-3119/

o 

https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe

✔ Git

Para clonar el repositorio en varios computadores.

✔ MySQL 5.7 / 8.0

Base de datos usada por el proyecto.

✔ GTK 3 Runtime (solo Windows)

Necesario para que WeasyPrint genere PDF.

Descarga oficial:
https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases

Instalar y reiniciar el PC.

📌 2. Clonar el repositorio
git clone https://github.com/TU-USUARIO/misionales-fastapi.git
cd misionales-fastapi

📌 3. Crear entorno virtual (venv)

Cada computador debe tener su propio venv, NO se comparte en GitHub.

python -m venv venv


Activar:

Windows PowerShell

venv\Scripts\activate


Linux/Mac

source venv/bin/activate


Verifica:

python --version


Debe mostrar:

Python 3.11.9

📌 4. Instalar dependencias
pip install --upgrade pip
pip install -r requirements.txt

📌 5. Variables de entorno (.env)

El archivo .env NO se sube a GitHub (por seguridad).

Ejemplo:

DB_URL=mysql+pymysql://usuario:password@localhost/misionales_db
SECRET_KEY=supersecreto

📌 6. Inicializar base de datos

El proyecto usa SQLAlchemy para crear las tablas automáticamente.

Opcional: prueba conexión

python test_db.py

📌 7. Crear usuarios administradores
python create_user.py

📌 8. Ejecutar servidor FastAPI
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000


Abrir navegador:

http://localhost:8000


API docs:

http://localhost:8000/docs

📌 9. Generación de PDF con WeasyPrint

Este proyecto usa:

Plantillas HTML (Jinja2)

WeasyPrint 62.3

Motor CSS moderno

Imagen corporativa

Las plantillas están en:

app/utils_pdf/templates/


Generación automática al registrar inspecciones.

📌 10. Estructura del proyecto
misionales-fastapi/
│
├── app/
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── routes_auth.py
│   ├── routes_inspecciones.py
│   ├── utils_pdf/
│   │     ├── utils_pdf.py
│   │     ├── templates/
│   │     │      ├── template.html
│   │     │      ├── template_multiple.html
│   ├── static/
│   │     ├── css/
│   │     ├── js/
│   │     ├── img/
│
├── create_user.py
├── requirements.txt
├── .gitignore
├── README.md
└── .env (NO subir)

Sistema MISONALES
├── 🔐 Login de usuarios
├── 📝 Formulario de inspecciones
├── ✍️ Firma digital
├── 📄 PDFs individuales
├── 📊 PDF consolidado de 15
├── 👥 Panel de usuarios ← NUEVO
├── 📋 Logs de auditoría ← NUEVO
└── 🔧 Gestión profesional ← NUEVO