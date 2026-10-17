# PoliRestaurante - Servicios REST de Yina

Backend Flask para las cinco funcionalidades asignadas a Yina:

1. Gestión de categorías.
2. Gestión de usuarios y tipos de usuario.
3. Gestión de horarios de empleados.
4. Gestión de pagos.
5. Gestión de entregas a domicilio.

No incluye CRUD de Producto, Mesa, Pedido ni DetallePedido, porque pertenecen a otras
integrantes.

## Tecnologías

- Python 3.14.3
- Flask 3.1.3
- Flask-SQLAlchemy 3.1.1
- SQLAlchemy 2.1.1
- psycopg 3.3.6
- PostgreSQL 18.4
- JSON y servicios REST

## Preparación

Activa el entorno e instala las dependencias si es necesario:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Copia `.env.example` como `.env` y configura la contraseña de PostgreSQL. El formato
esperado es:

```text
DATABASE_URL=postgresql+psycopg://postgres:CONTRASEÑA@localhost:5433/polirestaurante
```

Prepara las tablas propias y los roles iniciales:

```powershell
python -m flask --app app init-db
```

El comando usa `create_all`: crea únicamente lo que falta y no elimina tablas ni datos.

## Ejecutar la API

```powershell
python -m flask --app app run --debug
```

La URL local es `http://127.0.0.1:5000`. Para comprobar la conexión:

```text
GET /api/salud
```

## Estructura principal

```text
app.py                    Configuración Flask, errores JSON y comando init-db
extensions.py             Instancia compartida de SQLAlchemy
models.py                 Modelos ORM y enums
api_utils.py              Validación común de solicitudes
shared_dependencies.py    Contrato de integración con Pedido
routes/                    Blueprints REST por funcionalidad
tests/                     Pruebas funcionales y de error
postman/                   Colección y ambiente de Postman
categorias.py              Compatibilidad con el módulo anterior
consola.py                 Compatibilidad con la prueba anterior por consola
```

## Tablas propias

| Tabla | Uso |
|---|---|
| `categoria` | Clasificación de productos |
| `tipo_usuario` | Roles del sistema |
| `usuario` | Empleados, clientes y credenciales |
| `horario_empleado` | Turnos de empleados |
| `pago` | Pagos asociados a pedidos |
| `entrega` | Entregas de pedidos a domicilio |

La tabla antigua `categoria` conserva físicamente `nombre VARCHAR(100)` para no alterar
datos existentes. La API valida el máximo de 80 caracteres definido en el modelo
relacional del proyecto.

## Endpoints

### Categorías

```text
GET    /api/categorias
GET    /api/categorias/{id}
POST   /api/categorias
PUT    /api/categorias/{id}
PATCH  /api/categorias/{id}
PATCH  /api/categorias/{id}/estado
DELETE /api/categorias/{id}
```

La eliminación es lógica: cambia `activo` a `false`. Por defecto, el listado muestra
solo categorías activas. Usa `?incluir_inactivas=true` para ver todas.

```json
{
  "nombre": "Bebidas",
  "activo": true
}
```

### Tipos de usuario y usuarios

```text
GET/POST                 /api/tipos-usuario
GET/PUT/PATCH/DELETE     /api/tipos-usuario/{id}
GET/POST                 /api/usuarios
GET/PUT/PATCH/DELETE     /api/usuarios/{id}
PATCH                    /api/usuarios/{id}/estado
POST                     /api/auth/login
```

Los roles iniciales son `ADMINISTRADOR`, `COCINA`, `MESERO`, `CLIENTE` y
`DOMICILIARIO`. Las contraseñas se guardan con hash y nunca se devuelven en JSON.
`DELETE /api/usuarios/{id}` realiza desactivación lógica.

```json
{
  "id_tipo_usuario": 1,
  "nombre": "Yina Ardila",
  "usuario_login": "yina",
  "contrasena": "ClaveSegura123",
  "correo": "yina@example.com",
  "telefono": "3001234567"
}
```

### Horarios

```text
GET/POST                 /api/horarios
GET/PUT/PATCH/DELETE     /api/horarios/{id}
```

```json
{
  "id_usuario": 1,
  "fecha": "2026-10-24",
  "hora_inicio": "08:00",
  "hora_fin": "16:00",
  "observacion": "Turno de sustentación"
}
```

La API verifica que el usuario sea un empleado activo y evita turnos solapados.

### Pagos

```text
GET/POST                 /api/pagos
GET/PUT/PATCH/DELETE     /api/pagos/{id}
PATCH                    /api/pagos/{id}/estado
```

```json
{
  "id_pedido": 1,
  "metodo": "PSE",
  "valor": 25000
}
```

Los métodos permitidos son `EFECTIVO` y `PSE`; los estados son `PENDIENTE`,
`APROBADO` y `RECHAZADO`. Los pagos finalizados se conservan para auditoría.

### Entregas

```text
GET/POST                 /api/entregas
GET/PUT/PATCH/DELETE     /api/entregas/{id}
PATCH                    /api/entregas/{id}/estado
```

```json
{
  "id_pedido": 1,
  "direccion_entrega": "Calle 10 # 20-30",
  "telefono_contacto": "3001234567"
}
```

Flujo permitido:

```text
PENDIENTE_ASIGNACION -> ASIGNADA -> RECOGIDA -> EN_CAMINO -> ENTREGADA
```

Desde `ASIGNADA`, `RECOGIDA` o `EN_CAMINO` se puede registrar
`CON_INCIDENCIA` con una observación.

## Dependencia pendiente: Pedido

`pago.id_pedido` y `entrega.id_pedido` están preparados para integrarse con la tabla
`pedido` de la otra integrante. Esa tabla todavía no existe en esta rama ni en la base
actual, por lo que la API no crea una copia incompleta.

Mientras falte, `POST /api/pagos` y `POST /api/entregas` responden con estado HTTP
`503` y el código `ORDER_DEPENDENCY_UNAVAILABLE`.

Cuando se integre `Pedido`, debe contener al menos `id_pedido`, `tipo` y `estado`;
después se añadirá la clave foránea de las tablas propias hacia
`pedido.id_pedido`.

## Pruebas

```powershell
python -m unittest discover -s tests -v
```

Las pruebas usan SQLite en memoria y crean una tabla `pedido` temporal solo para
validar los contratos de Pagos y Entregas. No modifican PostgreSQL.

## Postman

La colección y el ambiente se encuentran dentro de la carpeta `postman` existente:

```text
postman/PoliRestaurante-Yina.postman_collection.json
postman/PoliRestaurante-local.postman_environment.json
```

Selecciona el ambiente `PoliRestaurante local`, inicia Flask y ejecuta las solicitudes
en el orden de las carpetas. Las solicitudes de Pagos y Entregas esperan un
`orderId` creado por el módulo compartido de Pedido.
