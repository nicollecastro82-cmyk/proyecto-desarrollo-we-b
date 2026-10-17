import unittest

from werkzeug.security import generate_password_hash

from app import create_app, seed_default_roles
from extensions import db
from models import TipoUsuario, Usuario


class HorariosApiTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"}
        )
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        seed_default_roles()
        self.client = self.app.test_client()
        self.employee = self.create_user("COCINA", "cocina")
        self.client_user = self.create_user("CLIENTE", "cliente")

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
        db.session.commit()
        return user

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def payload(self, start="08:00", end="16:00"):
        return {
            "id_usuario": self.employee.id_usuario,
            "fecha": "2026-10-20",
            "hora_inicio": start,
            "hora_fin": end,
            "observacion": "Turno de cocina",
        }

    def test_crud_horario(self):
        created = self.client.post("/api/horarios", json=self.payload())
        self.assertEqual(created.status_code, 201)
        schedule_id = created.get_json()["datos"]["id_horario"]

        listed = self.client.get(
            f"/api/horarios?id_usuario={self.employee.id_usuario}&fecha=2026-10-20"
        )
        self.assertEqual(len(listed.get_json()["datos"]), 1)

        updated = self.client.patch(
            f"/api/horarios/{schedule_id}", json={"hora_fin": "17:00"}
        )
        self.assertEqual(updated.get_json()["datos"]["hora_fin"], "17:00")
        self.assertEqual(self.client.delete(f"/api/horarios/{schedule_id}").status_code, 200)

    def test_rechaza_solapamiento(self):
        self.client.post("/api/horarios", json=self.payload())
        overlap = self.client.post("/api/horarios", json=self.payload("15:00", "18:00"))
        adjacent = self.client.post("/api/horarios", json=self.payload("16:00", "18:00"))

        self.assertEqual(overlap.status_code, 409)
        self.assertEqual(overlap.get_json()["error"]["codigo"], "SCHEDULE_OVERLAP")
        self.assertEqual(adjacent.status_code, 201)

    def test_rechaza_rango_invalido(self):
        response = self.client.post("/api/horarios", json=self.payload("16:00", "08:00"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"]["codigo"], "INVALID_TIME_RANGE")

    def test_rechaza_usuario_cliente(self):
        payload = self.payload()
        payload["id_usuario"] = self.client_user.id_usuario
        response = self.client.post("/api/horarios", json=payload)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()["error"]["codigo"], "USER_IS_NOT_EMPLOYEE")


if __name__ == "__main__":
    unittest.main()
