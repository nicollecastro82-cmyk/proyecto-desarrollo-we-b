"""Prueba temporal de Pedido, Pago y Entrega contra PostgreSQL real."""

from uuid import uuid4

from app import app
from extensions import db
from models import Entrega, EstadoPedido, Pago, Pedido, TipoPedido


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
    order_id = None

    try:
        expect(client.get("/api/salud"), 200, "salud PostgreSQL")
        with app.app_context():
            order = Pedido(
                tipo=TipoPedido.DOMICILIO,
                estado=EstadoPedido.PENDIENTE,
                valor_total="25000.00",
                observaciones=f"Prueba temporal Pedido {suffix}",
            )
            db.session.add(order)
            db.session.commit()
            order_id = order.id_pedido
            print(f"OK crear Pedido ORM: id={order_id}")

        payment = expect(
            client.post(
                "/api/pagos",
                json={"id_pedido": order_id, "metodo": "EFECTIVO", "valor": 25000},
            ),
            201,
            "crear Pago con FK real",
        )["datos"]
        expect(client.get(f"/api/pagos/{payment['id_pago']}"), 200, "consultar Pago")
        expect(
            client.patch(f"/api/pagos/{payment['id_pago']}", json={"valor": 26000}),
            200,
            "actualizar Pago",
        )

        delivery = expect(
            client.post(
                "/api/entregas",
                json={
                    "id_pedido": order_id,
                    "direccion_entrega": "Dirección temporal de integración",
                    "telefono_contacto": "3000000000",
                },
            ),
            201,
            "crear Entrega con FK real",
        )["datos"]
        expect(
            client.get(f"/api/entregas/{delivery['id_entrega']}"),
            200,
            "consultar Entrega",
        )
        expect(
            client.patch(
                f"/api/entregas/{delivery['id_entrega']}",
                json={"direccion_entrega": "Dirección temporal actualizada"},
            ),
            200,
            "actualizar Entrega",
        )

        expect(
            client.delete(f"/api/pagos/{payment['id_pago']}"),
            200,
            "eliminar Pago pendiente",
        )
        expect(
            client.delete(f"/api/entregas/{delivery['id_entrega']}"),
            200,
            "eliminar Entrega pendiente",
        )
        print("Prueba PostgreSQL de Pedido completada correctamente.")
    finally:
        if order_id is not None:
            with app.app_context():
                db.session.rollback()
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
                order = db.session.get(Pedido, order_id)
                if order is not None:
                    db.session.delete(order)
                db.session.commit()
                print(f"Limpieza completada: Pedido temporal {order_id} eliminado.")


if __name__ == "__main__":
    run()
