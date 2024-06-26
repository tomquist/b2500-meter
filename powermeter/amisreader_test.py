import unittest
from unittest.mock import patch, MagicMock
from powermeter import AmisReader


class TestAmisreader(unittest.TestCase):

    @patch("requests.Session.get")
    def test_amisreader_get_powermeter_watts(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"saldo": 1200}
        mock_get.return_value = mock_response

        amisreader = AmisReader("192.168.1.10")
        self.assertEqual(amisreader.get_powermeter_watts(), [1200])


if __name__ == "__main__":
    unittest.main()
