# models/datos_model.py
# ---------------------------------------------------------------
# MODELO (la "M" de MVC)
#
# Aquí está todo lo que tiene que ver con SQL Server:
#   - abrir la conexión con pyodbc
#   - guardar los registros que llegan de la API (sin duplicar)
#   - hacer los SELECT que necesita la página (tabla, filtros y resumen)
#
# El modelo NO arma páginas web ni sabe nada de Flask. Solo recibe
# datos, habla con la base de datos y devuelve listas/diccionarios.
# ---------------------------------------------------------------

import hashlib
import json
import os
from datetime import datetime

import pyodbc
from dotenv import load_dotenv

load_dotenv()

# Nombre de la tabla en un solo lugar, por si toca cambiarlo
TABLA = "dbo.HurtosVehiculos"

# Columnas que se pueden usar para llenar las listas desplegables.
# Se usa una "lista blanca" porque el nombre de una columna no se puede
# pasar como parámetro (?) y no queremos meter texto del usuario en el SQL.
COLUMNAS_PERMITIDAS = ("tipo_hurto", "genero", "departamento", "grupo_etario")


# ===============================================================
# 1. CONEXIÓN
# ===============================================================

def obtener_conexion():
    """Abre y devuelve una conexión a SQL Server usando los datos del .env."""
    servidor = os.getenv("DB_SERVER", "localhost")
    base_datos = os.getenv("DB_NAME", "DatosAbiertosDB")
    driver = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server")
    trusted = os.getenv("DB_TRUSTED", "yes").lower() == "yes"

    if trusted:
        # Autenticación de Windows (la que usamos en los PC del equipo)
        cadena = (
            f"DRIVER={{{driver}}};"
            f"SERVER={servidor};"
            f"DATABASE={base_datos};"
            "Trusted_Connection=yes;"
            "TrustServerCertificate=yes;"
        )
    else:
        # Autenticación de SQL Server (usuario y contraseña)
        usuario = os.getenv("DB_USER")
        clave = os.getenv("DB_PASSWORD")
        cadena = (
            f"DRIVER={{{driver}}};"
            f"SERVER={servidor};"
            f"DATABASE={base_datos};"
            f"UID={usuario};PWD={clave};"
            "TrustServerCertificate=yes;"
        )

    # TrustServerCertificate=yes sirve para practicar en local.
    # En un servidor real habría que configurar bien el certificado.
    return pyodbc.connect(cadena)


# ===============================================================
# 2. FUNCIONES DE APOYO PARA LIMPIAR LOS DATOS DE LA API
# ===============================================================

def convertir_fecha(texto):
    """
    La API manda la fecha como texto, por ejemplo "05/03/2014" (día/mes/año).
    La convertimos a un objeto date para guardarla en la columna DATE.
    Si viene vacía o con un formato raro, devolvemos None (queda NULL).
    """
    if not texto:
        return None

    # Probamos el formato que vimos en el JSON y, por si acaso, el formato
    # ISO que usan otros datasets de Socrata.
    formatos = ("%d/%m/%Y", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d")
    for formato in formatos:
        try:
            return datetime.strptime(texto.strip(), formato).date()
        except ValueError:
            continue
    return None


def convertir_entero(texto):
    """La cantidad llega como texto ("1"). La pasamos a int; si falla, None."""
    try:
        return int(float(texto))
    except (TypeError, ValueError):
        return None


def generar_id_api(registro):
    """
    Devuelve el identificador único del registro.

    Este dataset NO trae un campo "id" propio. Por eso le pedimos a la API
    el campo de sistema ":id" (ver api_client.py), que es único y estable.

    Si por alguna razón no llega, armamos una clave alternativa: un hash
    SHA-1 de todo el registro. OJO: con esa clave dos registros con
    exactamente los mismos datos quedarían como uno solo (lo explicamos
    en el README como limitación).
    """
    if registro.get(":id"):
        return str(registro[":id"])

    texto = json.dumps(registro, sort_keys=True, ensure_ascii=False)
    return "hash-" + hashlib.sha1(texto.encode("utf-8")).hexdigest()


# ===============================================================
# 3. GUARDAR (carga / sincronización desde la API)
# ===============================================================

def guardar_registros(registros):
    """
    Recorre la lista que devolvió la API y guarda en SQL Server solo los
    registros que todavía no existen (se comparan por id_api).

    Devuelve un diccionario con cuántos fueron nuevos y cuántos ya estaban,
    para mostrarle ese mensaje al usuario.
    """
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    nuevos = 0
    repetidos = 0

    try:
        for registro in registros:
            id_api = generar_id_api(registro)

            # Paso 1: ¿ya existe este registro en la tabla?
            cursor.execute(
                f"SELECT 1 FROM {TABLA} WHERE id_api = ?",
                id_api,
            )
            if cursor.fetchone():
                repetidos += 1
                continue

            # Paso 2: si no existe, lo insertamos.
            # Usamos ? (parámetros) en vez de concatenar texto, así se evita
            # la inyección SQL aunque los datos vengan de afuera.
            cursor.execute(
                f"""
                INSERT INTO {TABLA}
                    (id_api, departamento, municipio, codigo_dane,
                     armas_medios, fecha_hecho, genero, grupo_etario,
                     tipo_hurto, cantidad, json_original)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                id_api,
                registro.get("departamento"),
                registro.get("municipio"),
                registro.get("codigo_dane"),
                registro.get("armas_medios"),
                convertir_fecha(registro.get("fecha_hecho")),
                registro.get("genero"),
                registro.get("grupo_etario"),
                registro.get("tipo_de_hurto"),  # en el JSON tiene otro nombre
                convertir_entero(registro.get("cantidad")),
                json.dumps(registro, ensure_ascii=False),
            )
            nuevos += 1

        # Si todo salió bien, confirmamos los cambios
        conexion.commit()
        return {"recibidos": len(registros), "nuevos": nuevos, "repetidos": repetidos}

    except Exception:
        # Si algo falla, deshacemos todo lo de esta sincronización
        conexion.rollback()
        raise

    finally:
        # Esto se ejecuta siempre, haya error o no
        cursor.close()
        conexion.close()


# ===============================================================
# 4. CONSULTAR (lo que muestra la página web)
# ===============================================================

def _armar_filtros(texto="", tipo="", genero=""):
    """
    Arma la parte WHERE de la consulta según los filtros que llenó el
    usuario. Devuelve el texto del WHERE y la lista de parámetros.
    La usamos tanto para la tabla como para el resumen, así los dos
    muestran exactamente lo mismo.
    """
    condiciones = []
    parametros = []

    if texto:
        # COLLATE ..._CI_AI hace que no importen mayúsculas ni tildes:
        # "bogota" encuentra "Bogotá D.C." y "medellin" encuentra "Medellín".
        condiciones.append(
            "(departamento COLLATE Latin1_General_CI_AI LIKE ? "
            "OR municipio COLLATE Latin1_General_CI_AI LIKE ?)"
        )
        parametros.extend([f"%{texto}%", f"%{texto}%"])

    if tipo:
        condiciones.append("tipo_hurto = ?")
        parametros.append(tipo)

    if genero:
        condiciones.append("genero = ?")
        parametros.append(genero)

    where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
    return where, parametros


def _a_diccionarios(cursor):
    """Convierte las filas del cursor en una lista de diccionarios."""
    columnas = [columna[0] for columna in cursor.description]
    return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]


def consultar_registros(texto="", tipo="", genero="", limite=100):
    """Devuelve los registros guardados (máximo 'limite') según los filtros."""
    where, parametros = _armar_filtros(texto, tipo, genero)
    limite = int(limite)  # nos aseguramos de que sea un número

    conexion = obtener_conexion()
    cursor = conexion.cursor()
    try:
        cursor.execute(
            f"""
            SELECT TOP {limite}
                   id_api, departamento, municipio, codigo_dane,
                   fecha_hecho, tipo_hurto, armas_medios, genero,
                   grupo_etario, cantidad
            FROM {TABLA}
            {where}
            ORDER BY fecha_hecho DESC, id DESC
            """,
            *parametros,
        )
        return _a_diccionarios(cursor)
    finally:
        cursor.close()
        conexion.close()


def obtener_resumen(texto="", tipo="", genero=""):
    """
    Resumen numérico básico (lo pide la guía). Respeta los filtros, así que
    si el usuario busca "Antioquia" el resumen es solo de Antioquia.
    """
    where, parametros = _armar_filtros(texto, tipo, genero)

    conexion = obtener_conexion()
    cursor = conexion.cursor()
    try:
        # Totales generales
        cursor.execute(
            f"""
            SELECT COUNT(*)                   AS total_registros,
                   COALESCE(SUM(cantidad), 0) AS total_vehiculos,
                   MIN(fecha_hecho)           AS fecha_minima,
                   MAX(fecha_hecho)           AS fecha_maxima
            FROM {TABLA}
            {where}
            """,
            *parametros,
        )
        resumen = _a_diccionarios(cursor)[0]

        # Vehículos hurtados por tipo (motos vs automotores)
        cursor.execute(
            f"""
            SELECT tipo_hurto, SUM(cantidad) AS vehiculos
            FROM {TABLA}
            {where}
            GROUP BY tipo_hurto
            ORDER BY vehiculos DESC
            """,
            *parametros,
        )
        resumen["por_tipo"] = _a_diccionarios(cursor)

        # Los 5 departamentos con más vehículos hurtados
        cursor.execute(
            f"""
            SELECT TOP 5 departamento, SUM(cantidad) AS vehiculos
            FROM {TABLA}
            {where}
            GROUP BY departamento
            ORDER BY vehiculos DESC
            """,
            *parametros,
        )
        resumen["top_departamentos"] = _a_diccionarios(cursor)

        return resumen
    finally:
        cursor.close()
        conexion.close()


def obtener_valores_distintos(columna):
    """
    Devuelve los valores diferentes de una columna (por ejemplo, los tipos
    de hurto) para llenar las listas desplegables del formulario.
    """
    if columna not in COLUMNAS_PERMITIDAS:
        raise ValueError(f"Columna no permitida: {columna}")

    conexion = obtener_conexion()
    cursor = conexion.cursor()
    try:
        cursor.execute(
            f"""
            SELECT DISTINCT {columna}
            FROM {TABLA}
            WHERE {columna} IS NOT NULL
            ORDER BY {columna}
            """
        )
        return [fila[0] for fila in cursor.fetchall()]
    finally:
        cursor.close()
        conexion.close()


def contar_registros():
    """Cuántos registros hay en total en la tabla (sin filtros)."""
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {TABLA}")
        return cursor.fetchone()[0]
    finally:
        cursor.close()
        conexion.close()
