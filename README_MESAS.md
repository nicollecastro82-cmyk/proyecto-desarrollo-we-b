# PoliRestaurante - CRUD de mesas

Programa de consola para registrar, consultar, actualizar y cambiar el estado de las
mesas de PoliRestaurante. Reutiliza la conexión a PostgreSQL de `categorias.py`.

## Archivos Python

- `mesas.py`: define el modelo `Mesa`, las validaciones y las 5 funcionalidades.
- `consola_mesas.py`: menú de consola para usar las funcionalidades.

## Tabla mesa

| Campo         | Tipo                         | Restricción                          |
| ------------- | ---------------------------- | ------------------------------------ |
| `id_mesa`     | entero                       | llave primaria autoincremental       |
| `numero_mesa` | entero                       | obligatorio, único y mayor que cero  |
| `estado`      | texto de hasta 20 caracteres | obligatorio; `libre` u `ocupada`     |

## Funcionalidades

1. Registrar mesa (`crear_mesa`): crea una mesa en estado `libre`.
2. Consultar mesas (`listar_mesas`): lista todas, con filtro opcional por estado.
3. Consultar mesa por ID (`consultar_mesa`).
4. Actualizar número de mesa (`actualizar_mesa`).
5. Ocupar o liberar mesa (`ocupar_mesa` y `liberar_mesa`).

## Preparación

La conexión se guarda en `.env`, con el formato de `.env.example`. Para crear la tabla
`mesa` por primera vez:

```
python -c "from mesas import app, db; app.app_context().push(); db.create_all()"
```

## Ejecutar el programa

```
python consola_mesas.py
```