import unittest
from unittest.mock import patch, MagicMock
from powermeter import em300


class TestEm300(unittest.TestCase):

    def setUp(self):
        self.ip = "127.0.0.1"

    @patch("requests.Session.get")
    def test_get_powermeter_watts_no_calculate(self, mock_get):
        # Prepare the mocked response for no power calculation
        mock_response = MagicMock()
        mock_response.json.return_value = {"1-0:1.4.0*255": "400"}
        mock_get.return_value = mock_response

        # Initialize Emlog with json_power_calculate = False
        Em300 = Em300(self.ip, self.user, self.password, json_power_calculate=True)

        # Call the method and check the result
        result = emlog.get_powermeter_watts()
        self.assertEqual(result, [200])

    @patch("requests.Session.get")
    def test_get_powermeter_watts_with_calculate(self, mock_get):
        # Prepare the mocked response for power calculation
        mock_response = MagicMock()
        mock_response.json.return_value = {"1-0:1.4.0*255": "400", "1-0:2.4.0*255": "150"}
        mock_get.return_value = mock_response

        # Initialize Emlog with json_power_calculate = True
        Em300 = Em300(self.ip, self.user, self.password, json_power_calculate=True)

        # Call the method and check the result
        result = Em300.get_powermeter_watts()
        self.assertEqual(result, [250])


if __name__ == "__main__":
    unittest.main()
  
