"""CRUD real de Productos reutilizando una categoría existente en PostgreSQL."""

import os
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
    category_id = int(os.getenv("PRODUCT_CATEGORY_ID", "2"))
    suffix = uuid4().hex[:10]

    category = expect(
        client.get(f"/api/categorias/{category_id}"),
        200,
        "consultar categoría existente",
    )["datos"]
    if not category["activo"]:
        raise AssertionError(f"La categoría {category_id} está inactiva.")

    product = expect(
        client.post(
            "/productos",
            json={
                "nombre": f"Producto reutiliza categoría {suffix}",
                "descripcion": "Prueba PostgreSQL sin crear categorías",
                "precio": "18000.00",
                "id_categoria": category_id,
            },
        ),
        201,
        "POST producto",
    )
    product_id = product["id_producto"]
    if product["categoria"]["id_categoria"] != category_id:
        raise AssertionError("El producto no quedó relacionado con la categoría elegida.")

    expect(client.get(f"/productos/{product_id}"), 200, "GET producto por ID")
    listed = expect(
        client.get(f"/productos?id_categoria={category_id}"),
        200,
        "GET productos por categoría",
    )
    if not any(item["id_producto"] == product_id for item in listed):
        raise AssertionError("El producto creado no apareció en su categoría.")

    expect(
        client.put(
            f"/productos/{product_id}",
            json={"precio": "19000.50", "descripcion": "Actualizado en PostgreSQL"},
        ),
        200,
        "PUT producto",
    )
    expect(
        client.patch(
            f"/productos/{product_id}/disponibilidad",
            json={"disponible": False},
        ),
        200,
        "PATCH disponibilidad",
    )
    deleted = expect(
        client.delete(f"/productos/{product_id}"),
        200,
        "DELETE lógico producto",
    )
    if deleted["datos"]["activo"] or deleted["datos"]["disponible"]:
        raise AssertionError("El producto no quedó desactivado correctamente.")

    category_after = expect(
        client.get(f"/api/categorias/{category_id}"),
        200,
        "comprobar categoría sin modificaciones",
    )["datos"]
    if not category_after["activo"]:
        raise AssertionError("La prueba modificó indebidamente la categoría existente.")

    print(
        "CRUD de Productos completado con categoría existente: "
        f"producto_id={product_id}, categoria={category_after['nombre']} ({category_id})."
    )


if __name__ == "__main__":
    run()
