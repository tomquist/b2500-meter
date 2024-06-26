import unittest
from unittest.mock import patch, MagicMock
from powermeter import Emlog


class TestEmlog(unittest.TestCase):

    def setUp(self):
        self.ip = "127.0.0.1"
        self.meterindex = "1"

    @patch("requests.Session.get")
    def test_get_powermeter_watts_no_calculate(self, mock_get):
        # Prepare the mocked response for no power calculation
        mock_response = MagicMock()
        mock_response.json.return_value = {"Leistung170": "200"}
        mock_get.return_value = mock_response

        # Initialize Emlog with json_power_calculate = False
        emlog = Emlog(self.ip, self.meterindex, json_power_calculate=False)

        # Call the method and check the result
        result = emlog.get_powermeter_watts()
        self.assertEqual(result, [200])

    @patch("requests.Session.get")
    def test_get_powermeter_watts_with_calculate(self, mock_get):
        # Prepare the mocked response for power calculation
        mock_response = MagicMock()
        mock_response.json.return_value = {"Leistung170": "400", "Leistung270": "150"}
        mock_get.return_value = mock_response

        # Initialize Emlog with json_power_calculate = True
        emlog = Emlog(self.ip, self.meterindex, json_power_calculate=True)

        # Call the method and check the result
        result = emlog.get_powermeter_watts()
        self.assertEqual(result, [250])


if __name__ == "__main__":
    unittest.main()
