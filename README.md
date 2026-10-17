# PoliRestaurante - backend REST integrado

Backend universitario construido con Python, Flask, Flask-SQLAlchemy y PostgreSQL.
La aplicación común integra el trabajo de las tres ramas sin duplicar conexiones ni
instancias de SQLAlchemy.

## Responsabilidades conservadas

- **Yina:** categorías, usuarios y roles, horarios, pagos y entregas.
- **Nicole:** mesas.
- **Productos:** catálogo y disponibilidad de productos.

`Pedido` y `DetallePedido` no están implementados en este repositorio integrado. No
se creó una versión paralela porque son dependencias compartidas pendientes.

## Tecnologías

- Python 3.14.3
- Flask 3.1.3
- Flask-SQLAlchemy 3.1.1
- SQLAlchemy 2.1.1
- psycopg 3.3.6
- PostgreSQL 18.4

## Configuración

Activa el entorno e instala las dependencias si hace falta:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Copia `.env.example` como `.env` y cambia la contraseña:

```text
DATABASE_URL=postgresql+psycopg://postgres:CONTRASEÑA@localhost:5433/polirestaurante
```

## Base de datos

En PostgreSQL existen las tablas de Yina (`categoria`, `tipo_usuario`, `usuario`,
`horario_empleado`, `pago` y `entrega`) y las tablas integradas `mesa` y `producto`.
Todavía no existe `pedido`.

La migración `migrations/001_crear_mesa_y_producto.sql` se ejecutó el 17 de octubre
de 2026 con autorización previa. Creó `mesa`, `producto`, el enum `estado_mesa`, sus
restricciones y la FK de producto hacia categoría sin modificar datos anteriores.
Consulta `migrations/README.md` para ver el registro técnico.

Hay una diferencia conocida y compatible: `categoria.nombre` es `varchar(100)` en la
base actual y `varchar(80)` en el documento oficial. La API limita los nombres a 80,
pero no se redujo la columna para evitar afectar datos existentes.

## Ejecutar todos los servicios

El único punto de entrada necesario es `app.py`:

```powershell
python -m flask --app app run --debug
```

La API queda en `http://127.0.0.1:5000`. La comprobación de conexión es:

```text
GET /api/salud
```

No ejecutes `main.py` y `api_mesas.py` simultáneamente: se conservaron como entradas
compatibles, pero ambos cargan la misma aplicación integrada.

## Dos tareas CRUD por consola

Las cinco funcionalidades de Yina se pueden demostrar de dos formas independientes:

1. **Driver:** `consola_driver.py` usa `psycopg` y SQL parametrizado directamente.
   No importa Flask, SQLAlchemy ni los modelos ORM.
2. **ORM:** `consola_orm.py` usa los servicios Flask existentes, que ejecutan el CRUD
   mediante los modelos y la sesión de SQLAlchemy.

Para abrir un menú inicial y escoger cualquiera de las dos tareas:

```powershell
.\.venv\Scripts\python.exe consola.py
```

Para demostrar únicamente la conexión y el CRUD directo con el driver:

```powershell
.\.venv\Scripts\python.exe consola_driver.py
```

Para demostrar únicamente el CRUD con el ORM:

```powershell
.\.venv\Scripts\python.exe consola_orm.py
```

Los dos menús permiten escoger Categorías, Usuarios y roles, Horarios de empleados,
Pagos o Entregas. En los campos de actualización, `Enter` conserva el valor y `-`
elimina los campos opcionales que lo indiquen. Pagos y Entregas no podrán crear
registros hasta integrar la tabla compartida `pedido`; ambos menús informan esa
dependencia sin inventar otro modelo de Pedido.

## Endpoints

### Yina

```text
GET/POST                 /api/categorias
GET/PUT/PATCH/DELETE     /api/categorias/{id}
PATCH                    /api/categorias/{id}/estado

GET/POST                 /api/tipos-usuario
GET/PUT/PATCH/DELETE     /api/tipos-usuario/{id}
GET/POST                 /api/usuarios
GET/PUT/PATCH/DELETE     /api/usuarios/{id}
PATCH                    /api/usuarios/{id}/estado
POST                     /api/auth/login

GET/POST                 /api/horarios
GET/PUT/PATCH/DELETE     /api/horarios/{id}

GET/POST                 /api/pagos
GET/PUT/PATCH/DELETE     /api/pagos/{id}
PATCH                    /api/pagos/{id}/estado

GET/POST                 /api/entregas
GET/PUT/PATCH/DELETE     /api/entregas/{id}
PATCH                    /api/entregas/{id}/estado
```

Categorías y usuarios usan desactivación lógica. Por defecto, el listado de categorías
solo devuelve las activas.

### Mesas - Nicole

```text
GET/POST                 /mesas
GET/PUT                  /mesas/{id}
PATCH                    /mesas/{id}/estado
```

Estados válidos: `LIBRE`, `OCUPADA` y `FUERA_DE_SERVICIO`. También se aceptan en
minúsculas. No hay `DELETE` porque la funcionalidad administrativa conserva la mesa y
cambia su estado.

Ejemplo:

```json
{
  "numero_mesa": 10
}
```

### Productos

```text
GET/POST                 /productos
GET/PUT/PATCH/DELETE     /productos/{id}
PATCH                    /productos/{id}/disponibilidad
```

El listado devuelve solo productos activos y disponibles. `DELETE` realiza una
desactivación lógica y conserva el registro.

```json
{
  "nombre": "Bandeja paisa",
  "descripcion": "Plato tradicional",
  "precio": 25000,
  "id_categoria": 2
}
```

El modelo Python conserva los nombres que usó el módulo original (`nombre`,
`descripcion`, `precio`) y los mapea a las columnas oficiales
`nombre_producto`, `descripcion_producto` y `precio_producto`.

## Dependencia pendiente de Pedido

Pagos necesita que `pedido` contenga al menos `id_pedido`. Entregas necesita además
`tipo`, con el valor `DOMICILIO` para poder crear una entrega. El contrato oficial
completo también incluye `id_mesa`, `id_mesero`, `id_cliente`, `estado`, `valor_total`,
`observaciones`, `fecha_creacion` y `fecha_ultima_actualizacion`.

Mientras la tabla no exista:

- `POST /api/pagos` responde `503 ORDER_DEPENDENCY_UNAVAILABLE`.
- `POST /api/entregas` responde `503 ORDER_DEPENDENCY_UNAVAILABLE`.
- Consultar registros de pago o entrega existentes sí está disponible.
- Las claves foráneas de `pago.id_pedido` y `entrega.id_pedido` siguen pendientes.

## Pruebas automáticas

```powershell
python -m unittest discover -s tests -v
```

Las pruebas usan SQLite en memoria y no modifican PostgreSQL. Incluyen los módulos de
Yina, la integración de Mesas y Productos, rutas duplicadas, validaciones y errores.

La prueba explícita contra PostgreSQL se ejecuta por separado porque crea datos de
integración identificables:

```powershell
python -m tests.postgresql_smoke
python -m tests.productos_postgresql_smoke
```

Esta prueba reutiliza por defecto la categoría existente `Bebidas` con ID `2`,
desactiva por API el producto y usuario creados, elimina solo su horario temporal y
deja la mesa creada en `FUERA_DE_SERVICIO`, pues el módulo de Mesas no define
eliminación. Puedes seleccionar otra categoría activa mediante `PRODUCT_CATEGORY_ID`.
El segundo comando prueba únicamente POST, GET, PUT, PATCH y DELETE lógico de
Productos sin crear ni modificar categorías.

## Postman

Importa el ambiente:

```text
postman/PoliRestaurante-local.postman_environment.json
```

Después importa y ejecuta por separado las colecciones, manteniendo visible la autoría:

```text
postman/PoliRestaurante-Yina.postman_collection.json
postman/PoliRestaurante-Mesas.postman_collection.json
postman/PoliRestaurante-Productos.postman_collection.json
```

Usa una base de desarrollo. Las colecciones generan nombres y números de prueba únicos.
Productos verifica primero que `productCategoryId` corresponda a una categoría activa
y desactiva al final únicamente el producto de prueba; nunca crea, modifica ni
desactiva categorías. Mesas deja la mesa creada en `FUERA_DE_SERVICIO` porque ese
módulo no contempla eliminación.

## Archivos principales

```text
app.py                    Fábrica Flask y punto de entrada común
consola.py                Menú para elegir entre las dos tareas CRUD
consola_driver.py         CRUD directo con psycopg y SQL parametrizado
consola_orm.py            Entrada independiente al CRUD con SQLAlchemy ORM
extensions.py             Única instancia compartida de SQLAlchemy
models.py                 Modelos de las funcionalidades de Yina
routes/                    Blueprints REST de Yina
api_mesas.py              Blueprint REST de Mesas
mesas.py                  Modelo y lógica de Mesa
main.py                   Blueprint REST de Productos
producto.py               Modelo ORM de Producto
catalogo_dao.py           Acceso a datos de Productos y Categoría
shared_dependencies.py    Contrato temporal con Pedido
tests/                     Pruebas automáticas
postman/                   Colecciones y ambiente
migrations/               Migraciones SQL y registro de su ejecución
```
