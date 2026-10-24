import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import consola
from app import create_app, seed_default_roles
from extensions import db
from functionalities import FUNCTIONALITY_NAMES, functionality_label
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

    def test_menu_principal_muestra_las_quince_funcionalidades(self):
        salida = io.StringIO()
        with patch("builtins.input", side_effect=["0"]), redirect_stdout(salida):
            consola.ejecutar_menu_orm()

        texto = salida.getvalue()
        self.assertIn("SQLALCHEMY ORM", texto)
        opciones = consola.opciones_principales_orm()
        for numero, _nombre in enumerate(FUNCTIONALITY_NAMES, start=1):
            self.assertIn(functionality_label(numero), texto)
            self.assertTrue(callable(opciones[f"{numero:02d}"]))
        self.assertEqual(len(opciones), 15)

    def test_menu_inicial_separa_driver_y_orm(self):
        salida = io.StringIO()
        with patch("builtins.input", side_effect=["0"]), redirect_stdout(salida):
            consola.ejecutar_menu()

        texto = salida.getvalue()
        self.assertIn("CRUD directo con el driver psycopg", texto)
        self.assertIn("CRUD mediante SQLAlchemy ORM", texto)


if __name__ == "__main__":
    unittest.main()
