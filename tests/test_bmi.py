import unittest

from bmi_logic import bmi_category, bmi_value
from server import normalize_base_path, validate_profile


class BmiLogicTests(unittest.TestCase):
    def test_bmi_value(self):
        self.assertEqual(bmi_value(180, 81), 25.0)

    def test_bmi_category(self):
        self.assertEqual(bmi_category(17.4), "Underweight")
        self.assertEqual(bmi_category(22.0), "Healthy")
        self.assertEqual(bmi_category(28.2), "Overweight")
        self.assertEqual(bmi_category(33.1), "Obese")

    def test_validation(self):
        payload = {
            "firstName": "Ada",
            "lastName": "Stone",
            "email": "ada@example.com",
            "password": "secret123",
            "age": 30,
            "gender": "Female",
            "heightCm": 168,
            "weightKg": 61,
        }
        result = validate_profile(payload, require_password=True)
        self.assertEqual(result["errors"], {})

    def test_base_path_normalization(self):
        self.assertEqual(normalize_base_path(None), "")
        self.assertEqual(normalize_base_path("/"), "")
        self.assertEqual(normalize_base_path("agent1/devops/bmi-calculator"), "/agent1/devops/bmi-calculator")


if __name__ == "__main__":
    unittest.main()
