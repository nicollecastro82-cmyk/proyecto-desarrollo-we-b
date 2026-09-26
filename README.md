# PoliRestaurante - CRUD de categorías

Programa de consola para crear, consultar, buscar, modificar y activar o desactivar
las categorías del menú de PoliRestaurante. No incluye frontend, páginas web ni
comandos con enlaces. Las categorías no se eliminan físicamente: se desactivan para
conservar la información administrativa. Los listados y las búsquedas muestran
únicamente categorías activas.

## Tecnologías

| Tecnología | Versión |
|---|---:|
| Python | 3.14.3 |
| pip | 26.2.1 |
| Flask | 3.1.3 |
| Flask-SQLAlchemy | 3.1.1 |
| SQLAlchemy | 2.1.1 |
| psycopg | 3.3.6 |
| psycopg-binary | 3.3.6 |
| python-dotenv | 1.2.3 |
| PostgreSQL | 18.4 |

## Archivos Python

- `app.py`: configura Flask y PostgreSQL, define el modelo `Categoria` y contiene el
  comando que crea la base de datos y la tabla.
- `consola.py`: contiene la lógica CRUD y el menú de consola.

No se necesitan otros archivos `.py` para ejecutar el programa.

## Tabla categoria

| Campo | Tipo | Restricción |
|---|---|---|
| `id_categoria` | entero | llave primaria autoincremental |
| `nombre` | texto de hasta 100 caracteres | obligatorio y único |
| `activo` | booleano | obligatorio; inicia en verdadero |

## Preparación

Activa el entorno virtual:

```powershell
.\.venv\Scripts\Activate.ps1
```

La conexión se guarda en `.env`. Su formato es:

```text
DATABASE_URL=postgresql+psycopg://postgres:CONTRASEÑA@localhost:5433/polirestaurante
```

La base `polirestaurante` y la tabla `categoria` ya están creadas. Si en el futuro
necesitas volver a prepararlas, ejecuta:

```powershell
python -m flask --app app init-db
```

## Ejecutar el programa

```powershell
python consola.py
```

El programa mostrará este menú:

```text
1. Crear categoría
2. Consultar categorías activas
3. Buscar categoría activa
4. Modificar categoría
5. Activar o desactivar categoría
0. Salir
```
