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

## Dependencia pendiente

La migración no crea `pedido`, porque esa entidad pertenece al módulo compartido que
aún no está implementado. Cuando se integre, se deberá validar como mínimo el contrato
`id_pedido`, `tipo` y `estado`, y después preparar otra migración para agregar las
claves foráneas `pago.id_pedido -> pedido.id_pedido` y
`entrega.id_pedido -> pedido.id_pedido`.

La columna `categoria.nombre` mide actualmente 100 caracteres en PostgreSQL, mientras
el documento oficial indica 80. La API ya limita los nombres nuevos a 80. No se
ejecutó un `ALTER COLUMN`: reducir el tamaño requeriría una autorización estructural
independiente y una validación previa de datos.
