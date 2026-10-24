# PoliRestaurante - backend integrado

API universitaria para la gestión de un restaurante. El proyecto usa una sola
aplicación Flask, SQLAlchemy ORM y PostgreSQL; también incluye una consola
independiente con el driver `psycopg`.

## Tecnologías

- Python 3.14.3
- pip 26.2.1
- Flask 3.1.3
- Flask-SQLAlchemy 3.1.1
- SQLAlchemy 2.1.1
- psycopg y psycopg-binary 3.3.6
- python-dotenv 1.2.3
- PostgreSQL 18.4

## Responsabilidades conservadas

- Yina: Categorías, Usuarios y Roles, Horarios, Pagos y Entregas.
- Nicole: Mesas.
- Valeria: Productos y Menú.
- La integración de Pedido, Detalle, Cocina e Historial conecta esos módulos
  compartidos; no cambia la autoría de los desarrollos originales.

## Las 15 funcionalidades integradas

01. Gestionar categorías
02. Gestionar productos y menú
03. Gestionar mesas
04. Gestionar usuarios
05. Gestionar roles
06. Iniciar sesión
07. Gestionar horarios
08. Registrar pedidos en salón
09. Registrar pedidos a domicilio
10. Gestionar detalle del pedido
11. Consultar y filtrar pedidos en Cocina
12. Actualizar estado de preparación
13. Gestionar pagos
14. Gestionar domicilios y entregas
15. Consultar estado e historial de pedidos

Los nombres proceden de `functionalities.py`, que funciona como catálogo único
para impedir diferencias entre Driver, ORM y Postman.

## Correspondencia 1 a 1

| N.º | Funcionalidad | Menú Driver | Menú ORM | Carpeta Postman | Endpoints asociados | Estado de pruebas |
|---:|---|---|---|---|---|---|
| 01 | Gestionar categorías | 01 | 01 | 01. Gestionar categorías | `/api/categorias` | Automatizada; colección validada |
| 02 | Gestionar productos y menú | 02 | 02 | 02. Gestionar productos y menú | `/productos` | Automatizada; colección validada |
| 03 | Gestionar mesas | 03 | 03 | 03. Gestionar mesas | `/mesas` | Automatizada; colección validada |
| 04 | Gestionar usuarios | 04 | 04 | 04. Gestionar usuarios | `/api/usuarios` | Automatizada; colección validada |
| 05 | Gestionar roles | 05 | 05 | 05. Gestionar roles | `/api/tipos-usuario` | Automatizada; colección validada |
| 06 | Iniciar sesión | 06 | 06 | 06. Iniciar sesión | `/api/auth/login` | Automatizada; colección validada |
| 07 | Gestionar horarios | 07 | 07 | 07. Gestionar horarios | `/api/horarios` | Automatizada; colección validada |
| 08 | Registrar pedidos en salón | 08 | 08 | 08. Registrar pedidos en salón | `/api/pedidos` (`SALON`) | Automatizada; colección validada |
| 09 | Registrar pedidos a domicilio | 09 | 09 | 09. Registrar pedidos a domicilio | `/api/pedidos` (`DOMICILIO`) | Automatizada; colección validada |
| 10 | Gestionar detalle del pedido | 10 | 10 | 10. Gestionar detalle del pedido | `/api/pedidos/{id}/detalles` | Automatizada; colección validada |
| 11 | Consultar y filtrar pedidos en Cocina | 11 | 11 | 11. Consultar y filtrar pedidos en Cocina | `/api/cocina/pedidos` | Automatizada; colección validada |
| 12 | Actualizar estado de preparación | 12 | 12 | 12. Actualizar estado de preparación | `/api/pedidos/{id}/estado` | Automatizada; colección validada |
| 13 | Gestionar pagos | 13 | 13 | 13. Gestionar pagos | `/api/pagos` | Automatizada; colección validada |
| 14 | Gestionar domicilios y entregas | 14 | 14 | 14. Gestionar domicilios y entregas | `/api/pedidos/{id}/domiciliario`, `/api/entregas` | Automatizada; colección validada |
| 15 | Consultar estado e historial de pedidos | 15 | 15 | 15. Consultar estado e historial de pedidos | `/api/pedidos/{id}`, `/api/pedidos/{id}/historial` | Automatizada; colección validada |

"Colección validada" significa que su JSON, las 15 carpetas, las variables y
los scripts JavaScript fueron comprobados automáticamente. La ejecución visual en
la aplicación Postman sigue siendo una comprobación manual del usuario.

## Configuración

Activa el entorno e instala las dependencias solo si hace falta:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

El archivo `.env` local debe contener una URL como esta. No publiques ese archivo
ni la contraseña:

```text
DATABASE_URL=postgresql+psycopg://postgres:CONTRASEÑA@localhost:5433/polirestaurante
```

## Base de datos

El esquema `public` contiene las 11 tablas del modelo oficial:

```text
categoria          producto             mesa
tipo_usuario       usuario              horario_empleado
pedido             detalle_pedido       pago
entrega            historial_estado
```

Las migraciones no destruyen datos y son idempotentes:

- `001_crear_mesa_y_producto.sql`: Mesa, Producto y `estado_mesa`.
- `002_crear_pedido.sql`: Pedido, `tipo_pedido`, `estado_pedido` y relaciones.
- `003_crear_detalle_e_historial.sql`: Detalle, Historial, claves foráneas,
  restricciones e índices. Su trigger recalcula `pedido.valor_total` al insertar,
  actualizar o eliminar detalles.

Las tres se ejecutaron sobre la base configurada. Para comprobar las 11 tablas sin
modificar datos:

```powershell
.\.venv\Scripts\python.exe -m tests.verificar_esquema_postgresql
```

No es necesario usar SQLite para ejecutar el proyecto. SQLite en memoria se usa
únicamente para aislar las pruebas unitarias.

## Datos de demostración

`scripts/cargar_datos_demo.py` agrega un restaurante ficticio relacionado sobre
las 11 tablas oficiales. La carga usa una transacción, reconoce sus registros por
marcadores `[DEMO]`, conserva los datos anteriores y puede ejecutarse varias veces
sin duplicar información.

La contraseña de las cuentas demo no está escrita en el código ni en el README.
Defínela solo para la terminal actual y elimínala al terminar:

```powershell
$env:POLIRESTAURANTE_DEMO_PASSWORD = "ELIGE_UNA_CLAVE_DEMO_SEGURA"
.\.venv\Scripts\python.exe scripts\cargar_datos_demo.py
Remove-Item Env:\POLIRESTAURANTE_DEMO_PASSWORD
```

Para verificar posteriormente los datos sin insertar ni modificar registros:

```powershell
.\.venv\Scripts\python.exe scripts\cargar_datos_demo.py --verify-only
```

Usuarios disponibles: `demo_admin`, `demo_cocina`, `demo_mesero_1`,
`demo_mesero_2`, `demo_cliente_1`, `demo_cliente_2` y `demo_domiciliario`.
Todos usan la contraseña que se proporcionó mediante la variable de entorno al
crear la carga.

## Ejecutar Flask

Desde la carpeta del proyecto ejecuta solamente:

```powershell
.\.venv\Scripts\python.exe -m flask --app app run --debug
```

La API queda disponible en `http://127.0.0.1:5000`. Comprueba la conexión con:

```text
GET /api/salud
```

`app.py` es el punto de entrada común. `main.py` y `api_mesas.py` conservan los
blueprints originales de Productos y Mesas, pero no se ejecutan como aplicaciones
separadas.

## Consola Driver y consola ORM

Son dos implementaciones distintas sobre la misma base:

- `consola_driver.py` usa `psycopg` y SQL parametrizado. No importa Flask,
  SQLAlchemy ni los modelos ORM.
- `consola_orm.py` abre el menú de servicios Flask respaldados por los modelos y la
  sesión de SQLAlchemy.

Selector de las dos tareas:

```powershell
.\.venv\Scripts\python.exe consola.py
```

Driver directamente:

```powershell
.\.venv\Scripts\python.exe consola_driver.py
```

ORM directamente:

```powershell
.\.venv\Scripts\python.exe consola_orm.py
```

Cada consola muestra un menú con exactamente las 15 funcionalidades. En las
actualizaciones, `Enter` conserva el dato actual cuando el menú lo indica.

## Endpoints REST

### Categorías, usuarios, roles y horarios

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
```

Categorías y Usuarios usan desactivación lógica. Por defecto, Categorías solo
lista registros activos. Las contraseñas se guardan como hashes de Werkzeug y nunca
se devuelven en JSON.

### Mesas y productos

```text
GET/POST                 /mesas
GET/PUT                  /mesas/{id}
PATCH                    /mesas/{id}/estado

GET/POST                 /productos
GET/PUT/PATCH/DELETE     /productos/{id}
PATCH                    /productos/{id}/disponibilidad
```

Productos reutiliza `producto.id_categoria -> categoria.id_categoria`; no existe
otro CRUD de Categorías. El menú público oculta productos inactivos, no disponibles
o pertenecientes a categorías inactivas. Mesas conserva los registros y administra
los estados `LIBRE`, `OCUPADA` y `FUERA_DE_SERVICIO`.

### Pedidos, detalle, Cocina e historial

```text
GET/POST                 /api/pedidos
GET/PUT/PATCH/DELETE     /api/pedidos/{id}
GET/POST                 /api/pedidos/{id}/detalles
PUT/PATCH/DELETE         /api/pedidos/{id}/detalles/{id_detalle}
PATCH                    /api/pedidos/{id}/estado
PATCH                    /api/pedidos/{id}/domiciliario
GET                      /api/pedidos/{id}/historial
GET                      /api/cocina/pedidos?estado=PENDIENTE
```

Un pedido `SALON` exige una mesa libre y un usuario `MESERO`; al crearlo ocupa la
mesa y al entregarlo o cancelarlo la libera. Un pedido `DOMICILIO` exige un cliente,
dirección y teléfono, y crea sus datos de Entrega en la misma transacción.

Solo se agregan productos activos y disponibles. La cantidad debe ser positiva y el
precio se conserva en el detalle. El total se calcula a partir de los detalles. Las
transiciones permitidas son:

```text
PENDIENTE -> EN_PREPARACION | CANCELADO
EN_PREPARACION -> LISTO | CANCELADO
LISTO -> ENTREGADO
```

Los cambios a `EN_PREPARACION` y `LISTO` requieren un usuario de Cocina o
Administrador; cada cambio queda en `historial_estado` con fecha y responsable.

### Pagos y entregas

```text
GET/POST                 /api/pagos
GET/PUT/PATCH/DELETE     /api/pagos/{id}
PATCH                    /api/pagos/{id}/estado

GET/POST                 /api/entregas
GET/PUT/PATCH/DELETE     /api/entregas/{id}
PATCH                    /api/entregas/{id}/estado
```

Solo se admite un pago por pedido y su valor debe coincidir con el total calculado.
Un pago finalizado se conserva para auditoría. Una entrega solo pertenece a un
pedido `DOMICILIO`, se asigna cuando el pedido está `LISTO` y sigue el flujo
`ASIGNADA -> RECOGIDA -> EN_CAMINO -> ENTREGADA`.

## Postman

La colección principal tiene exactamente 15 carpetas de primer nivel. Importa:

```text
postman/PoliRestaurante-15-Funcionalidades.postman_collection.json
postman/PoliRestaurante-local.postman_environment.json
```

Selecciona el ambiente `PoliRestaurante local`, abre la colección
`PoliRestaurante — 15 Funcionalidades` y usa **Run collection** respetando el orden
guardado. Los scripts generan nombres, mesas e identificadores dinámicos; no debes
escribir IDs manuales. La primera carpeta comprueba Flask/PostgreSQL y selecciona
una categoría activa existente para Productos.

Las colecciones originales se conservan como respaldo y por autoría:

```text
postman/PoliRestaurante-Yina.postman_collection.json
postman/PoliRestaurante-Mesas.postman_collection.json
postman/PoliRestaurante-Productos.postman_collection.json
postman/PoliRestaurante-Pedidos.postman_collection.json
```

No importes esas cuatro colecciones de respaldo para la demostración de las 15,
porque aparecerían como colecciones adicionales y dificultarían el conteo. No han
sido eliminadas ni sobrescritas.

### Postman y los archivos YAML del espacio de trabajo

La colección principal ya está materializada en YAML dentro de
`postman/postman/collections/PoliRestaurante — 15 Funcionalidades/`, con sus 15
carpetas y 106 solicitudes. El ambiente YAML `PoliRestaurante local` también está
sincronizado con todas las variables dinámicas.

Las consultas de Categorías, Productos, Mesas, Usuarios, Pedidos, Pagos y
Entregas localizan los registros `[DEMO]` por nombre, login, número u observación
y guardan sus IDs en el ambiente. Los CRUD del Runner continúan usando variables
temporales diferentes, por lo que no desactivan ni modifican los datos base demo.

Si Postman tiene vinculada la carpeta `postman`, **no vuelvas a importar el JSON**:
abre directamente la colección YAML y selecciona `PoliRestaurante local`. El JSON
queda como respaldo portátil para otra computadora o espacio de trabajo.

Solo si la carpeta local no está vinculada, importa una vez los dos JSON indicados
arriba. Si ya existe una copia importada con el mismo nombre, conserva una sola en
la aplicación para evitar duplicados; no es necesario borrar ningún archivo del
proyecto.

Si usas las colecciones de respaldo por separado, respeta este orden manual:

1. En Yina, ejecuta Salud y crea los usuarios MESERO, COCINA, CLIENTE y
   DOMICILIARIO; las pruebas guardan sus IDs.
2. En Mesas, ejecuta POST, GET y PUT, pero conserva la mesa `LIBRE` hasta terminar
   los pedidos.
3. En Productos, verifica la categoría y ejecuta POST, GET y PUT; conserva el
   producto activo y disponible hasta terminar los pedidos.
4. Ejecuta Pedidos en orden. La colección reutiliza `mesaId`, `productId` y los IDs
   de usuario, calcula los totales y prueba HTTP 200, 201, 400, 403, 404, 409 y 422.
5. Para Pagos, usa el identificador y total guardados por Pedidos.
6. Al final puedes ejecutar la desactivación de Producto y el cambio de Mesa a
   `FUERA_DE_SERVICIO` para demostrar esas operaciones administrativas.

No hay IDs fijos de categorías, productos, mesas, usuarios o pedidos en la
colección principal. `productCategoryId` se obtiene de la lista real de categorías
activas y las demás variables se guardan al ejecutar cada solicitud.

## Pruebas

Pruebas automatizadas aisladas:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Prueba real de las 15 funcionalidades con Driver. Usa SQL parametrizado dentro de
una transacción y siempre ejecuta `rollback`:

```powershell
.\.venv\Scripts\python.exe -m tests.driver_postgresql_smoke
```

Prueba HTTP/ORM real del flujo central de pedidos. Crea datos temporales con sufijo
aleatorio y elimina exclusivamente esos registros al terminar:

```powershell
.\.venv\Scripts\python.exe -m tests.pedido_postgresql_smoke
```

Prueba independiente del CRUD de Productos con una categoría existente:

```powershell
.\.venv\Scripts\python.exe -m tests.productos_postgresql_smoke
```

Comprobación de solo lectura de la carga demo mediante ORM y REST:

```powershell
$env:POLIRESTAURANTE_DEMO_PASSWORD = "LA_MISMA_CLAVE_USADA_EN_LA_CARGA"
.\.venv\Scripts\python.exe -m tests.datos_demo_postgresql
Remove-Item Env:\POLIRESTAURANTE_DEMO_PASSWORD
```

Verificación realizada el 24 de octubre de 2026:

- 45 de 45 pruebas unitarias y de integración aisladas aprobadas.
- 11 de 11 tablas oficiales, claves foráneas y trigger de total verificados.
- 15 de 15 funcionalidades Driver aprobadas con `psycopg`; la transacción se
  revirtió al terminar.
- Flujo HTTP/ORM real de pedidos en salón y domicilio aprobado contra PostgreSQL;
  sus datos temporales fueron limpiados.
- CRUD HTTP real de Productos aprobado con una categoría existente y activa.
- Colección principal validada con 15 carpetas, 106 solicitudes, variables de
  demostración dinámicas y 117 scripts JavaScript con sintaxis válida.
- La ejecución visual del Runner de Postman no se marca como aprobada: debe hacerse
  manualmente después de importar la colección en la aplicación.

## Archivos principales

```text
app.py                                  aplicación Flask común
extensions.py                           instancia compartida de SQLAlchemy
models.py                               modelos ORM compartidos y de Yina
producto.py / main.py                   Producto y su blueprint
mesas.py / api_mesas.py                 Mesa y su blueprint
routes/pedidos.py                       pedidos, detalle, Cocina e historial
routes/pagos.py / routes/entregas.py    pagos y entregas
order_rules.py                          transiciones y roles permitidos
consola_driver.py                       Driver psycopg directo
consola_orm.py / consola.py             consola ORM y selector
functionalities.py                      nombres canónicos de las 15 funciones
migrations/                             migraciones seguras e idempotentes
postman/                                ambiente y colecciones
scripts/generar_coleccion_postman.py    genera la colección principal
scripts/cargar_datos_demo.py            carga ficticia, transaccional e idempotente
tests/                                  pruebas unitarias y smoke PostgreSQL
```
