import unittest
from unittest.mock import patch, MagicMock
from powermeter import Shelly1PM, ShellyEM, ShellyPlus1PM, Shelly3EM, Shelly3EMPro


class TestShelly(unittest.TestCase):

    @patch("requests.Session.get")
    def test_shelly1pm_get_powermeter_watts(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"meters": [{"power": 456}]}
        mock_get.return_value = mock_response

        shelly1pm = Shelly1PM("192.168.1.2", "user", "pass", "")
        self.assertEqual(shelly1pm.get_powermeter_watts(), [456])

    @patch("requests.Session.get")
    def test_shellyem_get_powermeter_watts(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "emeters": [{"power": 789}, {"power": 1011}, {"power": 1213}]
        }
        mock_get.return_value = mock_response

        shellyem = ShellyEM("192.168.1.3", "user", "pass", "")
        self.assertEqual(shellyem.get_powermeter_watts(), [789, 1011, 1213])

    @patch("requests.Session.get")
    def test_shellyplus1pm_get_powermeter_watts(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"apower": 150}
        mock_get.return_value = mock_response

        shellyplus1pm = ShellyPlus1PM("192.168.1.11", "user", "pass", "")
        self.assertEqual(shellyplus1pm.get_powermeter_watts(), [150])

    @patch("requests.Session.get")
    def test_shelly3em_get_powermeter_watts(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "emeters": [{"power": 100}, {"power": 200}, {"power": 300}]
        }
        mock_get.return_value = mock_response

        shellyem = Shelly3EM("192.168.1.12", "user", "pass", "")
        self.assertEqual(shellyem.get_powermeter_watts(), [100, 200, 300])

    @patch("requests.Session.get")
    def test_shelly3empro_get_powermeter_watts(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"total_act_power": 450}
        mock_get.return_value = mock_response

        shelly3empro = Shelly3EMPro("192.168.1.13", "user", "pass", "")
        self.assertEqual(shelly3empro.get_powermeter_watts(), [450])


if __name__ == "__main__":
    unittest.main()
