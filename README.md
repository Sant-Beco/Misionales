<div align="center">

<img src="app/static/img/Logotipo_01.png" alt="Incubant" height="72" />

# Misionales · Sistema de Inspección Vehicular

**Herramienta SST para conductores misionales de Incubant**  
Inspecciones pre-operacionales digitales · Firma en canvas · PDFs automáticos · Panel de administración

[![Python](https://img.shields.io/badge/Python-3.11.9-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?style=flat-square&logo=mysql&logoColor=white)](https://mysql.com)
[![WeasyPrint](https://img.shields.io/badge/WeasyPrint-62.3-F59C00?style=flat-square)](https://weasyprint.org)

</div>

---

## ¿Qué es Misionales?

Misionales es una plataforma web interna desarrollada para **Antioqueña de Incubación S.A.S.** que digitaliza y centraliza el proceso de inspección pre-operacional de vehículos de conductores misionales.

Antes de cada desplazamiento, el conductor registra el estado de su vehículo (moto, carro o camión), firma digitalmente y el sistema genera el PDF oficial de manera automática — sin papel, sin traslado físico de documentos, sin pérdida de registros.

El equipo SST accede al panel de administración para supervisar inspecciones en tiempo real, consultar historial, gestionar conductores y descargar reportes consolidados.

---

## Características

### Para el conductor
- Formulario adaptado al tipo de vehículo: **Moto** (13 aspectos), **Automóvil** (15 aspectos), **Camión** (20 aspectos)
- Selección de ruta con sugerencias inteligentes + escritura libre
- **Firma digital** en canvas — funciona en móvil y escritorio
- Descarga inmediata del PDF oficial al enviar
- Historial personal de inspecciones con descarga individual
- Reportes consolidados de 15 inspecciones generados automáticamente

### Para el administrador
- **Dashboard** con KPIs en tiempo real y gráficas comparativas por mes
- Vista global de inspecciones con filtros por conductor, placa, tipo y fecha
- Modal de detalle por inspección con todos los aspectos revisados
- Gestión completa de usuarios (crear, editar, suspender, reactivar)
- Log de auditoría de todas las acciones administrativas

### Seguridad
- Autenticación con usuario + PIN hasheado con **bcrypt**
- Tokens JWT almacenados en cookie `httpOnly` + soporte Bearer header
- Rate limiting: máximo 5 intentos fallidos por IP cada 5 minutos
- Aislamiento de datos: cada conductor solo accede a sus propios registros
- Rutas admin protegidas — conductores no pueden acceder al panel

---

## Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| Backend | FastAPI 0.110 · Python 3.11.9 · SQLAlchemy 2.0 |
| Base de datos | MySQL 8.0 / 5.7 · PyMySQL |
| PDFs | WeasyPrint 62.3 · Jinja2 · Futura (tipografía) |
| Frontend | HTML5 · CSS3 · JavaScript vanilla · Chart.js 4 |
| Auth | JWT · bcrypt · rate limiting por IP |
| Deploy | Uvicorn · systemd · Ubuntu 22.04/24.04 |

---

## Instalación local

### Requisitos previos

| Requisito | Versión | Notas |
|-----------|---------|-------|
| Python | **3.11.9 exacta** | [Descargar](https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe) |
| MySQL | 8.0 o 5.7 | — |
| GTK3 Runtime | última | Solo Windows — requerido por WeasyPrint · [Descargar](https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases) |
| Git | cualquiera | — |

> ⚠️ **Windows:** instalar GTK3 y **reiniciar el equipo** antes de continuar.

---

### Paso a paso

**1. Clonar el repositorio**
```bash
git clone https://github.com/TU-USUARIO/misionales-fastapi.git
cd misionales-fastapi
```

**2. Crear y activar el entorno virtual**
```bash
python -m venv venv

# Windows PowerShell
venv\Scripts\activate

# Linux / Mac
source venv/bin/activate

# Verificar versión (debe ser 3.11.9)
python --version
```

**3. Instalar dependencias**
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**4. Configurar variables de entorno**
```bash
cp .env.example .env
```

Editar `.env` con los valores del entorno:
```env
# Base de datos
DB_HOST=localhost
DB_USER=tu_usuario_mysql
DB_PASSWORD=tu_password_seguro
DB_NAME=misionales_db

# Seguridad — generar clave única:
# python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=pega_aqui_la_clave_generada

# CORS
CORS_ORIGINS=http://localhost:8000

# Producción (false para desarrollo local)
HTTPS_ENABLED=false
REGISTER_ENABLED=false
DEBUG=false
```

**5. Crear la base de datos**
```sql
CREATE DATABASE misionales_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Las tablas se crean automáticamente al iniciar la aplicación por primera vez.

> Si `usuarios` ya existía de una instalación anterior:
> ```sql
> ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS activo INT NOT NULL DEFAULT 1;
> ```

**6. Crear el primer administrador**
```bash
python admin_cli.py
```

El CLI solicita nombre de usuario, nombre completo, PIN y confirmación.

**7. Iniciar el servidor**
```bash
# Desarrollo (con auto-reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Producción
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Abrir en el navegador:
- Aplicación: [http://localhost:8000](http://localhost:8000)
- Documentación API: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Deploy en producción (VPS Ubuntu)

### Dependencias del sistema
```bash
sudo apt install libcairo2 libpango-1.0-0 libpangocairo-1.0-0
```

### Variables de entorno en producción
```env
CORS_ORIGINS=http://IP_DEL_VPS:8000
HTTPS_ENABLED=true
DEBUG=false
```

### Servicio systemd

Crear `/etc/systemd/system/misionales.service`:
```ini
[Unit]
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
```

```bash
sudo systemctl enable misionales
sudo systemctl start misionales
sudo systemctl status misionales
```

---

## Estructura del proyecto

```
misionales-fastapi/
│
├── app/
│   ├── main.py                         # App principal, CORS, exception handlers
│   ├── database.py                     # Conexión SQLAlchemy + MySQL
│   ├── models.py                       # ORM: Usuario, Inspeccion, Reporte, Log
│   ├── security.py                     # JWT, bcrypt, rate limiting
│   │
│   ├── routes_auth.py                  # Login, logout, registro
│   ├── routes_inspecciones.py          # Submit, historial, PDFs
│   ├── routes_admin.py                 # Dashboard, usuarios, inspecciones, logs
│   │
│   ├── utils_pdf.py                    # Generación PDF con WeasyPrint
│   ├── admin_cli.py                    # CLI para crear usuarios
│   │
│   ├── templates/
│   │   ├── login.html
│   │   ├── form.html                   # Formulario Moto / Carro / Camión
│   │   ├── lista_inspecciones.html     # Historial del conductor
│   │   ├── pdf_template.html           # PDF individual (A4)
│   │   ├── pdf_template_multiple.html  # PDF consolidado 15 (A4 landscape)
│   │   └── admin/
│   │       ├── dashboard.html
│   │       ├── inspecciones.html
│   │       ├── usuarios.html
│   │       ├── usuario_form.html
│   │       └── logs.html
│   │
│   └── static/
│       ├── css/incubant-theme.css
│       ├── img/logotipo_01.png          # ⚠ nombre en minúscula obligatorio
│       └── fonts/                       # Futura (4 variantes)
│
├── data/                               # Generado automáticamente — no se sube a Git
│   ├── generated_pdfs/usuarios/{id}/
│   │   ├── inspecciones/               # PDFs individuales
│   │   └── reportes/                   # PDFs consolidados
│   └── firmas/usuarios/{id}/           # PNGs de firmas digitales
│
├── requirements.txt
├── .env.example
├── .gitignore
├── migration.sql                       # Script BD para primer deploy
├── check_fonts.sh                      # Verificador de fonts para WeasyPrint
└── README.md
```

---

## Flujo de una inspección

```
Conductor abre el formulario
        ↓
Selecciona tipo de vehículo (Moto / Carro / Camión)
        ↓
Completa los aspectos pre-operacionales (B / M)
        ↓
Firma digitalmente en canvas
        ↓
Envía → FastAPI genera PDF con WeasyPrint
        ↓
PDF descargado automáticamente en el navegador
        ↓
Inspección guardada en BD
        ↓
Al llegar a 15 inspecciones → PDF consolidado generado
        ↓
Historial disponible en "Mis inspecciones"
```

---

## Solución de problemas

| Síntoma | Causa probable | Solución |
|---------|---------------|----------|
| WeasyPrint no genera PDF (Windows) | GTK3 no instalado | Instalar GTK3 Runtime y reiniciar el equipo |
| `No module named 'cairo'` | GTK3 no detectado | Reinstalar GTK3 y verificar PATH |
| Logo no aparece en el PDF | Nombre de archivo incorrecto | El archivo debe llamarse `logotipo_01.png` en **minúscula** (Linux es sensible) |
| Error al conectar MySQL | Credenciales incorrectas | Verificar `DB_USER`, `DB_PASSWORD` y `DB_NAME` en `.env` |
| `Column activo doesn't exist` | Migración pendiente | Ejecutar `ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS activo INT NOT NULL DEFAULT 1;` |
| Sesión expira constantemente | `SECRET_KEY` cambia en cada restart | Definir `SECRET_KEY` fija en `.env` |

---

## Licencia y soporte

Desarrollado por **SanWeb de Incubant · Antioqueña de Incubación S.A.S.**  
Sistema propietario para gestión SST de conductores misionales.

Para soporte técnico contactar al equipo de desarrollo interno de Incubant.