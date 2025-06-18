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

    @patch("requests.Session.get")
    def test_homeassistant_path_prefix(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.side_effect = [{"state": 1000}]
        mock_get.return_value = mock_response

        homeassistant = HomeAssistant(
            "ip",
            "8123",
            False,
            "token",
            "sensor.current_power",
            False,
            "sensor.power_input",
            "sensor.power_output",
            "/prefix",
        )
        homeassistant.get_powermeter_watts()
        mock_get.assert_called_with(
            "http://ip:8123/prefix/api/states/sensor.current_power",
            headers={
                "Authorization": "Bearer token",
                "content-type": "application/json",
            },
            timeout=10,
        )

    @patch("requests.Session.get")
    def test_homeassistant_get_powermeter_watts_three_phase(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.side_effect = [
            {"state": "100"},
            {"state": "200"},
            {"state": "300"},
        ]
        mock_get.return_value = mock_response

        homeassistant = HomeAssistant(
            "192.168.1.8",
            "8123",
            False,
            "token",
            ["sensor.power_phase1", "sensor.power_phase2", "sensor.power_phase3"],
            False,
            "",
            "",
            None,
        )
        self.assertEqual(homeassistant.get_powermeter_watts(), [100.0, 200.0, 300.0])

    @patch("requests.Session.get")
    def test_homeassistant_get_powermeter_watts_three_phase_calculated(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.side_effect = [
            {"state": "1000"},
            {"state": "200"},  # Phase 1
            {"state": "2000"},
            {"state": "300"},  # Phase 2
            {"state": "3000"},
            {"state": "400"},  # Phase 3
        ]
        mock_get.return_value = mock_response

        homeassistant = HomeAssistant(
            "192.168.1.8",
            "8123",
            False,
            "token",
            "",
            True,
            ["sensor.power_in_1", "sensor.power_in_2", "sensor.power_in_3"],
            ["sensor.power_out_1", "sensor.power_out_2", "sensor.power_out_3"],
            None,
        )
        self.assertEqual(homeassistant.get_powermeter_watts(), [800.0, 1700.0, 2600.0])


if __name__ == "__main__":
    unittest.main()
