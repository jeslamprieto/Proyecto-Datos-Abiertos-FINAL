# probar_conexion.py
# Prueba rápida para comprobar que Python se conecta a SQL Server.
# Ejecutar:  python probar_conexion.py
# Antes hay que haber corrido sql/crear_base_datos.sql en SSMS.

from models.datos_model import contar_registros, obtener_conexion

try:
    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute("SELECT @@VERSION")
    version = cursor.fetchone()[0]
    print("Conexión exitosa a SQL Server")
    print(version.splitlines()[0])

    cursor.close()
    conexion.close()

    print("Registros en la tabla HurtosVehiculos:", contar_registros())

except Exception as error:
    print("No se pudo conectar:")
    print(error)
    print("\nRevisar: servicio de SQL Server encendido, DB_SERVER y DB_DRIVER en el .env,")
    print("y que la base DatosAbiertosDB y la tabla existan.")
