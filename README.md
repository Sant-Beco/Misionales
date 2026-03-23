🚗 Misionales · Sistema de Inspección Vehicular
Incubant SST — Sistema de inspecciones pre-operacionales con generación automática de PDFs, firma digital y panel de administración.

✨ Características principales
MóduloDescripción🔐 AutenticaciónLogin con usuario + PIN (bcrypt), roles admin/conductor, rate limiting, redirección automática por sesión expirada📝 FormularioInspección para Moto, Automóvil y Camión (20 aspectos). Firma digital en canvas. Ruta con sugerencias + escritura libre📄 PDFsGeneración automática con WeasyPrint al registrar. Descarga individual. Consolidado de 15 inspecciones📋 Mis inspeccionesHistorial del conductor con modal de detalle, descarga de PDF por inspección e historial de consolidados📊 Dashboard adminKPIs en tiempo real, gráfica mensual comparativa (Chart.js), ranking de conductores🔍 Vista inspeccionesPanel admin con filtros por conductor, placa, tipo y fecha. Modal de detalle + descarga PDF👥 Gestión de usuariosCrear, editar, suspender/reactivar conductores y administradores📋 AuditoríaLog de todas las acciones administrativas con filtro y búsqueda

🛠 Stack tecnológico
Backend    FastAPI 0.110 · Python 3.11.9 · SQLAlchemy 2.0 · PyMySQL
BD         MySQL 8.0 / 5.7
PDFs       WeasyPrint 62.3 · Jinja2 · Fonts Futura
Frontend   HTML5 · CSS3 · JavaScript vanilla · Chart.js 4
Auth       JWT en httpOnly cookie + Bearer header · bcrypt · rate limiting

📋 Requisitos previos
Python 3.11.9 (obligatorio)
WeasyPrint, SQLAlchemy y bcrypt funcionan sin errores en esta versión exacta.

Descarga: https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe

MySQL 8.0 o 5.7
bash# Verificar versión instalada
mysql --version
GTK3 Runtime — solo Windows
Requerido para que WeasyPrint pueda generar PDFs.

Descarga: https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases
Instalar y reiniciar el equipo antes de continuar.

Git
bashgit --version

🚀 Instalación local
1. Clonar el repositorio
bashgit clone https://github.com/TU-USUARIO/misionales-fastapi.git
cd misionales-fastapi
2. Crear entorno virtual
Cada equipo debe tener su propio venv. No se comparte en GitHub.
bashpython -m venv venv
Activar:
bash# Windows PowerShell
venv\Scripts\activate

# Linux / Mac
source venv/bin/activate
Verificar versión:
bashpython --version
# Debe mostrar: Python 3.11.9
3. Instalar dependencias
bashpip install --upgrade pip
pip install -r requirements.txt
4. Configurar variables de entorno
Copia el archivo de ejemplo y édita los valores:
bashcp .env.example .env
Contenido del .env:
env# Base de datos
DB_HOST=localhost
DB_USER=tu_usuario_mysql
DB_PASSWORD=tu_password_seguro
DB_NAME=misionales_db

# Seguridad — genera una clave única:
# python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=pega_aqui_la_clave_generada

# CORS — IP del servidor o localhost para desarrollo
CORS_ORIGINS=http://localhost:8000

# Opciones de producción (dejar en false para desarrollo)
HTTPS_ENABLED=false
REGISTER_ENABLED=false
DEBUG=false
5. Inicializar base de datos
Crear la base de datos en MySQL:
sqlCREATE DATABASE misionales_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
Las tablas se crean automáticamente al iniciar la aplicación por primera vez gracias a SQLAlchemy.
Si la tabla usuarios ya existe de una instalación anterior, ejecutar:
sqlALTER TABLE usuarios ADD COLUMN IF NOT EXISTS activo INT NOT NULL DEFAULT 1;
6. Crear primer usuario administrador
bashpython admin_cli.py
El CLI te pedirá nombre de usuario, nombre completo, PIN y confirmación.
7. Arrancar el servidor
bash# Desarrollo (con auto-reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Producción (sin reload)
uvicorn app.main:app --host 0.0.0.0 --port 8000
Abrir en el navegador:

App: http://localhost:8000
Docs API: http://localhost:8000/docs


🌐 Deploy en producción (VPS)
Requisitos del servidor

Ubuntu 22.04 o 24.04
Python 3.11.9
MySQL 8.0
WeasyPrint requiere Cairo y Pango: sudo apt install libcairo2 libpango-1.0-0 libpangocairo-1.0-0

Variables de entorno en producción
envCORS_ORIGINS=http://IP_DEL_VPS:8000   # o tu dominio con HTTPS
HTTPS_ENABLED=true                      # cuando tengas SSL activo
DEBUG=false
Servicio systemd
Crear /etc/systemd/system/misionales.service:
ini[Unit]
Description=Misionales FastAPI
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/misionales
EnvironmentFile=/opt/misionales/.env
ExecStart=/opt/misionales/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
bashsudo systemctl enable misionales
sudo systemctl start misionales
sudo systemctl status misionales

📁 Estructura del proyecto
misionales-fastapi/
│
├── app/
│   ├── main.py                    # App principal, CORS, exception handlers
│   ├── database.py                # Conexión SQLAlchemy + MySQL
│   ├── models.py                  # Modelos ORM: Usuario, Inspeccion, Reporte, Log
│   ├── security.py                # JWT, bcrypt, rate limiting, autenticación
│   │
│   ├── routes_auth.py             # Login, logout, registro
│   ├── routes_inspecciones.py     # Submit, mis-inspecciones, PDF individual, consolidado
│   ├── routes_admin.py            # Dashboard, usuarios, inspecciones globales, logs
│   │
│   ├── utils_pdf.py               # Generación PDF con WeasyPrint
│   ├── admin_cli.py               # CLI para crear usuarios desde terminal
│   │
│   ├── templates/
│   │   ├── login.html
│   │   ├── form.html              # Formulario: Moto / Carro / Camión
│   │   ├── lista_inspecciones.html
│   │   ├── pdf_template.html      # PDF individual (A4)
│   │   ├── pdf_template_multiple.html  # PDF consolidado 15 (A4 landscape)
│   │   └── admin/
│   │       ├── dashboard.html
│   │       ├── inspecciones.html
│   │       ├── usuarios.html
│   │       ├── usuario_form.html
│   │       └── logs.html
│   │
│   ├── static/
│   │   ├── css/
│   │   │   └── incubant-theme.css
│   │   ├── img/
│   │   │   └── logotipo_01.png    # ⚠ nombre en minúscula obligatorio
│   │   └── fonts/
│   │       ├── 1_Futura_Md_Bt_negrilla.ttf
│   │       ├── 2_Futura_M_Bt_light.ttf
│   │       ├── 3_Futura_book_bt_parrafos.ttf
│   │       └── 4_Futura_book_italic_bt_parrafoss.ttf
│   │
│   └── data/                      # Generado automáticamente, no se sube a Git
│       ├── generated_pdfs/
│       │   └── usuarios/{id}/
│       │       ├── inspecciones/  # PDFs individuales
│       │       └── reportes/      # PDFs consolidados
│       └── firmas/
│           └── usuarios/{id}/     # PNGs de firmas digitales
│
├── requirements.txt
├── .env.example
├── .gitignore
├── migration.sql                  # Script BD para primer deploy
├── check_fonts.sh                 # Verificador de fonts para WeasyPrint
└── README.md

🔒 Seguridad

PINs hasheados con bcrypt (nunca se guarda el PIN en texto plano)
Tokens JWT con expiración de 24 horas almacenados en BD
Rate limiting: máximo 5 intentos fallidos por IP cada 5 minutos
Rutas admin protegidas por require_admin — conductores no pueden acceder
Cada conductor solo ve y descarga sus propias inspecciones y PDFs
/auth/register deshabilitado por defecto en producción
Cookie con Secure y SameSite=Lax cuando HTTPS_ENABLED=true
Handler global 401/403: redirige al login con mensaje claro en vez de error en blanco


📄 Flujo de una inspección
Conductor llena formulario (Moto/Carro/Camión)
    ↓
Firma digital en canvas
    ↓
Submit → FastAPI genera PDF con WeasyPrint
    ↓
PDF descargado automáticamente en el navegador
    ↓
Inspección guardada en BD (tabla inspecciones)
    ↓
Al llegar a 15 inspecciones → PDF consolidado mensual
    ↓
Las 15 inspecciones se archivan (tabla reportes_inspeccion)
    ↓
Historial disponible en "Mis inspecciones"

🐛 Problemas frecuentes
WeasyPrint no genera PDF (Windows)
→ Instalar GTK3 Runtime y reiniciar el equipo.
Error: No module named 'cairo'
→ El GTK3 no está instalado o no se reinició después de instalarlo.
Logo no aparece en el PDF
→ Verificar que el archivo se llama logotipo_01.png en minúscula. Linux es sensible a mayúsculas.
Error al conectar a MySQL
→ Verificar que DB_USER, DB_PASSWORD y DB_NAME en el .env coincidan con los de MySQL.
Columna activo no existe
→ Ejecutar: ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS activo INT NOT NULL DEFAULT 1;

📞 Soporte
Incubant · Antioqueña de Incubación S.A.S.
Sistema desarrollado para gestión SST de conductores misionales.