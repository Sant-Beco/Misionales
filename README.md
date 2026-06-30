<div align="center">
 
# Misionales · Sistema de Inspección Vehicular
 
**Herramienta SST para conductores misionales de Incubant**  
Inspecciones pre-operacionales digitales · Firma en canvas · PDFs automáticos · Panel de administración
 
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![MySQL](https://img.shields.io/badge/MySQL-8.0+-4479A1?style=flat-square&logo=mysql&logoColor=white)](https://mysql.com)
[![WeasyPrint](https://img.shields.io/badge/WeasyPrint-60+-F59C00?style=flat-square)](https://weasyprint.org)
[![License](https://img.shields.io/badge/License-Propietario-red?style=flat-square)](LICENSE)
 
</div>
 
---
 
## ¿Qué es Misionales?
 
Misionales es una plataforma web interna que digitaliza el proceso de inspección pre-operacional de vehículos para conductores misionales de **Antioqueña de Incubación S.A.S.**
 
Antes de cada desplazamiento, el conductor registra el estado de su vehículo (moto, carro o camión), firma digitalmente y el sistema genera el PDF oficial automáticamente — **sin papel, sin traslado físico de documentos, sin pérdida de registros.**
 
### Características principales
 
**Para el conductor:**
- Formulario adaptado al tipo de vehículo: **Moto** (13 aspectos), **Automóvil** (15 aspectos), **Camión** (50 aspectos)
- Firma digital en canvas — funciona en móvil y escritorio
- Descarga inmediata del PDF oficial al enviar
- Historial personal con descarga individual
- Reportes consolidados cada 15 inspecciones generados automáticamente
 
**Para el administrador:**
- Dashboard con KPIs en tiempo real
- Vista global de inspecciones con filtros
- Gestión de usuarios (crear, editar, suspender)
- Log de auditoría de todas las acciones
- Descarga de reportes consolidados
 
**Seguridad:**
- Autenticación con usuario + PIN hasheado con **bcrypt**
- Tokens JWT en cookie `httpOnly`
- Rate limiting: máx 5 intentos fallidos por IP cada 5 minutos
- Aislamiento de datos: cada conductor solo accede a sus registros
- Rutas admin protegidas
 
---
 
## 📋 Tabla de Contenidos
 
1. [Stack Tecnológico](#stack-tecnológico)
2. [Requisitos Previos](#requisitos-previos)
3. [Instalación Local](#instalación-local)
4. [Configuración](#configuración)
5. [Estructura del Proyecto](#estructura-del-proyecto)
6. [Flujo de Inspección](#flujo-de-una-inspección)
7. [API Endpoints](#api-endpoints)
8. [Deploy en Producción](#deploy-en-producción)
9. [Solución de Problemas](#solución-de-problemas)
10. [Sostenibilidad](#sostenibilidad)
11. [Historial de Cambios](#historial-de-cambios)
 
---
 
## 🔧 Stack Tecnológico
 
| Capa | Tecnología | Versión |
|------|-----------|---------|
| Backend | FastAPI | 0.110+ |
| Base de datos | MySQL / MariaDB | 8.0+ / 5.7+ |
| ORM | SQLAlchemy | 2.0+ |
| Autenticación | JWT + bcrypt | — |
| PDFs | WeasyPrint + Jinja2 | 60+ |
| Frontend | HTML5 + CSS3 + JS vanilla | — |
| Servidor | Uvicorn ASGI | — |
| Deploy | systemd + Ubuntu 22.04+ | — |
 
---
 
## 🖥️ Requisitos Previos
 
| Requisito | Versión | Notas |
|-----------|---------|-------|
| Python | **3.10+** | Recomendado 3.11.9 |
| MySQL | 8.0 o 5.7 | — |
| GTK3 Runtime | última | **Solo Windows** — requerido por WeasyPrint |
| Git | cualquiera | — |
| pip | 21+ | — |
 
### ⚠️ Nota importante para Windows
 
**Instalar GTK3 Runtime y reiniciar el equipo antes de continuar:**
1. Descargar desde [GitHub](https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases)
2. Ejecutar instalador
3. Reiniciar equipo
4. Continuar con instalación de dependencias Python
 
---
 
## 🚀 Instalación Local
 
### Paso 1: Clonar repositorio
```bash
git clone https://github.com/tu-usuario/misionales-incubant.git
cd misionales-incubant
```
 
### Paso 2: Crear entorno virtual
```bash
python -m venv venv
 
# Windows (PowerShell)
venv\Scripts\activate
 
# Linux / Mac
source venv/bin/activate
 
# Verificar versión
python --version
```
 
### Paso 3: Instalar dependencias
```bash
pip install --upgrade pip
pip install -r requirements.txt
```
 
### Paso 4: Configurar variables de entorno
```bash
cp .env.example .env
```
 
Editar `.env`:
```env
# Base de datos
DATABASE_URL=mysql+pymysql://root:password@localhost:3306/misionales_incubant
 
# Seguridad
SECRET_KEY=tu-clave-secreta-aleatorea-64-caracteres-aqui
ALGORITHM=HS256
DEFAULT_TOKEN_EXPIRATION_HOURS=24
 
# Server
DEBUG=True
HTTPS_ENABLED=False
ALLOWED_ORIGINS=http://localhost:8000
 
# Almacenamiento
PDF_OUTPUT_DIR=app/data/generated_pdfs
FIRMAS_OUTPUT_DIR=app/data/firmas
```
 
**Para generar SECRET_KEY:**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
 
### Paso 5: Crear base de datos
```bash
mysql -u root -p
> CREATE DATABASE misionales_incubant CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
> EXIT;
```
 
Las tablas se crean automáticamente al iniciar la aplicación.
 
### Paso 6: Crear primer usuario admin
```bash
python -c "from app.database import Base, engine; Base.metadata.create_all(bind=engine)"
```
 
Luego acceder a `/admin` en el navegador y crear usuario.
 
### Paso 7: Iniciar servidor
```bash
# Desarrollo (con auto-reload)
python main.py
# O: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
 
# Acceder a:
# - App: http://localhost:8000
# - Docs API: http://localhost:8000/docs
```
 
---
 
## ⚙️ Configuración
 
### Variables de Entorno Críticas
 
| Variable | Descripción | Desarrollo | Producción |
|----------|-------------|-----------|-----------|
| `SECRET_KEY` | Clave JWT | random | random (fija) |
| `DEBUG` | Modo depuración | True | False |
| `HTTPS_ENABLED` | Forzar HTTPS | False | True |
| `DEFAULT_TOKEN_EXPIRATION_HOURS` | Expiración token | 24 | 24 |
| `DATABASE_URL` | Conexión BD | localhost | IP remota |
 
---
 
## 📁 Estructura del Proyecto
 
```
misionales-incubant/
├── app/
│   ├── main.py                      # App principal, CORS, handlers
│   ├── database.py                  # SQLAlchemy + MySQL
│   ├── models.py                    # ORM: Usuario, Inspeccion, etc
│   ├── security.py                  # JWT, bcrypt, autenticación
│   ├── utils_pdf.py                 # WeasyPrint
│   │
│   ├── routes/
│   │   ├── auth.py                  # /login, /logout, /verify, /me
│   │   ├── inspecciones.py          # /submit, /mis-inspecciones, /detalle
│   │   └── admin.py                 # /admin, /admin/usuarios, /admin/logs
│   │
│   ├── templates/
│   │   ├── auth/login.html
│   │   ├── inspecciones/
│   │   │   ├── index.html           # Formulario
│   │   │   └── lista_inspecciones.html
│   │   ├── admin/
│   │   │   ├── dashboard.html
│   │   │   ├── inspecciones.html
│   │   │   ├── usuarios.html
│   │   │   └── logs.html
│   │   ├── pdf_template.html        # PDF individual
│   │   └── pdf_template_multiple.html # PDF consolidado
│   │
│   └── static/
│       ├── css/incubant-theme.css
│       ├── js/
│       │   ├── session-check.js     # Verificador sesión
│       │   └── form-validation.js
│       └── img/logotipo_01.png      # ⚠️ minúscula obligatoria
│
├── data/                            # Generado automáticamente (NO Git)
│   ├── generated_pdfs/usuarios/{id}/
│   │   ├── inspecciones/
│   │   └── reportes/
│   └── firmas/usuarios/{id}/
│
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```
 
---
 
## 🔄 Flujo de una Inspección
 
```
Conductor abre http://localhost:8000/
        ↓
Selecciona tipo de vehículo (Moto / Carro / Camión)
        ↓
Completa los 13-50 aspectos pre-operacionales (B / M)
        ↓
Ingresa datos del vehículo y documentos
        ↓
Firma digitalmente en canvas
        ↓
Envía → FastAPI valida 15 puntos críticos
        ↓
Backend genera PDF con WeasyPrint
        ↓
PDF descargado automáticamente
        ↓
Inspección guardada en BD + firma PNG en disco
        ↓
Conductor accede a /inspecciones/mis-inspecciones
        ↓
Visualiza historial (últimas 15) + modal con detalles
        ↓
Al completar 15 inspecciones → PDF consolidado generado automáticamente
        ↓
Contador reinicia: 0/15 (nuevo ciclo)
```
 
---
 
## 🛣️ API Endpoints
 
### Autenticación
 
```
GET  /login                 # Formulario login
POST /auth/login            # Autenticar con cédula + PIN
POST /auth/logout           # Cerrar sesión
GET  /auth/me               # Datos usuario actual
GET  /auth/verify           # Verificar token válido
```
 
### Inspecciones (Conductor)
 
```
GET  /                                      # Formulario
POST /inspecciones/submit                   # Enviar inspección
GET  /inspecciones/mis-inspecciones         # Historial (últimas 15)
GET  /inspecciones/mis-inspecciones?formato=json
GET  /inspecciones/detalle/{id}?formato=json
GET  /inspecciones/detalle/{id}?formato=pdf
GET  /inspecciones/reporte-consolidado/{id}  # Descargar consolidado
```
 
### Admin
 
```
GET  /admin                          # Dashboard
GET  /admin/inspecciones            # Todas las inspecciones
GET  /admin/usuarios                # Gestionar usuarios
POST /admin/usuarios                # Crear usuario
PUT  /admin/usuarios/{id}           # Editar usuario
GET  /admin/logs                    # Auditoria
```
 
---
 
## 🚀 Deploy en Producción
 
### Dependencias del sistema (Ubuntu 22.04)
 
```bash
sudo apt update
sudo apt install -y python3.10 python3-pip mysql-server git nginx
sudo apt install -y libcairo2 libpango-1.0-0 libpangocairo-1.0-0
```
 
### Configuración systemd
 
Crear `/etc/systemd/system/misionales.service`:
 
```ini
[Unit]
Description=Misionales Incubant
After=network.target
 
[Service]
Type=notify
User=www-data
WorkingDirectory=/home/app/misionales
Environment="PATH=/home/app/misionales/venv/bin"
ExecStart=/home/app/misionales/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10
 
[Install]
WantedBy=multi-user.target
```
 
```bash
sudo systemctl enable misionales
sudo systemctl start misionales
sudo systemctl status misionales
```
 
### Nginx como proxy
 
```nginx
server {
    listen 80;
    server_name tu-dominio.com;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
 
### SSL con Let's Encrypt
 
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot certonly --nginx -d tu-dominio.com
```
 
---
 
## 🐛 Solución de Problemas
 
| Síntoma | Causa | Solución |
|---------|-------|----------|
| **WeasyPrint falla (Windows)** | GTK3 no instalado | Instalar GTK3 Runtime y reiniciar |
| **`No module named 'cairo'`** | GTK3 no detectado | Reinstalar GTK3, verificar PATH |
| **Logo no aparece en PDF** | Nombre incorrecto | Archivo debe llamarse `logotipo_01.png` (minúscula) |
| **Error conectar MySQL** | Credenciales inválidas | Verificar `DATABASE_URL` en `.env` |
| **Contador 15 muestra 90** | Versión vieja | Actualizar a v2.1 |
| **"Error cargando detalle"** | Falta `credentials: "include"` | Ya está arreglado en v2.1 |
| **Sesión expira constantemente** | `SECRET_KEY` cambia en restart | Definir `SECRET_KEY` fija en `.env` |
| **Base de datos lenta (1000+ registros)** | Faltan índices | Ejecutar: `ALTER TABLE inspecciones ADD INDEX idx_usuario_fecha (usuario_id, fecha DESC);` |
 
---
 
## 📈 Sostenibilidad
 
### Crecimiento de Datos Estimado
 
**100 conductores × 5 años:**
- Inspecciones en BD: ~90,000 registros
- PDFs individuales: ~27 GB
- Firmas PNG: ~6.75 GB
- PDFs consolidados: ~9 GB
- **Total disco: ~45 GB** ✅ Sostenible en VPS con SSD 100GB
 
### Recomendaciones por Período
 
**Inmediato (0-6 meses):**
- ✅ Mostrar solo últimas 15 inspecciones
- ✅ Contador correcto (0-15)
- ✅ No borrar inspecciones (auditoría)
 
**Corto plazo (6-12 meses):**
- Agregar índices en BD
- Paginación en historial consolidados
- Búsqueda en historial completo
 
**Mediano plazo (1-2 años):**
- Archivado automático (>2 años → tabla archivo)
- Comprimir firmas antiguas
- Resultado: 87 GB → 30 GB
 
**Largo plazo (2+ años):**
- Exportar a AWS S3 o Google Cloud Storage
- Mantener últimas 15 en disco rápido
- Acceso a histórico con latencia
 
Ver [SOSTENIBILIDAD_Y_RECOMENDACIONES.md](./SOSTENIBILIDAD_Y_RECOMENDACIONES.md) para detalles.
 
---
 
## 📝 Historial de Cambios
 
### v2.1 (2026-06-29) ✅ Actual
- **Correcciones por Sostenibilidad**
  - Limitar `/mis-inspecciones` a últimas 15 registros
  - Arreglar contador de consolidado (0-15)
  - Comentar borrado automático de inspecciones
  - Documentación completa de sostenibilidad
 
### v2.0 (2026-06-28)
- Integración completa RBAC + PDFs
- Admin: usuarios, logs, inspecciones
- PDF consolidado cada 15 inspecciones
- session-check.js mejorado
 
### v1.5 (2026-06-25)
- Migrar a httpOnly cookies
- Endpoints retornan JSON para AJAX
- `/auth/me` para verificar sesión
 
### v1.0 (2026-05-25)
- MVP funcional
- Autenticación básica
- Formulario inspección
- PDF individual
 
---
 
## 📚 Documentación Adicional
 
- [README.md](./README.md) — Documentación técnica completa
- [INDICE_ARCHIVOS_FINALES.md](./INDICE_ARCHIVOS_FINALES.md) — Guía de aplicación
- [SOSTENIBILIDAD_Y_RECOMENDACIONES.md](./SOSTENIBILIDAD_Y_RECOMENDACIONES.md) — Plan de mantenimiento
 
---
 
## 🤝 Equipo de Desarrollo
 
Desarrollado por **SanWeb de Incubant**  
**Antioqueña de Incubación S.A.S.**
 
---
 
## 📄 Licencia
 
Sistema propietario para gestión SST de conductores misionales.
 
---
 
## 📞 Soporte
 
Para soporte técnico, contactar al equipo de desarrollo interno de Incubant.
 
---
 
**Última actualización:** 2026-06-29  
**Versión actual:** v2.1  
**Estado:** ✅ Estable y Sostenible