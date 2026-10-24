import unittest

from werkzeug.security import generate_password_hash

from app import create_app, seed_default_roles
from extensions import db
from mesas import EstadoMesa, Mesa
from models import (
    Categoria,
    EstadoPedido,
    Pedido,
    TipoUsuario,
    Usuario,
)
from producto import Producto


class PedidosApiTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"}
        )
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        seed_default_roles()

        self.mesero = self.create_user("MESERO", "mesero_pedidos")
        self.cliente = self.create_user("CLIENTE", "cliente_pedidos")
        self.cocina = self.create_user("COCINA", "cocina_pedidos")
        self.domiciliario = self.create_user("DOMICILIARIO", "domiciliario_pedidos")
        self.mesa = Mesa(numero_mesa=10, estado=EstadoMesa.LIBRE)
        self.categoria = Categoria(nombre="Platos", activo=True)
        db.session.add_all([self.mesa, self.categoria])
        db.session.flush()
        self.producto = Producto(
            nombre="Almuerzo",
            descripcion="Producto de prueba",
            precio="12500.00",
            activo=True,
            disponible=True,
            id_categoria=self.categoria.id_categoria,
        )
        db.session.add(self.producto)
        db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def create_user(self, role_name, login):
        role = db.session.scalar(
            db.select(TipoUsuario).where(TipoUsuario.descripcion == role_name)
        )
        user = Usuario(
            id_tipo_usuario=role.id_tipo_usuario,
            nombre=login.replace("_", " ").title(),
            usuario_login=login,
            contrasena_hash=generate_password_hash("ClaveSegura123"),
            activo=True,
        )
        db.session.add(user)
        db.session.flush()
        return user

    def create_salon_order(self):
        response = self.client.post(
            "/api/pedidos",
            json={
                "tipo": "SALON",
                "id_mesa": self.mesa.id_mesa,
                "id_mesero": self.mesero.id_usuario,
                "observaciones": "Sin cebolla",
            },
        )
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        return response.get_json()["datos"]

    def create_delivery_order(self):
        response = self.client.post(
            "/api/pedidos",
            json={
                "tipo": "DOMICILIO",
                "id_cliente": self.cliente.id_usuario,
                "direccion_entrega": "Calle 10 # 20-30",
                "telefono_contacto": "3001234567",
            },
        )
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        return response.get_json()["datos"]

    def add_product(self, order_id, quantity=2):
        response = self.client.post(
            f"/api/pedidos/{order_id}/detalles",
            json={"id_producto": self.producto.id_producto, "cantidad": quantity},
        )
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        return response.get_json()

    def advance_to_ready(self, order_id):
        for state in ("EN_PREPARACION", "LISTO"):
            response = self.client.patch(
                f"/api/pedidos/{order_id}/estado",
                json={
                    "estado": state,
                    "id_usuario_cambio": self.cocina.id_usuario,
                },
            )
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))

    def test_registra_pedido_salon_ocupa_mesa_y_permite_cancelar(self):
        order = self.create_salon_order()
        db.session.expire_all()
        self.assertEqual(db.session.get(Mesa, self.mesa.id_mesa).estado, EstadoMesa.OCUPADA)

        updated = self.client.patch(
            f"/api/pedidos/{order['id_pedido']}",
            json={"observaciones": "Mesa junto a la ventana"},
        )
        self.assertEqual(updated.status_code, 200)

        cancelled = self.client.delete(
            f"/api/pedidos/{order['id_pedido']}",
            json={
                "id_usuario_cambio": self.mesero.id_usuario,
                "observacion": "Cliente canceló antes de preparar.",
            },
        )
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(cancelled.get_json()["datos"]["estado"], "CANCELADO")
        db.session.expire_all()
        self.assertEqual(db.session.get(Mesa, self.mesa.id_mesa).estado, EstadoMesa.LIBRE)

    def test_registra_pedido_domicilio_y_datos_de_entrega(self):
        order = self.create_delivery_order()
        self.assertEqual(order["tipo"], "DOMICILIO")
        self.assertEqual(order["entrega"]["estado"], "PENDIENTE_ASIGNACION")
        self.assertEqual(order["entrega"]["direccion_entrega"], "Calle 10 # 20-30")

        missing = self.client.post(
            "/api/pedidos",
            json={"tipo": "DOMICILIO", "id_cliente": self.cliente.id_usuario},
        )
        self.assertEqual(missing.status_code, 400)

    def test_crud_detalle_recalcula_total(self):
        order = self.create_salon_order()
        created = self.add_product(order["id_pedido"], 2)
        detail_id = created["datos"]["id_detalle"]
        self.assertEqual(created["valor_total"], "25000.00")

        listed = self.client.get(f"/api/pedidos/{order['id_pedido']}/detalles")
        self.assertEqual(len(listed.get_json()["datos"]), 1)
        updated = self.client.patch(
            f"/api/pedidos/{order['id_pedido']}/detalles/{detail_id}",
            json={"cantidad": 3, "comentarios": "Tres porciones"},
        )
        self.assertEqual(updated.get_json()["valor_total"], "37500.00")

        deleted = self.client.delete(
            f"/api/pedidos/{order['id_pedido']}/detalles/{detail_id}"
        )
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.get_json()["valor_total"], "0.00")

    def test_detalle_rechaza_cantidad_y_producto_no_disponible(self):
        order = self.create_salon_order()
        invalid_quantity = self.client.post(
            f"/api/pedidos/{order['id_pedido']}/detalles",
            json={"id_producto": self.producto.id_producto, "cantidad": 0},
        )
        self.assertEqual(invalid_quantity.status_code, 400)

        self.producto.disponible = False
        db.session.commit()
        unavailable = self.client.post(
            f"/api/pedidos/{order['id_pedido']}/detalles",
            json={"id_producto": self.producto.id_producto, "cantidad": 1},
        )
        self.assertEqual(unavailable.status_code, 409)

    def test_cocina_filtra_actualiza_estado_y_registra_historial(self):
        order = self.create_salon_order()
        self.add_product(order["id_pedido"], 1)

        kitchen = self.client.get("/api/cocina/pedidos?estado=PENDIENTE")
        self.assertEqual(kitchen.status_code, 200)
        self.assertEqual(len(kitchen.get_json()["datos"]), 1)
        self.advance_to_ready(order["id_pedido"])

        delivered = self.client.patch(
            f"/api/pedidos/{order['id_pedido']}/estado",
            json={
                "estado": "ENTREGADO",
                "id_usuario_cambio": self.mesero.id_usuario,
            },
        )
        self.assertEqual(delivered.status_code, 200)
        history = self.client.get(f"/api/pedidos/{order['id_pedido']}/historial")
        self.assertEqual(
            [item["estado"] for item in history.get_json()["datos"]],
            ["PENDIENTE", "EN_PREPARACION", "LISTO", "ENTREGADO"],
        )

    def test_rechaza_transicion_por_rol_y_pedido_vacio(self):
        order = self.create_salon_order()
        forbidden = self.client.patch(
            f"/api/pedidos/{order['id_pedido']}/estado",
            json={
                "estado": "EN_PREPARACION",
                "id_usuario_cambio": self.cliente.id_usuario,
            },
        )
        self.assertEqual(forbidden.status_code, 403)

        empty = self.client.patch(
            f"/api/pedidos/{order['id_pedido']}/estado",
            json={
                "estado": "EN_PREPARACION",
                "id_usuario_cambio": self.cocina.id_usuario,
            },
        )
        self.assertEqual(empty.status_code, 409)
        self.assertEqual(empty.get_json()["error"]["codigo"], "ORDER_EMPTY")

    def test_asigna_domiciliario_y_finaliza_entrega_pedido(self):
        order = self.create_delivery_order()
        self.add_product(order["id_pedido"], 2)
        self.advance_to_ready(order["id_pedido"])

        assigned = self.client.patch(
            f"/api/pedidos/{order['id_pedido']}/domiciliario",
            json={"id_domiciliario": self.domiciliario.id_usuario},
        )
        self.assertEqual(assigned.status_code, 200)
        delivery_id = assigned.get_json()["datos"]["id_entrega"]
        for state in ("RECOGIDA", "EN_CAMINO", "ENTREGADA"):
            response = self.client.patch(
                f"/api/entregas/{delivery_id}/estado", json={"estado": state}
            )
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))

        db.session.expire_all()
        saved_order = db.session.get(Pedido, order["id_pedido"])
        self.assertEqual(saved_order.estado, EstadoPedido.ENTREGADO)
        self.assertEqual(saved_order.historial[-1].estado, EstadoPedido.ENTREGADO)

    def test_pago_debe_coincidir_con_total_del_pedido(self):
        order = self.create_salon_order()
        self.add_product(order["id_pedido"], 2)

        invalid = self.client.post(
            "/api/pagos",
            json={"id_pedido": order["id_pedido"], "metodo": "EFECTIVO", "valor": 1000},
        )
        valid = self.client.post(
            "/api/pagos",
            json={
                "id_pedido": order["id_pedido"],
                "metodo": "EFECTIVO",
                "valor": 25000,
            },
        )
        self.assertEqual(invalid.status_code, 409)
        self.assertEqual(invalid.get_json()["error"]["codigo"], "PAYMENT_AMOUNT_MISMATCH")
        self.assertEqual(valid.status_code, 201)


if __name__ == "__main__":
    unittest.main()
