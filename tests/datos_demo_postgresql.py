"""Verificación de solo lectura de los datos demo sobre PostgreSQL real."""

import os

from app import app
from scripts.cargar_datos_demo import PASSWORD_ENV, preflight, verify_demo_data


def expect(client, path, status=200, method="get", json=None):
    response = getattr(client, method)(path, json=json)
    if response.status_code != status:
        raise AssertionError(
            f"{method.upper()} {path}: HTTP {response.status_code}: "
            f"{response.get_data(as_text=True)}"
        )
    return response.get_json()


def run():
    password = os.getenv(PASSWORD_ENV)
    if not password:
        raise RuntimeError(f"Define {PASSWORD_ENV} para comprobar el inicio de sesión demo.")

    client = app.test_client()
    with app.app_context():
        connection, counts = preflight()
        verification = verify_demo_data()

    health = expect(client, "/api/salud")
    assert health["base_datos"] == "conectada"

    categories = expect(client, "/api/categorias")["datos"]
    assert len([item for item in categories if item["nombre"].endswith("[DEMO]")]) == 4

    products = expect(client, "/productos")
    demo_products = [item for item in products if item["nombre"].endswith("[DEMO]")]
    assert len(demo_products) == 12

    tables = expect(client, "/mesas")
    demo_tables = [item for item in tables if item["numero_mesa"] in {9101, 9102, 9103, 9104}]
    assert len(demo_tables) == 4

    roles = expect(client, "/api/tipos-usuario")["datos"]
    assert {item["descripcion"] for item in roles}.issuperset(
        {"ADMINISTRADOR", "COCINA", "MESERO", "CLIENTE", "DOMICILIARIO"}
    )

    users = expect(client, "/api/usuarios")["datos"]
    demo_users = [item for item in users if item["usuario_login"].startswith("demo_")]
    assert len(demo_users) == 7
    expect(
        client,
        "/api/auth/login",
        method="post",
        json={"usuario_login": "demo_admin", "contrasena": password},
    )

    schedules = expect(client, "/api/horarios")["datos"]
    assert len([item for item in schedules if (item["observacion"] or "").startswith("[DEMO]")]) == 4

    orders = expect(client, "/api/pedidos")["datos"]
    demo_orders = [item for item in orders if (item["observaciones"] or "").startswith("[DEMO:")]
    assert len(demo_orders) == 7
    assert {item["estado"] for item in demo_orders} == {
        "PENDIENTE",
        "EN_PREPARACION",
        "LISTO",
        "ENTREGADO",
        "CANCELADO",
    }

    for order in demo_orders:
        details = expect(client, f"/api/pedidos/{order['id_pedido']}/detalles")["datos"]
        assert details

    kitchen_pending = expect(client, "/api/cocina/pedidos?estado=PENDIENTE")["datos"]
    kitchen_preparing = expect(client, "/api/cocina/pedidos?estado=EN_PREPARACION")["datos"]
    assert any((item["observaciones"] or "").startswith("[DEMO:") for item in kitchen_pending)
    assert any((item["observaciones"] or "").startswith("[DEMO:") for item in kitchen_preparing)

    payments = expect(client, "/api/pagos")["datos"]
    assert len([item for item in payments if (item["referencia_transaccion"] or "").startswith("DEMO-")]) == 3

    deliveries = expect(client, "/api/entregas")["datos"]
    assert len([item for item in deliveries if (item["observacion"] or "").startswith("[DEMO]")]) == 3

    delivered = next(
        item
        for item in demo_orders
        if (item["observaciones"] or "").startswith("[DEMO:PEDIDO_DOMICILIO_ENTREGADO]")
    )
    history = expect(client, f"/api/pedidos/{delivered['id_pedido']}/historial")["datos"]
    assert [item["estado"] for item in history] == [
        "PENDIENTE",
        "EN_PREPARACION",
        "LISTO",
        "ENTREGADO",
    ]

    print(
        "OK datos demo PostgreSQL/REST: 11 tablas, 4 categorías, 12 productos, "
        "4 mesas, 7 usuarios, 7 pedidos, 3 pagos, 3 entregas."
    )
    print(f"OK base: {connection['base']}/{connection['esquema']}; conteos: {counts}")
    print(f"OK reglas: {verification}")


if __name__ == "__main__":
    run()
