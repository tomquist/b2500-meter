import unittest
from unittest.mock import patch, MagicMock
from powermeter import VZLogger


class TestVZLogger(unittest.TestCase):

    @patch("requests.Session.get")
    def test_vzlogger_get_powermeter_watts(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": [{"tuples": [[None, 900]]}]}
        mock_get.return_value = mock_response

        vzlogger = VZLogger("192.168.1.9", "8088", "uuid")
        self.assertEqual(vzlogger.get_powermeter_watts(), [900])


if __name__ == "__main__":
    unittest.main()
