import unittest
from unittest.mock import patch, MagicMock
from powermeter import ESPHome


class TestESPHome(unittest.TestCase):

    @patch("requests.Session.get")
    def test_esphome_get_powermeter_watts(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"value": 234}
        mock_get.return_value = mock_response

        esphome = ESPHome("192.168.1.4", "80", "sensor", "power")
        self.assertEqual(esphome.get_powermeter_watts(), [234])


if __name__ == "__main__":
    unittest.main()
