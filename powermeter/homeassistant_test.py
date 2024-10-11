import unittest
from unittest.mock import patch, MagicMock
from powermeter import HomeAssistant


class TestPowermeters(unittest.TestCase):

    @patch("requests.Session.get")
    def test_homeassistant_get_powermeter_watts(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.side_effect = [{"state": 1000}, {"state": 200}]
        mock_get.return_value = mock_response

        homeassistant = HomeAssistant(
            "192.168.1.8",
            "8123",
            False,
            "token",
            "sensor.current_power",
            True,
            "sensor.power_input",
            "sensor.power_output",
            None,
        )
        self.assertEqual(homeassistant.get_powermeter_watts(), [800])


if __name__ == "__main__":
    unittest.main()
