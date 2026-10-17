import unittest

from app import create_app, seed_default_roles
from extensions import db


class CategoriasApiTestCase(unittest.TestCase):
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

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_crud_y_desactivacion_logica(self):
        created = self.client.post("/api/categorias", json={"nombre": "Bebidas"})
        self.assertEqual(created.status_code, 201)
        category_id = created.get_json()["datos"]["id_categoria"]

        listed = self.client.get("/api/categorias")
        self.assertEqual([item["nombre"] for item in listed.get_json()["datos"]], ["Bebidas"])

        updated = self.client.patch(
            f"/api/categorias/{category_id}", json={"nombre": "Bebidas frías"}
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["datos"]["nombre"], "Bebidas frías")

        deleted = self.client.delete(f"/api/categorias/{category_id}")
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(deleted.get_json()["datos"]["activo"])
        self.assertEqual(self.client.get("/api/categorias").get_json()["datos"], [])

        all_categories = self.client.get("/api/categorias?incluir_inactivas=true")
        self.assertEqual(len(all_categories.get_json()["datos"]), 1)

    def test_rechaza_nombre_duplicado_sin_distinguir_mayusculas(self):
        self.client.post("/api/categorias", json={"nombre": "Postres"})
        duplicate = self.client.post("/api/categorias", json={"nombre": "postres"})

        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(duplicate.get_json()["error"]["codigo"], "CATEGORY_NAME_EXISTS")

    def test_valida_json_y_campos_obligatorios(self):
        wrong_type = self.client.post(
            "/api/categorias", data="nombre=Bebidas", content_type="text/plain"
        )
        missing = self.client.post("/api/categorias", json={})

        self.assertEqual(wrong_type.status_code, 415)
        self.assertEqual(missing.status_code, 400)

    def test_salud_confirma_conexion(self):
        response = self.client.get("/api/salud")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["base_datos"], "conectada")


if __name__ == "__main__":
    unittest.main()
