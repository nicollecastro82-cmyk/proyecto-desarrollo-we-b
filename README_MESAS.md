# PoliRestaurante - módulo de Mesas (Nicole)

El módulo mantiene sus cinco funcionalidades originales y ahora se registra en la
aplicación común de `app.py`:

1. Registrar una mesa.
2. Listar mesas, con filtro opcional por estado.
3. Consultar una mesa por ID.
4. Actualizar el número de una mesa.
5. Cambiar el estado de una mesa.

La tabla oficial usa `id_mesa`, `numero_mesa` y el enum `estado_mesa`, cuyos valores
son `LIBRE`, `OCUPADA` y `FUERA_DE_SERVICIO`.

## API REST

```text
POST  /mesas
GET   /mesas
GET   /mesas/{id}
PUT   /mesas/{id}
PATCH /mesas/{id}/estado
```

Ejecuta todo el backend con:

```powershell
python -m flask --app app run --debug
```

La migración `migrations/001_crear_mesa_y_producto.sql` ya fue ejecutada y verificada
en PostgreSQL. Para pruebas aisladas usa:

```powershell
python -m unittest tests.test_integracion_api -v
```

La colección de Postman es
`postman/PoliRestaurante-Mesas.postman_collection.json`.
