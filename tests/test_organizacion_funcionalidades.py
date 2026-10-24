import json
import re
import unittest
from pathlib import Path

import consola
import consola_driver
from functionalities import FUNCTIONALITY_NAMES, functionality_label


ROOT = Path(__file__).resolve().parents[1]
COLLECTION = (
    ROOT / "postman" / "PoliRestaurante-15-Funcionalidades.postman_collection.json"
)
POSTMAN_YAML = (
    ROOT
    / "postman"
    / "postman"
    / "collections"
    / "PoliRestaurante — 15 Funcionalidades"
)
POSTMAN_YAML_ENVIRONMENT = (
    ROOT
    / "postman"
    / "postman"
    / "environments"
    / "PoliRestaurante local.environment.yaml"
)


class OrganizacionFuncionalidadesTestCase(unittest.TestCase):
    def test_las_tres_interfaces_tienen_los_mismos_quince_nombres(self):
        collection = json.loads(COLLECTION.read_text(encoding="utf-8"))
        expected = [functionality_label(number) for number in range(1, 16)]

        self.assertEqual(collection["info"]["name"], "PoliRestaurante — 15 Funcionalidades")
        self.assertEqual([item["name"] for item in collection["item"]], expected)
        self.assertEqual(len(collection["item"]), 15)
        self.assertTrue(all(folder["item"] for folder in collection["item"]))

        driver_options = consola_driver.opciones_principales_driver()
        self.assertEqual(list(driver_options), [f"{number:02d}" for number in range(1, 16)])
        self.assertEqual(
            [driver_options[key][0] for key in driver_options],
            list(FUNCTIONALITY_NAMES),
        )

        orm_options = consola.opciones_principales_orm()
        self.assertEqual(list(orm_options), [f"{number:02d}" for number in range(1, 16)])
        self.assertEqual(len(orm_options), 15)

    def test_todas_las_solicitudes_postman_tienen_metodo_url_y_prueba(self):
        collection = json.loads(COLLECTION.read_text(encoding="utf-8"))
        requests = [request for folder in collection["item"] for request in folder["item"]]

        self.assertGreater(len(requests), 15)
        for item in requests:
            self.assertIn(item["request"]["method"], {"GET", "POST", "PUT", "PATCH", "DELETE"})
            self.assertTrue(item["request"]["url"].startswith("{{baseUrl}}"))
            test_events = [event for event in item.get("event", []) if event["listen"] == "test"]
            self.assertTrue(test_events, item["name"])

    def test_workspace_yaml_coincide_con_la_coleccion_y_el_ambiente_json(self):
        expected_folders = [functionality_label(number) for number in range(1, 16)]
        yaml_folders = sorted(
            path.name
            for path in POSTMAN_YAML.iterdir()
            if path.is_dir() and path.name[:2].isdigit()
        )
        self.assertEqual(yaml_folders, expected_folders)
        collection = json.loads(COLLECTION.read_text(encoding="utf-8"))
        request_count = sum(len(folder["item"]) for folder in collection["item"])
        self.assertEqual(len(list(POSTMAN_YAML.rglob("*.request.yaml"))), request_count)

        json_environment = json.loads(
            (ROOT / "postman" / "PoliRestaurante-local.postman_environment.json")
            .read_text(encoding="utf-8")
        )
        json_keys = {variable["key"] for variable in json_environment["values"]}
        yaml_text = POSTMAN_YAML_ENVIRONMENT.read_text(encoding="utf-8")
        yaml_keys = re.findall(r"^  - key: (.+)$", yaml_text, flags=re.MULTILINE)

        self.assertEqual(len(yaml_keys), len(set(yaml_keys)))
        self.assertEqual(set(yaml_keys), json_keys)


if __name__ == "__main__":
    unittest.main()
