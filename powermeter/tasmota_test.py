import unittest
from unittest.mock import patch, MagicMock
from powermeter import (
    Tasmota,
)


class TestTasmota(unittest.TestCase):

    @patch("requests.Session.get")
    def test_tasmota_get_powermeter_watts(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"StatusSNS": {"ENERGY": {"Power": 123}}}
        mock_get.return_value = mock_response

        tasmota = Tasmota(
            "192.168.1.1", "user", "pass", "StatusSNS", "ENERGY", "Power", "", "", False
        )
        self.assertEqual(tasmota.get_powermeter_watts(), [123])


if __name__ == "__main__":
    unittest.main()
