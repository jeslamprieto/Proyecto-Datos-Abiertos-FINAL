# api/api_client.py
# ---------------------------------------------------------------
# Cliente de la API de datos abiertos (datos.gov.co).
#
# Este archivo NO es parte del Modelo ni del Controlador: es un
# "servicio" que solo se encarga de hablar con la API externa.
# Así el modelo se dedica únicamente a SQL Server, como dice la guía.
#
# Dataset: Hurto de automotores y motocicletas - Policía Nacional
# Endpoint: https://www.datos.gov.co/resource/9vha-vh9n.json
# ---------------------------------------------------------------

import os

import requests
from dotenv import load_dotenv

load_dotenv()


class APIClient:
    """Se encarga de pedirle los datos a la API de Socrata (SODA)."""

    def __init__(self):
        # Leemos el id del recurso desde el .env. Si no está, usamos
        # el de nuestro dataset para que el proyecto funcione igual.
        recurso = os.getenv("API_RESOURCE_ID", "9vha-vh9n")
        self.url = f"https://www.datos.gov.co/resource/{recurso}.json"

        # El token de aplicación es OPCIONAL. Sin token la API funciona,
        # pero puede limitar las peticiones (error HTTP 429).
        self.token = os.getenv("API_APP_TOKEN", "").strip()

    def obtener_registros(self, limite=100, desde=0):
        """
        Pide 'limite' registros a la API empezando en la posición 'desde'.
        Devuelve una lista de diccionarios (cada diccionario es un registro).
        """
        # Parámetros de la consulta SODA:
        #   $select=:*, *  -> trae los campos normales y además los campos
        #                     de sistema como ":id", que usamos como
        #                     identificador único de cada registro.
        #   $order=:id     -> ordena siempre igual, así el mismo "desde"
        #                     devuelve los mismos registros cada vez.
        #   $limit/$offset -> cuántos traer y desde dónde (paginación).
        parametros = {
            "$select": ":*, *",
            "$order": ":id",
            "$limit": limite,
            "$offset": desde,
        }

        encabezados = {}
        if self.token:
            encabezados["X-App-Token"] = self.token

        respuesta = requests.get(
            self.url,
            params=parametros,
            headers=encabezados,
            timeout=20,  # para que no se quede esperando para siempre
        )

        # Plan B: si la API no acepta $select con campos de sistema
        # (responde 400), repetimos la petición solo con límite y offset.
        # En ese caso el modelo genera una clave alternativa (ver
        # generar_id_api en datos_model.py).
        if respuesta.status_code == 400:
            respuesta = requests.get(
                self.url,
                params={"$limit": limite, "$offset": desde},
                headers=encabezados,
                timeout=20,
            )

        # Si la respuesta es un error (404, 429, 500...), esto lanza
        # una excepción que después atrapa el controlador.
        respuesta.raise_for_status()

        datos = respuesta.json()

        # Validación básica: la API siempre debería devolver una lista.
        if not isinstance(datos, list):
            raise ValueError("La API no devolvió una lista de registros.")

        return datos
