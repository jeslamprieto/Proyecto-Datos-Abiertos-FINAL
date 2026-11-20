# probar_api.py
# Prueba rápida para comprobar que la API responde (sin tocar SQL Server).
# Ejecutar:  python probar_api.py
# La salida de este script sirve como "Evidencia de respuesta JSON".

import json

from api.api_client import APIClient

cliente = APIClient()
print("Consultando:", cliente.url)

datos = cliente.obtener_registros(limite=5)

print("Cantidad recibida:", len(datos))

if datos:
    print("\nCampos del primer registro:")
    for campo, valor in datos[0].items():
        print(f"  {campo:15} -> {valor}")

    print("\nPrimer registro completo (JSON):")
    print(json.dumps(datos[0], indent=2, ensure_ascii=False))
else:
    print("La API no devolvió registros")
