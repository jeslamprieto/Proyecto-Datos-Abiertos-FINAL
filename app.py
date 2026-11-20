# app.py
# ---------------------------------------------------------------
# CONTROLADOR (la "C" de MVC) y punto de entrada de la aplicación.
#
# Las rutas de Flask reciben lo que pide el navegador, deciden qué hacer,
# llaman al cliente de la API o al modelo y escogen qué plantilla mostrar.
# Aquí NO hay SQL ni HTML: eso le toca al modelo y a la vista.
#
# Para ejecutar:  python app.py   y abrir http://127.0.0.1:5000
# ---------------------------------------------------------------

import os

import requests
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for

from api.api_client import APIClient
from models.datos_model import (
    consultar_registros,
    contar_registros,
    guardar_registros,
    obtener_resumen,
    obtener_valores_distintos,
)

load_dotenv()

app = Flask(__name__)

# La clave secreta la necesita Flask para los mensajes flash.
# Se lee del .env para no dejarla escrita en el código.
app.secret_key = os.getenv("FLASK_SECRET_KEY", "clave-local-de-desarrollo")

# Cantidades que dejamos escoger en el formulario de sincronización.
# Las limitamos para no saturar la API (y para no esperar tanto).
CANTIDADES_PERMITIDAS = [50, 100, 500, 1000]


# Filtros de Jinja: pequeñas funciones de formato que usa la vista.
# Solo cambian cómo se ve un dato, no consultan nada.
@app.template_filter("fecha")
def formato_fecha(valor):
    """Muestra una fecha como dd/mm/aaaa (como se acostumbra en Colombia)."""
    if hasattr(valor, "strftime"):
        return valor.strftime("%d/%m/%Y")
    # A veces el driver devuelve la fecha como texto "aaaa-mm-dd"
    if isinstance(valor, str) and len(valor) >= 10 and valor[4] == "-":
        return f"{valor[8:10]}/{valor[5:7]}/{valor[0:4]}"
    return valor or "—"


@app.template_filter("miles")
def formato_miles(valor):
    """1234567 -> 1.234.567 (punto como separador de miles)."""
    try:
        return f"{int(valor):,}".replace(",", ".")
    except (TypeError, ValueError):
        return valor


@app.route("/", methods=["GET"])
def inicio():
    """Página principal: muestra los registros guardados, filtros y resumen."""
    # 1. Leemos los filtros que vienen en la URL (?q=...&tipo=...&genero=...)
    filtros = {
        "texto": request.args.get("q", "").strip(),
        "tipo": request.args.get("tipo", "").strip(),
        "genero": request.args.get("genero", "").strip(),
    }

    # 2. Le pedimos al modelo los datos que necesita la vista
    try:
        registros = consultar_registros(**filtros)
        resumen = obtener_resumen(**filtros)
        tipos = obtener_valores_distintos("tipo_hurto")
        generos = obtener_valores_distintos("genero")
        total_general = contar_registros()
        error_bd = None
    except Exception as error:
        # Si SQL Server está apagado o el .env está mal, mostramos la página
        # igual pero con un aviso, en vez de que salga el error feo de Flask.
        registros, resumen, tipos, generos, total_general = [], None, [], [], 0
        error_bd = str(error)

    # 3. Le pasamos todo a la vista (templates/index.html)
    return render_template(
        "index.html",
        registros=registros,
        resumen=resumen,
        tipos=tipos,
        generos=generos,
        total_general=total_general,
        filtros=filtros,
        cantidades=CANTIDADES_PERMITIDAS,
        error_bd=error_bd,
    )


@app.route("/sincronizar", methods=["POST"])
def sincronizar():
    """Consulta la API y guarda en SQL Server los registros nuevos."""
    # Leemos y validamos lo que mandó el formulario
    try:
        cantidad = int(request.form.get("cantidad", 100))
        desde = int(request.form.get("desde", 0))
    except ValueError:
        flash("La cantidad y la posición deben ser números.", "error")
        return redirect(url_for("inicio"))

    if cantidad not in CANTIDADES_PERMITIDAS:
        cantidad = 100
    if desde < 0:
        desde = 0

    try:
        # 1. El cliente de la API trae los datos en JSON
        cliente = APIClient()
        datos = cliente.obtener_registros(limite=cantidad, desde=desde)

        if not datos:
            flash("La API no devolvió registros desde esa posición.", "info")
            return redirect(url_for("inicio"))

        # 2. El modelo los guarda en SQL Server (sin duplicar)
        resultado = guardar_registros(datos)

        flash(
            f"Sincronización terminada. Recibidos de la API: {resultado['recibidos']} · "
            f"Nuevos guardados: {resultado['nuevos']} · "
            f"Ya existían (no se duplicaron): {resultado['repetidos']}",
            "success",
        )

    # Separamos los errores de la API de los de la base de datos para que
    # el mensaje le diga al usuario dónde está el problema.
    except requests.exceptions.Timeout:
        flash("La API se demoró demasiado en responder. Intenta de nuevo.", "error")
    except requests.exceptions.HTTPError as error:
        flash(f"La API respondió con un error HTTP: {error}", "error")
    except requests.exceptions.RequestException as error:
        flash(f"No hubo conexión con la API (revisa el Internet): {error}", "error")
    except Exception as error:
        flash(f"No fue posible guardar los datos en SQL Server: {error}", "error")

    # Volvemos a la página principal (patrón Post/Redirect/Get, así al
    # recargar la página no se vuelve a enviar el formulario)
    return redirect(url_for("inicio"))


if __name__ == "__main__":
    # debug=True solo mientras desarrollamos en nuestro computador
    app.run(debug=True)
