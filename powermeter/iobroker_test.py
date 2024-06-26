import unittest
from unittest.mock import patch, MagicMock
from powermeter import IoBroker


class TestIoBroker(unittest.TestCase):

    def setUp(self):
        self.ip = "127.0.0.1"
        self.port = "8080"
        self.current_power_alias = "alias1"
        self.power_input_alias = "input_alias"
        self.power_output_alias = "output_alias"

    @patch("requests.Session.get")
    def test_get_powermeter_watts_no_calculate(self, mock_get):
        # Prepare the mocked response for no power calculation
        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": self.current_power_alias, "val": 100}]
        mock_get.return_value = mock_response

        # Initialize IoBroker with power_calculate = False
        iobroker = IoBroker(
            self.ip,
            self.port,
            self.current_power_alias,
            power_calculate=False,
            power_input_alias=self.power_input_alias,
            power_output_alias=self.power_output_alias,
        )

        # Call the method and check the result
        result = iobroker.get_powermeter_watts()
        self.assertEqual(result, [100])

    @patch("requests.Session.get")
    def test_get_powermeter_watts_with_calculate(self, mock_get):
        # Prepare the mocked response for power calculation
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": self.power_input_alias, "val": 300},
            {"id": self.power_output_alias, "val": 150},
        ]
        mock_get.return_value = mock_response

        # Initialize IoBroker with power_calculate = True
        iobroker = IoBroker(
            self.ip,
            self.port,
            self.current_power_alias,
            power_calculate=True,
            power_input_alias=self.power_input_alias,
            power_output_alias=self.power_output_alias,
        )

        # Call the method and check the result
        result = iobroker.get_powermeter_watts()
        self.assertEqual(result, [150])


if __name__ == "__main__":
    unittest.main()
