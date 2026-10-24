"""CRUD real de Productos reutilizando una categoría existente en PostgreSQL."""

import os
from uuid import uuid4

from app import app
from extensions import db
from producto import Producto


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
    configured_category = os.getenv("PRODUCT_CATEGORY_ID")
    category_id = int(configured_category or "2")
    suffix = uuid4().hex[:10]

    response = client.get(f"/api/categorias/{category_id}")
    category = expect(response, 200, "consultar categoría existente")["datos"]
    if not category["activo"]:
        if configured_category:
            raise AssertionError(f"La categoría configurada {category_id} está inactiva.")
        active = expect(
            client.get("/api/categorias"), 200, "buscar categoría activa alternativa"
        )["datos"]
        if not active:
            raise AssertionError("No existe ninguna categoría activa para la prueba.")
        category = active[0]
        category_id = category["id_categoria"]
        print(f"AVISO: la categoría 2 está inactiva; se usará la {category_id}.")

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
    with app.app_context():
        temporary = db.session.get(Producto, product_id)
        if temporary is not None:
            db.session.delete(temporary)
            db.session.commit()
    print("Limpieza OK: el producto temporal fue eliminado físicamente.")


if __name__ == "__main__":
    run()
