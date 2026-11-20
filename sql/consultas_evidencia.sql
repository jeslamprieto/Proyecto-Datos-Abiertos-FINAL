/* ============================================================
   Consultas para sacar las evidencias en SSMS
   (se ejecutan después de sincronizar desde la página web)
   ============================================================ */
USE DatosAbiertosDB;
GO

-- Evidencia 1: cuántos registros tenemos guardados
SELECT COUNT(*) AS total_registros
FROM dbo.HurtosVehiculos;

-- Evidencia 2: los últimos registros que guardó la aplicación
SELECT TOP 20 id, id_api, departamento, municipio, fecha_hecho,
       tipo_hurto, genero, cantidad, fecha_captura
FROM dbo.HurtosVehiculos
ORDER BY id DESC;

-- Evidencia 3: prueba de que NO hay duplicados.
-- Si esta consulta no devuelve filas, ningún id_api está repetido.
SELECT id_api, COUNT(*) AS veces
FROM dbo.HurtosVehiculos
GROUP BY id_api
HAVING COUNT(*) > 1;

-- Evidencia 4: el mismo resumen que mostramos en la página web
SELECT tipo_hurto,
       COUNT(*)      AS registros,
       SUM(cantidad) AS vehiculos_hurtados
FROM dbo.HurtosVehiculos
GROUP BY tipo_hurto
ORDER BY vehiculos_hurtados DESC;

SELECT TOP 5 departamento,
       SUM(cantidad) AS vehiculos_hurtados
FROM dbo.HurtosVehiculos
GROUP BY departamento
ORDER BY vehiculos_hurtados DESC;

-- Evidencia 5: ver el JSON original de un registro
SELECT TOP 1 id_api, json_original
FROM dbo.HurtosVehiculos;

/* Si se necesita empezar de cero durante las pruebas (OJO: borra todo):
   TRUNCATE TABLE dbo.HurtosVehiculos;
*/
