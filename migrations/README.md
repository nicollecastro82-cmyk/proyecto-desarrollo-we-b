# Migraciones de integración

## 001 - Mesas y productos

`001_crear_mesa_y_producto.sql` se ejecutó correctamente el 17 de octubre de 2026 en
la base `polirestaurante`, esquema `public`, PostgreSQL 18.4, después de recibir
autorización explícita.

La migración creó:

- El enum `estado_mesa`: `LIBRE`, `OCUPADA` y `FUERA_DE_SERVICIO`.
- La tabla `mesa`, con PK, número único y validación positiva.
- La tabla `producto`, con PK, nombre único, precio positivo, estados lógicos y FK
  `producto.id_categoria -> categoria.id_categoria` con `ON DELETE RESTRICT`.
- El índice `ix_producto_id_categoria`.

No eliminó ni actualizó datos existentes. Se verificaron las columnas, PK, FK,
restricciones, enum e índice mediante introspección de PostgreSQL.

## 002 - Pedido

`002_crear_pedido.sql` se ejecutó correctamente el 23 de octubre de 2026 en la base
`polirestaurante`, esquema `public`, PostgreSQL 18.4. Se volvió a ejecutar para
comprobar que fuera idempotente y no duplicó objetos ni modificó datos.

La migración implementa la entidad compartida definida en el modelo
relacional oficial. Crea los enums `tipo_pedido` y `estado_pedido`, la tabla `pedido`,
sus claves foráneas hacia `mesa` y `usuario`, los índices y la actualización automática
de `fecha_ultima_actualizacion`.

También formaliza las relaciones uno a uno:

- `pago.id_pedido -> pedido.id_pedido`.
- `entrega.id_pedido -> pedido.id_pedido`.

La migración no elimina ni actualiza registros existentes.

## 003 - Detalle de pedido e historial

`003_crear_detalle_e_historial.sql` completa las 11 tablas del modelo oficial con
`detalle_pedido` e `historial_estado`. Incluye PK, FK, índices, cantidades positivas,
precios no negativos y una línea única por producto dentro de cada pedido.

Se ejecutó correctamente el 24 de octubre de 2026 sobre la base `polirestaurante`
configurada en `.env`. Se ejecutó una segunda vez para comprobar su idempotencia y
se verificaron por introspección las 11 tablas, las cuatro claves foráneas nuevas y
el trigger. No se eliminaron ni modificaron registros existentes.

El disparador `trg_detalle_recalcular_total` mantiene `pedido.valor_total` como la
suma de `cantidad * precio_unitario` después de insertar, modificar o eliminar un
detalle. La migración no elimina ni modifica registros existentes.

La columna `categoria.nombre` mide actualmente 100 caracteres en PostgreSQL, mientras
el documento oficial indica 80. La API ya limita los nombres nuevos a 80. No se
ejecutó un `ALTER COLUMN`: reducir el tamaño requeriría una autorización estructural
independiente y una validación previa de datos.
