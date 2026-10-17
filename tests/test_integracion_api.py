import unittest

from app import create_app, seed_default_roles
from extensions import db
from models import Categoria
from producto import Producto


class IntegracionApiTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            }
        )
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        seed_default_roles()
        self.client = self.app.test_client()

        self.category = Categoria(nombre="Platos fuertes", activo=True)
        db.session.add(self.category)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_aplicacion_comun_registra_rutas_sin_duplicados(self):
        registrations = []
        for rule in self.app.url_map.iter_rules():
            for method in rule.methods - {"HEAD", "OPTIONS"}:
                registrations.append((str(rule), method))

        self.assertEqual(len(registrations), len(set(registrations)))
        self.assertIn(("/api/categorias", "GET"), registrations)
        self.assertIn(("/mesas", "POST"), registrations)
        self.assertIn(("/productos", "POST"), registrations)

    def test_crud_funcional_de_mesas(self):
        created = self.client.post("/mesas", json={"numero_mesa": 10})
        self.assertEqual(created.status_code, 201)
        mesa_id = created.get_json()["id_mesa"]
        self.assertEqual(created.get_json()["estado"], "LIBRE")

        listed = self.client.get("/mesas?estado=libre")
        self.assertEqual(len(listed.get_json()), 1)
        self.assertEqual(self.client.get(f"/mesas/{mesa_id}").status_code, 200)

        updated = self.client.put(f"/mesas/{mesa_id}", json={"numero_mesa": 11})
        self.assertEqual(updated.get_json()["numero_mesa"], 11)

        changed = self.client.patch(
            f"/mesas/{mesa_id}/estado", json={"estado": "ocupada"}
        )
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(changed.get_json()["estado"], "OCUPADA")

    def test_mesas_rechazan_duplicados_y_estados_invalidos(self):
        self.client.post("/mesas", json={"numero_mesa": 1})
        duplicate = self.client.post("/mesas", json={"numero_mesa": 1})
        invalid = self.client.patch(
            "/mesas/1/estado", json={"estado": "RESERVADA"}
        )

        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(invalid.status_code, 400)

    def test_crud_funcional_de_productos(self):
        created = self.client.post(
            "/productos",
            json={
                "nombre": "Bandeja paisa",
                "descripcion": "Plato tradicional",
                "precio": 25000,
                "id_categoria": self.category.id_categoria,
            },
        )
        self.assertEqual(created.status_code, 201)
        product_id = created.get_json()["id_producto"]
        self.assertTrue(created.get_json()["activo"])

        listed = self.client.get(
            f"/productos?id_categoria={self.category.id_categoria}"
        )
        self.assertEqual(len(listed.get_json()), 1)

        updated = self.client.put(
            f"/productos/{product_id}", json={"precio": "26000.50"}
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["precio"], "26000.50")

        hidden = self.client.patch(
            f"/productos/{product_id}/disponibilidad",
            json={"disponible": False},
        )
        self.assertFalse(hidden.get_json()["disponible"])
        self.assertEqual(self.client.get("/productos").get_json(), [])

        deleted = self.client.delete(f"/productos/{product_id}")
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(deleted.get_json()["datos"]["activo"])

    def test_productos_validan_duplicado_categoria_y_reactivacion_indebida(self):
        payload = {
            "nombre": "Sopa",
            "precio": 12000,
            "id_categoria": self.category.id_categoria,
        }
        created = self.client.post("/productos", json=payload)
        product_id = created.get_json()["id_producto"]

        payload["nombre"] = "sopa"
        duplicate = self.client.post("/productos", json=payload)
        self.assertEqual(duplicate.status_code, 409)

        self.client.delete(f"/productos/{product_id}")
        reactivation = self.client.patch(
            f"/productos/{product_id}/disponibilidad",
            json={"disponible": True},
        )
        self.assertEqual(reactivation.status_code, 409)

        invalid_price = self.client.post(
            "/productos",
            json={
                "nombre": "Precio inválido",
                "precio": True,
                "id_categoria": self.category.id_categoria,
            },
        )
        self.assertEqual(invalid_price.status_code, 400)

        self.category.activo = False
        db.session.commit()
        unavailable = self.client.post(
            "/productos",
            json={
                "nombre": "Ensalada",
                "precio": 10000,
                "id_categoria": self.category.id_categoria,
            },
        )
        self.assertEqual(unavailable.status_code, 422)

    def test_modelo_producto_usa_columnas_del_documento_oficial(self):
        self.assertEqual(
            set(Producto.__table__.columns.keys()),
            {
                "id_producto",
                "nombre_producto",
                "descripcion_producto",
                "precio_producto",
                "activo",
                "disponible",
                "id_categoria",
            },
        )

    def test_menu_oculta_productos_de_categorias_inactivas(self):
        created = self.client.post(
            "/productos",
            json={
                "nombre": "Producto de categoría desactivada",
                "precio": 9000,
                "id_categoria": self.category.id_categoria,
            },
        )
        self.assertEqual(created.status_code, 201)

        self.category.activo = False
        db.session.commit()

        listed = self.client.get(
            f"/productos?id_categoria={self.category.id_categoria}"
        )
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.get_json(), [])


if __name__ == "__main__":
    unittest.main()
