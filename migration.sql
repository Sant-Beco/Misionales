-- ═══════════════════════════════════════════════════════
--  MISIONALES · Incubant SST
--  Script de migración y setup de base de datos
--  Ejecutar UNA SOLA VEZ antes del primer deploy
-- ═══════════════════════════════════════════════════════
--
--  Uso:
--    mysql -u root -p < migration.sql
--  o dentro de MySQL:
--    source /ruta/al/migration.sql
-- ═══════════════════════════════════════════════════════


-- ── 1. CREAR BASE DE DATOS (si no existe) ─────────────
CREATE DATABASE IF NOT EXISTS misionales_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE misionales_db;


-- ── 2. CREAR USUARIO DE APLICACIÓN ────────────────────
--  Cambia 'TU_PASSWORD' por el mismo valor que pusiste en DB_PASSWORD del .env
--  Solo dar permisos sobre misionales_db, no sobre todo MySQL

CREATE USER IF NOT EXISTS 'user_misionales'@'localhost'
  IDENTIFIED BY 'RemisionHuevo248123';

GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, INDEX, ALTER
  ON misionales_db.*
  TO 'user_misionales'@'localhost';

FLUSH PRIVILEGES;


-- ── 3. TABLAS (SQLAlchemy las crea automáticamente al arrancar) ──
--  No hace falta crearlas manualmente, FastAPI + SQLAlchemy
--  ejecuta models.Base.metadata.create_all(bind=engine) al iniciar.
--
--  Las tablas que se crearán automáticamente son:
--    usuarios, inspecciones, reportes_inspeccion, logs_auditoria


-- ── 4. MIGRACIÓN CRÍTICA: columna 'activo' ─────────────
--  Si la tabla usuarios YA EXISTE de una instalación anterior,
--  agregar la columna activo (los nuevos deployments la crean automáticamente)

ALTER TABLE usuarios
  ADD COLUMN IF NOT EXISTS activo INT NOT NULL DEFAULT 1
  COMMENT '1=activo, 0=suspendido';

-- Activar todos los usuarios existentes (por si acaso)
UPDATE usuarios SET activo = 1 WHERE activo IS NULL;


-- ── 5. VERIFICACIÓN FINAL ──────────────────────────────
SELECT 'Verificación de tablas:' AS info;

SELECT
  table_name AS tabla,
  table_rows AS filas_aprox,
  ROUND(data_length / 1024, 1) AS kb_datos
FROM information_schema.tables
WHERE table_schema = 'misionales_db'
ORDER BY table_name;

SELECT 'Columna activo en usuarios:' AS info;

SELECT column_name, column_type, column_default, is_nullable
FROM information_schema.columns
WHERE table_schema = 'misionales_db'
  AND table_name = 'usuarios'
  AND column_name = 'activo';

SELECT '✅ Migración completada. Listo para el primer arranque.' AS resultado;