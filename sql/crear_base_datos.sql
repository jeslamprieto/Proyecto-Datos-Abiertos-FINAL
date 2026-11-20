/* ============================================================
   Proyecto: Sistema Web de Consulta y Análisis de Datos Abiertos
   Dataset:  Hurto de automotores y motocicletas (datos.gov.co)
   Recurso:  9vha-vh9n
   Archivo:  crear_base_datos.sql

   Este script crea la base de datos y la tabla donde guardamos
   los registros que nos devuelve la API. Se ejecuta UNA sola vez
   desde SQL Server Management Studio (SSMS) con F5.
   ============================================================ */

-- 1. Creamos la base de datos solo si no existe todavía
--    (así el script se puede volver a correr sin que salga error)
IF DB_ID('DatosAbiertosDB') IS NULL
    CREATE DATABASE DatosAbiertosDB;
GO

USE DatosAbiertosDB;
GO

-- 2. Tabla principal.
--    Las columnas salen de los campos reales del JSON de la API:
--    departamento, municipio, codigo_dane, armas_medios, fecha_hecho,
--    genero, grupo_etario, tipo_de_hurto y cantidad.
IF OBJECT_ID('dbo.HurtosVehiculos', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.HurtosVehiculos (
        -- Llave interna de nuestra tabla (la genera SQL Server)
        id              INT IDENTITY(1,1) PRIMARY KEY,

        -- Identificador del registro en la fuente. La API de Socrata lo
        -- entrega en el campo de sistema ":id". Lo dejamos UNIQUE para
        -- que nunca se guarde dos veces el mismo registro.
        id_api          NVARCHAR(100)  NOT NULL UNIQUE,

        departamento    NVARCHAR(100)  NULL,
        municipio       NVARCHAR(150)  NULL,

        -- El código DANE lo guardamos como texto y no como número
        -- porque empieza con cero en varios departamentos (ej: 08001000)
        -- y si fuera INT se perdería ese cero.
        codigo_dane     NVARCHAR(10)   NULL,

        armas_medios    NVARCHAR(100)  NULL,

        -- La API manda la fecha como texto "dd/mm/aaaa". En Python la
        -- convertimos a fecha antes de insertarla, así podemos ordenar
        -- y filtrar por fecha sin problemas.
        fecha_hecho     DATE           NULL,

        genero          NVARCHAR(30)   NULL,
        grupo_etario    NVARCHAR(30)   NULL,

        -- En el JSON se llama "tipo_de_hurto". Ejemplo de valor:
        -- "ARTÍCULO 239. HURTO MOTOCICLETAS"
        tipo_hurto      NVARCHAR(150)  NULL,

        -- Número de vehículos hurtados en ese registro
        cantidad        INT            NULL,

        -- Guardamos el JSON completo por si después necesitamos un campo
        -- que no modelamos como columna (recomendación de la guía)
        json_original   NVARCHAR(MAX)  NULL,

        -- Fecha y hora en que nuestra aplicación guardó el registro
        fecha_captura   DATETIME2      NOT NULL DEFAULT SYSDATETIME()
    );
END
GO

-- 3. Índices sencillos para que las búsquedas por departamento,
--    municipio y tipo de hurto respondan más rápido cuando haya
--    bastantes filas. No son obligatorios, pero no estorban.
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Hurtos_Departamento')
    CREATE INDEX IX_Hurtos_Departamento ON dbo.HurtosVehiculos (departamento, municipio);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Hurtos_Tipo')
    CREATE INDEX IX_Hurtos_Tipo ON dbo.HurtosVehiculos (tipo_hurto);
GO

-- 4. Comprobación rápida: debe mostrar la tabla vacía con sus columnas
SELECT TOP 5 * FROM dbo.HurtosVehiculos;
GO
