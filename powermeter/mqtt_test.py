import unittest
from .mqtt import extract_json_value


class TestExtractJsonValue(unittest.TestCase):
    def test_extract_curr_w(self):
        data = {
            "SML": {
                "curr_w": 381,
            }
        }
        path = "$.SML.curr_w"
        self.assertEqual(extract_json_value(data, path), 381)

    def test_extract_nonexistent_path(self):
        data = {
            "SML": {
                "curr_w": 381,
            }
        }
        path = "$.SML.nonexistent"
        with self.assertRaises(ValueError):
            extract_json_value(data, path)

    def test_extract_float_value(self):
        data = {
            "SML": {
                "curr_w": 381.75,
            }
        }
        path = "$.SML.curr_w"
        self.assertEqual(extract_json_value(data, path), 381.75)

    def test_extract_from_array(self):
        data = {
            "SML": {
                "measurements": [{"curr_w": 100.5}, {"curr_w": 200.75}, {"curr_w": 300}]
            }
        }
        path = "$.SML.measurements[1].curr_w"
        self.assertEqual(extract_json_value(data, path), 200.75)


if __name__ == "__main__":
    unittest.main()
