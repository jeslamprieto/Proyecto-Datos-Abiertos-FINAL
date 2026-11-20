# Sistema Web de Consulta y Análisis de Datos Abiertos de Colombia
### Hurtos de automotores y motocicletas

**Asignatura:** Desarrollo de Aplicaciones con Acceso a Datos
**Programa:** Ingeniería de Sistemas · 4.° semestre
**Integrantes:**
- Integrante 1 (API y datos): _Nombre Apellido_
- Integrante 2 (SQL Server y Modelo): _Nombre Apellido_
- Integrante 3 (Controlador y Vista): _Nombre Apellido_

---

## 1. Objetivo

Construir una aplicación web pequeña que consulte un conjunto de datos abiertos de Colombia por medio de una API REST, guarde esos registros en SQL Server y permita consultarlos desde el navegador, organizando el código con el patrón **Modelo–Vista–Controlador (MVC)**.

Escogimos el tema de **hurto de vehículos** porque es un problema que se ve mucho en las noticias y en nuestras ciudades, y nos pareció interesante poder responder preguntas sencillas con datos reales, por ejemplo: *¿se roban más motos o más carros?* o *¿qué departamentos tienen más casos?*

> Como dice la guía, el proyecto **no** es un CRUD. Solo hacemos tres cosas: **consumir** la API, **almacenar** los registros y **consultar** lo que se guardó.

---

## 2. Conjunto de datos elegido

| Dato | Valor |
|---|---|
| Nombre | Hurto de automotores y motocicletas |
| Publicado en | datos.gov.co (Portal de Datos Abiertos de Colombia) |
| Entidad que reporta | Policía Nacional de Colombia |
| Identificador del recurso | `9vha-vh9n` |
| Ficha del dataset | https://www.datos.gov.co/d/9vha-vh9n |
| Endpoint (API SODA) | https://www.datos.gov.co/resource/9vha-vh9n.json |
| Formato de respuesta | JSON (lista de objetos) |

**Propósito:** cada registro es un hecho de hurto de un automotor o de una motocicleta, con el lugar (departamento y municipio), la fecha, el tipo de hurto y algunos datos de la víctima (género y grupo de edad).

### 2.1 Campos del JSON y cómo los usamos

Revisamos el JSON real que devuelve la API. Un registro se ve así:

```json
{
  "departamento": "ATLÁNTICO",
  "municipio": "Barranquilla (CT)",
  "codigo_dane": "08001000",
  "armas_medios": "NO REPORTADO",
  "fecha_hecho": "05/03/2014",
  "genero": "FEMENINO",
  "grupo_etario": "ADULTOS",
  "tipo_de_hurto": "ARTÍCULO 239. HURTO AUTOMOTORES",
  "cantidad": "1"
}
```

| Campo en la API | Columna en SQL Server | Tipo | Qué significa | ¿Se muestra? |
|---|---|---|---|---|
| `:id` (campo de sistema) | `id_api` | NVARCHAR(100) UNIQUE | Identificador único del registro en la fuente | No (solo interno) |
| `departamento` | `departamento` | NVARCHAR(100) | Departamento donde ocurrió el hurto | Sí + filtro |
| `municipio` | `municipio` | NVARCHAR(150) | Municipio. "(CT)" quiere decir que es la capital | Sí + filtro |
| `codigo_dane` | `codigo_dane` | NVARCHAR(10) | Código DANE del municipio | No |
| `armas_medios` | `armas_medios` | NVARCHAR(100) | Arma o medio usado en el hurto | Sí |
| `fecha_hecho` | `fecha_hecho` | DATE | Fecha en que pasó el hecho | Sí |
| `genero` | `genero` | NVARCHAR(30) | Género de la víctima | Sí + filtro |
| `grupo_etario` | `grupo_etario` | NVARCHAR(30) | Grupo de edad (adultos, adolescentes, menores) | Sí |
| `tipo_de_hurto` | `tipo_hurto` | NVARCHAR(150) | Motocicleta o automotor (Art. 239 del Código Penal) | Sí + filtro |
| `cantidad` | `cantidad` | INT | Número de vehículos hurtados en el registro | Sí (y se suma en el resumen) |
| (todo el registro) | `json_original` | NVARCHAR(MAX) | El JSON completo, por si después necesitamos otro campo | No |

### 2.2 Decisiones que tomamos con los datos

1. **¿Qué usamos como identificador?** Este fue el problema más grande. El dataset **no trae un campo `id`**. Si usábamos, por ejemplo, municipio + fecha, dos hurtos distintos del mismo día en Medellín quedarían como uno solo. Investigando la documentación de Socrata (la plataforma de datos.gov.co) encontramos que cada fila tiene un **campo de sistema `:id`** que es único y no cambia. Para que la API lo devuelva se le agrega el parámetro `$select=:*, *`. Ese valor es el que guardamos en `id_api`, que tiene restricción `UNIQUE`.
   - **Plan B:** si por algún motivo la API no devuelve `:id`, el modelo calcula un hash SHA-1 de todo el registro y lo usa como clave (función `generar_id_api`). La limitación es que dos registros exactamente iguales quedarían como uno.
2. **Fecha:** la API manda la fecha como texto `dd/mm/aaaa`. La convertimos en Python a tipo fecha para guardarla en una columna `DATE`; así se puede ordenar y sacar el periodo (fecha mínima y máxima).
3. **Código DANE como texto:** algunos códigos empiezan con cero (`08001000`). Si lo guardábamos como número se perdía ese cero.
4. **Cantidad como entero:** llega como texto `"1"`, pero la pasamos a `INT` para poder usar `SUM()` en el resumen.
5. **Orden fijo con `$order=:id`:** así, si pedimos "100 registros desde la posición 0" dos veces, la API devuelve los mismos 100. Eso nos sirve para probar que no se duplican.

---

## 3. Tecnologías y requisitos

- Python 3.10 o superior
- Flask (servidor web y plantillas Jinja2)
- requests (peticiones HTTP a la API)
- pyodbc (conexión Python–SQL Server)
- python-dotenv (leer la configuración del archivo `.env`)
- Microsoft SQL Server + SQL Server Management Studio (SSMS)
- Microsoft ODBC Driver 18 for SQL Server
- Visual Studio Code y un navegador

---

## 4. Instalación (Windows)

**1. Crear la base de datos.** Abrir SSMS, conectarse al servidor, abrir el archivo `sql/crear_base_datos.sql` y ejecutarlo con **F5**. Crea la base `DatosAbiertosDB` y la tabla `HurtosVehiculos`.

**2. Crear el entorno virtual e instalar dependencias.** En una terminal dentro de la carpeta del proyecto:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> Si PowerShell no deja activar el entorno, ejecutar una vez:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

**3. Configurar el `.env`.** Copiar `.env.example` con el nombre `.env` y cambiar los valores:

```env
DB_SERVER=localhost          # o localhost\SQLEXPRESS si usan Express
DB_NAME=DatosAbiertosDB
DB_DRIVER=ODBC Driver 18 for SQL Server
DB_TRUSTED=yes               # yes = autenticación de Windows
DB_USER=
DB_PASSWORD=
API_RESOURCE_ID=9vha-vh9n
API_APP_TOKEN=               # opcional
FLASK_SECRET_KEY=una-clave-cualquiera
```

> El `.env` **no se entrega ni se sube a GitHub** (está en el `.gitignore`) porque puede tener contraseñas.

**4. Probar por partes (opcional pero recomendado):**

```powershell
python probar_api.py        # debe mostrar 5 registros del JSON
python probar_conexion.py   # debe decir "Conexión exitosa a SQL Server"
```

---

## 5. Ejecución

```powershell
python app.py
```

Abrir en el navegador: **http://127.0.0.1:5000**

En la página:
1. Escoger cuántos registros traer (50, 100, 500 o 1000) y desde qué posición, y pulsar **"Consultar API y guardar"**. Sale un mensaje con cuántos llegaron, cuántos eran nuevos y cuántos ya existían.
2. Ver el **resumen**: total de registros, total de vehículos hurtados, periodo de los hechos, vehículos por tipo de hurto y los 5 departamentos con más casos.
3. Buscar en la **tabla** por departamento o municipio (no importan tildes ni mayúsculas), y filtrar por tipo de hurto y género. El resumen también se actualiza con el filtro.

---

## 6. Estructura del proyecto y MVC

```
proyecto_datos_abiertos/
│
├── app.py                    # CONTROLADOR: rutas de Flask
├── api/
│   ├── __init__.py
│   └── api_client.py         # Servicio: consumo de la API externa
├── models/
│   ├── __init__.py
│   └── datos_model.py        # MODELO: conexión y consultas a SQL Server
├── templates/
│   └── index.html            # VISTA: página que ve el usuario
├── static/
│   └── estilos.css           # Estilos de la vista
├── sql/
│   ├── crear_base_datos.sql  # Script de creación de BD y tabla
│   └── consultas_evidencia.sql
├── evidencias/               # Capturas para la entrega
├── probar_api.py             # Prueba de la API
├── probar_conexion.py        # Prueba de la conexión a SQL Server
├── .env.example              # Plantilla de configuración
├── .gitignore
├── requirements.txt
└── README.md
```

| Capa | Archivo | Qué hace | Qué NO hace |
|---|---|---|---|
| **Modelo** | `models/datos_model.py` | Abre la conexión con pyodbc, convierte los datos, inserta sin duplicar y hace los `SELECT` (tabla, filtros, resumen) | No sabe nada de HTML ni de Flask |
| **Vista** | `templates/index.html` + `static/estilos.css` | Muestra formularios, mensajes, resumen y tabla con Jinja2 | No se conecta a SQL Server ni a la API |
| **Controlador** | `app.py` | Recibe las peticiones (`/` y `/sincronizar`), valida el formulario, llama a la API y al modelo y escoge la plantilla | No tiene SQL ni HTML |
| **Servicio API** | `api/api_client.py` | Hace la petición HTTP con `requests` y devuelve el JSON como lista de Python | No guarda nada en la BD |

### Flujo completo

```
NAVEGADOR ──(1) POST /sincronizar──► CONTROLADOR (app.py)
                                        │
                     (2) obtener_registros()      (3) guardar_registros()
                                        ▼                    ▼
                                 API datos.gov.co     MODELO ──► SQL SERVER
                                    (JSON)                         │
                                        └────────► CONTROLADOR ◄───┘
                                                       │ (4) redirect + flash
NAVEGADOR ◄──(6) HTML── VISTA (index.html) ◄──(5) GET / consultar_registros()
```

### Rutas

| Ruta | Método | Función |
|---|---|---|
| `/` | GET | Muestra la página. Recibe los filtros `q`, `tipo` y `genero` en la URL |
| `/sincronizar` | POST | Pide datos a la API y los guarda. Recibe `cantidad` y `desde` del formulario |

---

## 7. Cómo evitamos los duplicados

Lo hicimos en dos niveles:

1. **En Python:** antes de cada `INSERT`, el modelo hace `SELECT 1 FROM HurtosVehiculos WHERE id_api = ?`. Si ya existe, lo cuenta como repetido y sigue con el siguiente.
2. **En SQL Server:** la columna `id_api` tiene restricción `UNIQUE`. Aunque el código fallara, la base de datos no dejaría guardar dos veces el mismo registro.

Además, todo el guardado está en una transacción: si algo falla en la mitad, se hace `rollback()` y no queda la carga a medias.

---

## 8. Pruebas realizadas

| # | Prueba | Resultado esperado |
|---|---|---|
| 1 | `python probar_api.py` | Se reciben 5 registros con los 9 campos y el `:id` |
| 2 | `python probar_conexion.py` | "Conexión exitosa a SQL Server" |
| 3 | Abrir la página con la tabla vacía | Sale "No hay registros para mostrar" |
| 4 | Sincronizar 100 desde la posición 0 | Nuevos: 100 · Ya existían: 0 |
| 5 | Repetir la misma sincronización | Nuevos: 0 · Ya existían: 100 (**no se duplican**) |
| 6 | Sincronizar 500 desde la posición 50 | Nuevos: 450 · Ya existían: 50 |
| 7 | Buscar "medellin" (sin tilde) | Aparecen registros de Medellín |
| 8 | Filtrar por tipo "Hurto Motocicletas" y género | La tabla y el resumen cambian según el filtro |
| 9 | Escribir letras en la posición | Mensaje "deben ser números" |
| 10 | Apagar SQL Server y abrir la página | Aviso amigable en vez de error 500 |
| 11 | En SSMS, correr la consulta de duplicados de `sql/consultas_evidencia.sql` | No devuelve filas |

---

## 9. Evidencias

En la carpeta `evidencias/` van las capturas que pide la guía (ver el archivo `evidencias/LEEME.md`):

- Respuesta JSON de la API (salida de `probar_api.py` o el endpoint en el navegador)
- Registros guardados en SQL Server (consultas de `sql/consultas_evidencia.sql` en SSMS)
- Página principal, mensaje de sincronización y consulta filtrada

---

## 10. Errores frecuentes y cómo resolverlos

| Error | Causa | Solución |
|---|---|---|
| `TemplateSyntaxError: tag name expected` | (Nos pasó en las pruebas) Habíamos puesto `{% ... %}` dentro de un comentario HTML `<!-- -->` y Jinja igual lo intenta leer | Usar comentarios de Jinja `{# ... #}` |
| `Data source name not found` | El nombre del driver en el `.env` no coincidía con el instalado | Revisar en "Orígenes de datos ODBC" de Windows el nombre exacto |
| `Login failed` | Autenticación equivocada | Poner `DB_TRUSTED=yes` para Windows o completar usuario y clave |
| `Invalid object name 'dbo.HurtosVehiculos'` | No se había corrido el script SQL o se corrió en otra base | Ejecutar `sql/crear_base_datos.sql` completo |
| HTTP 429 | La API limita las peticiones sin token | Esperar un rato, pedir menos registros o crear un token gratuito en datos.gov.co |
| Búsqueda "bogota" no encontraba "Bogotá" | El `LIKE` distingue tildes según la intercalación | Usamos `COLLATE Latin1_General_CI_AI` en el filtro |

---

## 11. Limitaciones y alcance

- No es un CRUD: no se crean, editan ni eliminan registros desde la web (así lo pide la guía).
- La tabla de la página muestra máximo 100 registros por consulta (los más recientes), pero el resumen sí cuenta todos los que coinciden con el filtro.
- No tiene usuarios ni login, y solo está pensada para correr en local (`debug=True` solo en desarrollo).
- El dataset es grande; nosotros solo cargamos una parte por bloques usando la posición (`$offset`).
- Si se usa el plan B del identificador (hash), dos registros idénticos quedarían como uno.

---

## 12. Distribución del trabajo

| Integrante | Responsabilidad principal | Archivos |
|---|---|---|
| Integrante 1 · API | Elegir el dataset, leer la documentación de Socrata, resolver el tema del `:id`, petición HTTP y manejo de errores | `api/api_client.py`, `probar_api.py` |
| Integrante 2 · SQL y Modelo | Script de BD, conexión pyodbc, conversión de datos, inserción sin duplicados, consultas y resumen | `sql/`, `models/datos_model.py`, `probar_conexion.py` |
| Integrante 3 · Web | Rutas de Flask, validación de formularios, plantilla HTML, filtros y estilos | `app.py`, `templates/index.html`, `static/estilos.css` |
| Todos | Integración, pruebas, evidencias, README y sustentación | — |

---

## 13. Referencias

- Portal de Datos Abiertos de Colombia: https://www.datos.gov.co/
- Documentación de la API SODA (Socrata): https://dev.socrata.com/docs/queries/
- Campos de sistema de Socrata (`:id`): https://dev.socrata.com/docs/system-fields
- Documentación de Flask: https://flask.palletsprojects.com/
- Documentación de pyodbc: https://github.com/mkleehammer/pyodbc/wiki
