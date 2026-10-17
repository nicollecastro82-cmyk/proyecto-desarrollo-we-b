import unittest

from app import create_app, seed_default_roles
from extensions import db
from models import TipoUsuario


class UsuariosApiTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"}
        )
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        seed_default_roles()
        self.client = self.app.test_client()
        self.admin_role = db.session.scalar(
            db.select(TipoUsuario).where(TipoUsuario.descripcion == "ADMINISTRADOR")
        )

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def user_payload(self, login="yina"):
        return {
            "id_tipo_usuario": self.admin_role.id_tipo_usuario,
            "nombre": "Yina Ardila",
            "usuario_login": login,
            "contrasena": "ClaveSegura123",
            "correo": f"{login}@example.com",
            "telefono": "3001234567",
        }

    def test_roles_iniciales_y_crud_de_rol(self):
        initial = self.client.get("/api/tipos-usuario").get_json()["datos"]
        self.assertEqual(len(initial), 5)

        created = self.client.post(
            "/api/tipos-usuario", json={"descripcion": "SUPERVISOR"}
        )
        self.assertEqual(created.status_code, 201)
        role_id = created.get_json()["datos"]["id_tipo_usuario"]
        updated = self.client.patch(
            f"/api/tipos-usuario/{role_id}", json={"descripcion": "AUDITOR"}
        )
        self.assertEqual(updated.get_json()["datos"]["descripcion"], "AUDITOR")
        self.assertEqual(self.client.delete(f"/api/tipos-usuario/{role_id}").status_code, 200)

    def test_crea_usuario_sin_exponer_hash_y_valida_login(self):
        created = self.client.post("/api/usuarios", json=self.user_payload())
        self.assertEqual(created.status_code, 201)
        self.assertNotIn("contrasena_hash", created.get_json()["datos"])

        valid_login = self.client.post(
            "/api/auth/login",
            json={"usuario_login": "YINA", "contrasena": "ClaveSegura123"},
        )
        invalid_login = self.client.post(
            "/api/auth/login",
            json={"usuario_login": "yina", "contrasena": "incorrecta"},
        )
        self.assertEqual(valid_login.status_code, 200)
        self.assertEqual(invalid_login.status_code, 401)

    def test_rechaza_usuario_y_correo_duplicados(self):
        self.client.post("/api/usuarios", json=self.user_payload())
        duplicate = self.client.post("/api/usuarios", json=self.user_payload("YINA"))
        self.assertEqual(duplicate.status_code, 409)

    def test_desactivacion_logica_impide_login(self):
        created = self.client.post("/api/usuarios", json=self.user_payload())
        user_id = created.get_json()["datos"]["id_usuario"]
        deleted = self.client.delete(f"/api/usuarios/{user_id}")
        denied = self.client.post(
            "/api/auth/login",
            json={"usuario_login": "yina", "contrasena": "ClaveSegura123"},
        )
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(denied.status_code, 403)

    def test_no_elimina_rol_en_uso(self):
        role = self.client.post(
            "/api/tipos-usuario", json={"descripcion": "SUPERVISOR"}
        ).get_json()["datos"]
        payload = self.user_payload()
        payload["id_tipo_usuario"] = role["id_tipo_usuario"]
        self.client.post("/api/usuarios", json=payload)
        response = self.client.delete(f"/api/tipos-usuario/{role['id_tipo_usuario']}")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"]["codigo"], "ROLE_IN_USE")

    def test_roles_base_son_inmutables(self):
        response = self.client.delete(
            f"/api/tipos-usuario/{self.admin_role.id_tipo_usuario}"
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.get_json()["error"]["codigo"], "SYSTEM_ROLE_IMMUTABLE"
        )


if __name__ == "__main__":
    unittest.main()
