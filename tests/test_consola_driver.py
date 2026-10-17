import unittest
from unittest.mock import patch

import consola_driver


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


if __name__ == "__main__":
    unittest.main()
