import unittest

from werkzeug.security import generate_password_hash

from app import create_app, seed_default_roles
from extensions import db
from models import EstadoPedido, Pedido, TipoPedido, TipoUsuario, Usuario


class PagosEntregasApiTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"}
        )
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        seed_default_roles()
        db.session.add_all(
            [
                Pedido(
                    id_pedido=1,
                    tipo=TipoPedido.DOMICILIO,
                    estado=EstadoPedido.PENDIENTE,
                ),
                Pedido(
                    id_pedido=2,
                    tipo=TipoPedido.SALON,
                    estado=EstadoPedido.PENDIENTE,
                ),
                Pedido(
                    id_pedido=3,
                    tipo=TipoPedido.DOMICILIO,
                    estado=EstadoPedido.LISTO,
                ),
            ]
        )
        self.confirmer = self.create_user("MESERO", "mesero")
        self.courier = self.create_user("DOMICILIARIO", "domiciliario")
        db.session.commit()
        self.client = self.app.test_client()

    def create_user(self, role_name, login):
        role = db.session.scalar(
            db.select(TipoUsuario).where(TipoUsuario.descripcion == role_name)
        )
        user = Usuario(
            id_tipo_usuario=role.id_tipo_usuario,
            nombre=login.title(),
            usuario_login=login,
            contrasena_hash=generate_password_hash("ClaveSegura123"),
            activo=True,
        )
        db.session.add(user)
        db.session.flush()
        return user

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_crud_pago_y_aprobacion(self):
        created = self.client.post(
            "/api/pagos", json={"id_pedido": 1, "metodo": "PSE", "valor": 25000}
        )
        self.assertEqual(created.status_code, 201)
        payment_id = created.get_json()["datos"]["id_pago"]

        updated = self.client.patch(f"/api/pagos/{payment_id}", json={"valor": "26000.50"})
        self.assertEqual(updated.get_json()["datos"]["valor"], "26000.50")

        approved = self.client.patch(
            f"/api/pagos/{payment_id}/estado",
            json={
                "estado": "APROBADO",
                "id_usuario_confirma": self.confirmer.id_usuario,
                "referencia_transaccion": "PSE-001",
            },
        )
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.get_json()["datos"]["estado"], "APROBADO")
        self.assertEqual(self.client.delete(f"/api/pagos/{payment_id}").status_code, 409)

    def test_rechaza_pago_duplicado_y_valor_invalido(self):
        self.client.post(
            "/api/pagos", json={"id_pedido": 1, "metodo": "EFECTIVO", "valor": 10000}
        )
        duplicate = self.client.post(
            "/api/pagos", json={"id_pedido": 1, "metodo": "EFECTIVO", "valor": 10000}
        )
        invalid = self.client.post(
            "/api/pagos", json={"id_pedido": 3, "metodo": "EFECTIVO", "valor": 0}
        )
        not_finite = self.client.post(
            "/api/pagos",
            json={"id_pedido": 3, "metodo": "EFECTIVO", "valor": "NaN"},
        )
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(not_finite.status_code, 400)

    def test_crud_entrega_y_flujo_de_estados(self):
        created = self.client.post(
            "/api/entregas",
            json={
                "id_pedido": 1,
                "direccion_entrega": "Calle 10 # 20-30",
                "telefono_contacto": "3001234567",
            },
        )
        self.assertEqual(created.status_code, 201)
        delivery_id = created.get_json()["datos"]["id_entrega"]
        self.assertEqual(
            created.get_json()["datos"]["estado"], "PENDIENTE_ASIGNACION"
        )

        assigned = self.client.patch(
            f"/api/entregas/{delivery_id}/estado",
            json={"estado": "ASIGNADA", "id_domiciliario": self.courier.id_usuario},
        )
        self.assertEqual(assigned.status_code, 200)
        for state in ("RECOGIDA", "EN_CAMINO", "ENTREGADA"):
            response = self.client.patch(
                f"/api/entregas/{delivery_id}/estado", json={"estado": state}
            )
            self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.get_json()["datos"]["fecha_entrega"])
        self.assertEqual(self.client.delete(f"/api/entregas/{delivery_id}").status_code, 409)

    def test_rechaza_entrega_para_pedido_de_salon(self):
        response = self.client.post(
            "/api/entregas",
            json={
                "id_pedido": 2,
                "direccion_entrega": "Calle 10 # 20-30",
                "telefono_contacto": "3001234567",
            },
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()["error"]["codigo"], "ORDER_IS_NOT_DELIVERY")

    def test_rechaza_pago_para_pedido_inexistente(self):
        response = self.client.post(
            "/api/pagos",
            json={"id_pedido": 999, "metodo": "EFECTIVO", "valor": 10000},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.get_json()["error"]["codigo"], "ORDER_NOT_FOUND"
        )

    def test_modelo_pedido_relaciona_pago_y_entrega(self):
        payment = self.client.post(
            "/api/pagos", json={"id_pedido": 1, "metodo": "EFECTIVO", "valor": 10000}
        )
        delivery = self.client.post(
            "/api/entregas",
            json={
                "id_pedido": 1,
                "direccion_entrega": "Calle 10 # 20-30",
                "telefono_contacto": "3001234567",
            },
        )

        self.assertEqual(payment.status_code, 201)
        self.assertEqual(delivery.status_code, 201)
        db.session.expire_all()
        order = db.session.get(Pedido, 1)
        self.assertEqual(order.pago.id_pedido, order.id_pedido)
        self.assertEqual(order.entrega.id_pedido, order.id_pedido)


if __name__ == "__main__":
    unittest.main()
