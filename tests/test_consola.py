import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import consola
from app import create_app, seed_default_roles
from extensions import db
from models import Categoria


class ConsolaYinaTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"}
        )
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        seed_default_roles()
        self.cliente_anterior = consola.cliente_api
        consola.cliente_api = self.app.test_client()

    def tearDown(self):
        consola.cliente_api = self.cliente_anterior
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_titulo_no_muestra_lineas_de_decoracion(self):
        salida = io.StringIO()
        with redirect_stdout(salida):
            consola.titulo("POLIRESTAURANTE")

        self.assertEqual(salida.getvalue(), "\nPOLIRESTAURANTE\n")

    def test_menu_de_categorias_ejecuta_crud_mediante_la_api(self):
        entradas = [
            "1",  # menú principal: Categorías
            "1", "Bebidas", "s",  # crear
            "2",  # listar activas
            "6", "1", "Bebidas frías", "",  # actualizar nombre
            "8", "1", "s",  # eliminación lógica
            "0",  # volver
            "0",  # salir
        ]
        salida = io.StringIO()
        with patch("builtins.input", side_effect=entradas), redirect_stdout(salida):
            consola.ejecutar_menu_orm()

        db.session.expire_all()
        categoria = db.session.get(Categoria, 1)
        self.assertEqual(categoria.nombre, "Bebidas frías")
        self.assertFalse(categoria.activo)
        self.assertIn("HTTP 201", salida.getvalue())
        self.assertIn("Categoría desactivada correctamente", salida.getvalue())

    def test_menu_principal_abre_las_cinco_funcionalidades(self):
        entradas = [
            "1", "0",  # Categorías
            "2", "1", "0", "2", "0", "0",  # Roles y Usuarios
            "3", "0",  # Horarios
            "4", "0",  # Pagos
            "5", "0",  # Entregas
            "0",
        ]
        salida = io.StringIO()
        with patch("builtins.input", side_effect=entradas), redirect_stdout(salida):
            consola.ejecutar_menu_orm()

        texto = salida.getvalue()
        self.assertIn("CRUD DE CATEGORÍAS", texto)
        self.assertIn("CRUD DE ROLES", texto)
        self.assertIn("CRUD DE USUARIOS", texto)
        self.assertIn("CRUD DE HORARIOS", texto)
        self.assertIn("CRUD DE PAGOS", texto)
        self.assertIn("CRUD DE ENTREGAS", texto)

    def test_menu_inicial_separa_driver_y_orm(self):
        salida = io.StringIO()
        with patch("builtins.input", side_effect=["0"]), redirect_stdout(salida):
            consola.ejecutar_menu()

        texto = salida.getvalue()
        self.assertIn("CRUD directo con el driver psycopg", texto)
        self.assertIn("CRUD mediante SQLAlchemy ORM", texto)


if __name__ == "__main__":
    unittest.main()
