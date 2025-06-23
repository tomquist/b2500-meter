import unittest
from unittest.mock import patch, MagicMock
from powermeter import JsonHttpPowermeter
from requests.auth import HTTPBasicAuth


class TestJsonHttpPowermeter(unittest.TestCase):
    @patch("requests.Session.get")
    def test_single_phase(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"power": 100}
        mock_get.return_value = mock_response

        meter = JsonHttpPowermeter("http://localhost", "$.power")
        self.assertEqual(meter.get_powermeter_watts(), [100.0])

    @patch("requests.Session.get")
    def test_three_phase(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "p1": 100,
            "p2": 200,
            "p3": 300,
        }
        mock_get.return_value = mock_response

        meter = JsonHttpPowermeter(
            "http://localhost",
            ["$.p1", "$.p2", "$.p3"],
        )
        self.assertEqual(meter.get_powermeter_watts(), [100.0, 200.0, 300.0])

    @patch("requests.Session.get")
    def test_headers_and_auth(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"power": 50}
        mock_get.return_value = mock_response

        meter = JsonHttpPowermeter(
            "http://localhost",
            "$.power",
            username="user",
            password="pass",
            headers={"X-Test": "1"},
        )
        meter.get_powermeter_watts()
        mock_get.assert_called_with(
            "http://localhost",
            headers={"X-Test": "1"},
            auth=HTTPBasicAuth("user", "pass"),
            timeout=10,
        )


if __name__ == "__main__":
    unittest.main()
