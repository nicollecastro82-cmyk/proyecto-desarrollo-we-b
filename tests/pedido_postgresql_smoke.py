"""Prueba HTTP/ORM del flujo completo de pedidos contra PostgreSQL real.

Todos los registros creados llevan un sufijo aleatorio y se eliminan al terminar.
No modifica ni elimina datos preexistentes.
"""

from uuid import uuid4

from app import app
from extensions import db
from mesas import Mesa
from models import Entrega, Pago, Pedido, Usuario
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
    suffix = uuid4().hex[:10]
    order_ids = []
    user_ids = []
    product_id = None
    table_id = None

    try:
        expect(client.get("/api/salud"), 200, "salud PostgreSQL")
        categories = expect(
            client.get("/api/categorias"), 200, "categorias activas"
        )["datos"]
        if not categories:
            raise AssertionError("Se requiere al menos una categoria activa.")
        category_id = categories[0]["id_categoria"]

        roles = expect(client.get("/api/tipos-usuario"), 200, "roles")["datos"]
        role_ids = {role["descripcion"]: role["id_tipo_usuario"] for role in roles}

        def create_user(role):
            login = f"smoke_{role.lower()}_{suffix}"
            data = expect(
                client.post(
                    "/api/usuarios",
                    json={
                        "id_tipo_usuario": role_ids[role],
                        "nombre": f"Temporal {role} {suffix}",
                        "usuario_login": login,
                        "contrasena": "ClaveSegura123",
                        "correo": f"{login}@example.com",
                    },
                ),
                201,
                f"crear usuario {role}",
            )["datos"]
            user_ids.append(data["id_usuario"])
            return data["id_usuario"], login

        waiter_id, waiter_login = create_user("MESERO")
        kitchen_id, _ = create_user("COCINA")
        client_id, _ = create_user("CLIENTE")
        courier_id, _ = create_user("DOMICILIARIO")
        expect(
            client.post(
                "/api/auth/login",
                json={
                    "usuario_login": waiter_login,
                    "contrasena": "ClaveSegura123",
                },
            ),
            200,
            "iniciar sesion",
        )

        product = expect(
            client.post(
                "/productos",
                json={
                    "nombre": f"Producto pedido temporal {suffix}",
                    "descripcion": "Prueba controlada PostgreSQL",
                    "precio": "12500.00",
                    "id_categoria": category_id,
                },
            ),
            201,
            "crear producto temporal",
        )
        product_id = product["id_producto"]

        table_number = 700_000_000 + int(suffix[:6], 16) % 100_000_000
        table = expect(
            client.post("/mesas", json={"numero_mesa": table_number}),
            201,
            "crear mesa temporal",
        )
        table_id = table["id_mesa"]

        salon = expect(
            client.post(
                "/api/pedidos",
                json={
                    "tipo": "SALON",
                    "id_mesa": table_id,
                    "id_mesero": waiter_id,
                    "observaciones": f"Smoke {suffix}",
                },
            ),
            201,
            "registrar pedido en salon",
        )["datos"]
        salon_id = salon["id_pedido"]
        order_ids.append(salon_id)
        expect(
            client.patch(
                f"/api/pedidos/{salon_id}",
                json={"observaciones": "Actualizado desde smoke"},
            ),
            200,
            "actualizar pedido",
        )
        detail = expect(
            client.post(
                f"/api/pedidos/{salon_id}/detalles",
                json={"id_producto": product_id, "cantidad": 2},
            ),
            201,
            "agregar detalle y recalcular total",
        )
        if detail["valor_total"] != "25000.00":
            raise AssertionError("El total del pedido no fue recalculado.")
        detail_id = detail["datos"]["id_detalle"]
        expect(
            client.put(
                f"/api/pedidos/{salon_id}/detalles/{detail_id}",
                json={"cantidad": 2, "comentarios": "Actualizado"},
            ),
            200,
            "actualizar detalle",
        )
        expect(
            client.get(f"/api/pedidos/{salon_id}/detalles"),
            200,
            "consultar detalle",
        )
        expect(
            client.get("/api/cocina/pedidos?estado=PENDIENTE"),
            200,
            "filtrar pedidos de Cocina",
        )
        expect(
            client.patch(
                f"/api/pedidos/{salon_id}/estado",
                json={"estado": "EN_PREPARACION", "id_usuario_cambio": client_id},
            ),
            403,
            "rechazar rol no autorizado",
        )
        for state in ("EN_PREPARACION", "LISTO"):
            expect(
                client.patch(
                    f"/api/pedidos/{salon_id}/estado",
                    json={"estado": state, "id_usuario_cambio": kitchen_id},
                ),
                200,
                f"cambiar pedido a {state}",
            )

        payment = expect(
            client.post(
                "/api/pagos",
                json={
                    "id_pedido": salon_id,
                    "metodo": "EFECTIVO",
                    "valor": "25000.00",
                },
            ),
            201,
            "registrar pago por el total",
        )["datos"]
        expect(
            client.patch(
                f"/api/pagos/{payment['id_pago']}/estado",
                json={"estado": "APROBADO", "id_usuario_confirma": waiter_id},
            ),
            200,
            "confirmar pago",
        )
        expect(
            client.patch(
                f"/api/pedidos/{salon_id}/estado",
                json={"estado": "ENTREGADO", "id_usuario_cambio": waiter_id},
            ),
            200,
            "entregar pedido en salon",
        )
        history = expect(
            client.get(f"/api/pedidos/{salon_id}/historial"),
            200,
            "consultar historial",
        )["datos"]
        if [item["estado"] for item in history] != [
            "PENDIENTE",
            "EN_PREPARACION",
            "LISTO",
            "ENTREGADO",
        ]:
            raise AssertionError("El historial no contiene la secuencia esperada.")

        delivery_order = expect(
            client.post(
                "/api/pedidos",
                json={
                    "tipo": "DOMICILIO",
                    "id_cliente": client_id,
                    "direccion_entrega": "Calle temporal 10 # 20-30",
                    "telefono_contacto": "3000000000",
                },
            ),
            201,
            "registrar pedido a domicilio",
        )["datos"]
        delivery_order_id = delivery_order["id_pedido"]
        order_ids.append(delivery_order_id)
        delivery_id = delivery_order["entrega"]["id_entrega"]
        expect(
            client.post(
                f"/api/pedidos/{delivery_order_id}/detalles",
                json={"id_producto": product_id, "cantidad": 1},
            ),
            201,
            "agregar detalle al domicilio",
        )
        for state in ("EN_PREPARACION", "LISTO"):
            expect(
                client.patch(
                    f"/api/pedidos/{delivery_order_id}/estado",
                    json={"estado": state, "id_usuario_cambio": kitchen_id},
                ),
                200,
                f"domicilio a {state}",
            )
        expect(
            client.patch(
                f"/api/pedidos/{delivery_order_id}/domiciliario",
                json={"id_domiciliario": courier_id},
            ),
            200,
            "asignar domiciliario",
        )
        for state in ("RECOGIDA", "EN_CAMINO", "ENTREGADA"):
            expect(
                client.patch(
                    f"/api/entregas/{delivery_id}/estado", json={"estado": state}
                ),
                200,
                f"entrega a {state}",
            )
        final = expect(
            client.get(f"/api/pedidos/{delivery_order_id}"),
            200,
            "consultar estado final",
        )["datos"]
        if final["estado"] != "ENTREGADO":
            raise AssertionError("El pedido a domicilio no quedo ENTREGADO.")

        print("Prueba PostgreSQL integrada completada correctamente.")
    finally:
        with app.app_context():
            db.session.rollback()
            for order_id in order_ids:
                order = db.session.get(Pedido, order_id)
                if order is None:
                    continue
                payment = db.session.scalar(
                    db.select(Pago).where(Pago.id_pedido == order_id)
                )
                delivery = db.session.scalar(
                    db.select(Entrega).where(Entrega.id_pedido == order_id)
                )
                if payment is not None:
                    db.session.delete(payment)
                if delivery is not None:
                    db.session.delete(delivery)
                db.session.flush()
                db.session.delete(order)
            db.session.flush()
            if product_id is not None:
                product = db.session.get(Producto, product_id)
                if product is not None:
                    db.session.delete(product)
            if table_id is not None:
                table = db.session.get(Mesa, table_id)
                if table is not None:
                    db.session.delete(table)
            for user_id in user_ids:
                user = db.session.get(Usuario, user_id)
                if user is not None:
                    db.session.delete(user)
            db.session.commit()
            print("Limpieza OK: solo se eliminaron los registros temporales del smoke.")


if __name__ == "__main__":
    run()
