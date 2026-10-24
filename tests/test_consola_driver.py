import unittest
from io import StringIO
from unittest.mock import MagicMock, patch

import consola_driver
from functionalities import FUNCTIONALITY_NAMES, functionality_label


class ConsolaDriverTestCase(unittest.TestCase):
    def test_url_de_sqlalchemy_se_convierte_para_psycopg(self):
        with patch.dict(
            "os.environ",
            {
                "DATABASE_URL": (
                    "postgresql+psycopg://postgres:clave@localhost:5433/"
                    "polirestaurante"
                )
            },
        ):
            self.assertEqual(
                consola_driver.url_para_psycopg(),
                "postgresql://postgres:clave@localhost:5433/polirestaurante",
            )

    def test_url_es_obligatoria(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "DATABASE_URL"):
                consola_driver.url_para_psycopg()

    def test_menu_driver_muestra_las_quince_funcionalidades(self):
        connection = MagicMock()
        with (
            patch.object(consola_driver, "conectar", return_value=connection),
            patch.object(consola_driver, "consultar"),
            patch("builtins.input", return_value="0"),
            patch("sys.stdout", new_callable=StringIO) as output,
        ):
            consola_driver.ejecutar_menu_driver()

        text = output.getvalue()
        self.assertIn("DRIVER DE PYTHON", text)
        opciones = consola_driver.opciones_principales_driver()
        self.assertEqual(len(opciones), 15)
        for numero, nombre in enumerate(FUNCTIONALITY_NAMES, start=1):
            self.assertIn(functionality_label(numero), text)
            self.assertEqual(opciones[f"{numero:02d}"][0], nombre)
        connection.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
