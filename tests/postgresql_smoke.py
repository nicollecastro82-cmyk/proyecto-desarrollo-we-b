"""Prueba de humo explícita contra PostgreSQL.

No forma parte del descubrimiento normal de unittest porque crea datos identificables
en la base configurada en .env. Se ejecuta manualmente durante la integración.
"""

import os
from datetime import date
from uuid import uuid4

from app import app


def expect(response, expected_status, label):
    if response.status_code != expected_status:
        raise AssertionError(
            f"{label}: se esperaba HTTP {expected_status}, se obtuvo "
            f"{response.status_code}: {response.get_data(as_text=True)}"
        )
    print(f"OK {label}: HTTP {response.status_code}")
    return response.get_json()


def run():
    client = app.test_client()
    suffix = uuid4().hex[:10]

    expect(client.get("/api/salud"), 200, "salud y conexión PostgreSQL")

    category_id = int(os.getenv("PRODUCT_CATEGORY_ID", "2"))
    category = expect(
        client.get(f"/api/categorias/{category_id}"),
        200,
        "consultar categoría existente",
    )["datos"]
    if not category["activo"]:
        raise AssertionError(
            f"La categoría existente {category_id} está inactiva y no puede usarse."
        )

    product = expect(
        client.post(
            "/productos",
            json={
                "nombre": f"Producto integración {suffix}",
                "descripcion": "Registro temporal de la prueba PostgreSQL",
                "precio": "12500.50",
                "id_categoria": category_id,
            },
        ),
        201,
        "crear producto",
    )
    product_id = product["id_producto"]
    expect(client.get(f"/productos/{product_id}"), 200, "consultar producto")
    expect(
        client.get(f"/productos?id_categoria={category_id}"),
        200,
        "listar menú por categoría",
    )
    expect(
        client.put(
            f"/productos/{product_id}",
            json={"precio": "13000.00", "descripcion": "Producto actualizado"},
        ),
        200,
        "actualizar producto",
    )
    expect(
        client.patch(
            f"/productos/{product_id}/disponibilidad",
            json={"disponible": False},
        ),
        200,
        "cambiar disponibilidad de producto",
    )
    expect(
        client.delete(f"/productos/{product_id}"),
        200,
        "desactivar producto",
    )
    table_number = 1_000_000 + int(suffix[:6], 16) % 900_000_000
    table = expect(
        client.post("/mesas", json={"numero_mesa": table_number}),
        201,
        "crear mesa",
    )
    table_id = table["id_mesa"]
    expect(client.get(f"/mesas/{table_id}"), 200, "consultar mesa")
    expect(client.get("/mesas?estado=LIBRE"), 200, "listar mesas libres")
    expect(
        client.put(
            f"/mesas/{table_id}",
            json={"numero_mesa": table_number + 1},
        ),
        200,
        "actualizar mesa",
    )
    expect(
        client.patch(
            f"/mesas/{table_id}/estado",
            json={"estado": "FUERA_DE_SERVICIO"},
        ),
        200,
        "cambiar estado de mesa",
    )

    roles = expect(client.get("/api/tipos-usuario"), 200, "listar roles")["datos"]
    waiter_role = next(role for role in roles if role["descripcion"] == "MESERO")
    login = f"integracion_{suffix}"
    password = "PruebaSegura123"
    user = expect(
        client.post(
            "/api/usuarios",
            json={
                "id_tipo_usuario": waiter_role["id_tipo_usuario"],
                "nombre": "Usuario Integración",
                "usuario_login": login,
                "contrasena": password,
                "correo": f"{login}@example.com",
                "telefono": "3000000000",
            },
        ),
        201,
        "crear usuario",
    )["datos"]
    user_id = user["id_usuario"]
    expect(
        client.post(
            "/api/auth/login",
            json={"usuario_login": login, "contrasena": password},
        ),
        200,
        "autenticar usuario",
    )
    expect(
        client.patch(
            f"/api/usuarios/{user_id}",
            json={"telefono": "3110000000"},
        ),
        200,
        "actualizar usuario",
    )

    schedule_payload = {
        "id_usuario": user_id,
        "fecha": date(2099, 10, 24).isoformat(),
        "hora_inicio": "08:00",
        "hora_fin": "16:00",
        "observacion": f"Prueba PostgreSQL {suffix}",
    }
    schedule = expect(
        client.post("/api/horarios", json=schedule_payload),
        201,
        "crear horario",
    )["datos"]
    schedule_id = schedule["id_horario"]
    expect(
        client.get(f"/api/horarios/{schedule_id}"),
        200,
        "consultar horario",
    )
    schedule_payload["hora_fin"] = "17:00"
    expect(
        client.put(f"/api/horarios/{schedule_id}", json=schedule_payload),
        200,
        "actualizar horario",
    )
    expect(
        client.delete(f"/api/horarios/{schedule_id}"),
        200,
        "eliminar horario temporal",
    )
    expect(
        client.delete(f"/api/usuarios/{user_id}"),
        200,
        "desactivar usuario de prueba",
    )

    expect(client.get("/api/pagos"), 200, "listar pagos")
    expect(client.get("/api/entregas"), 200, "listar entregas")
    payment_dependency = expect(
        client.post(
            "/api/pagos",
            json={"id_pedido": 1, "metodo": "EFECTIVO", "valor": 10000},
        ),
        503,
        "dependencia Pedido para pagos",
    )
    delivery_dependency = expect(
        client.post(
            "/api/entregas",
            json={
                "id_pedido": 1,
                "direccion_entrega": "Dirección de prueba",
                "telefono_contacto": "3000000000",
            },
        ),
        503,
        "dependencia Pedido para entregas",
    )
    if payment_dependency["error"]["codigo"] != "ORDER_DEPENDENCY_UNAVAILABLE":
        raise AssertionError("Pagos no informó correctamente la falta de Pedido.")
    if delivery_dependency["error"]["codigo"] != "ORDER_DEPENDENCY_UNAVAILABLE":
        raise AssertionError("Entregas no informó correctamente la falta de Pedido.")

    print("Prueba PostgreSQL completada correctamente.")
    print(f"Datos trazables: sufijo={suffix}, mesa_id={table_id}, usuario_id={user_id}")


if __name__ == "__main__":
    run()
