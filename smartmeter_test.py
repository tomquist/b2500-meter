import unittest
from unittest.mock import patch, MagicMock
from smartmeter import (
    extract_json_value,
    Tasmota,
    Shelly1PM,
    ShellyPlus1PM,
    ShellyEM,
    Shelly3EM,
    Shelly3EMPro,
    ESPHome,
    Shrdzm,
    Emlog,
    IoBroker,
    HomeAssistant,
    VZLogger,
    AmisReader,
    ModbusPowermeter,
)


class TestExtractJsonValue(unittest.TestCase):
    def test_extract_curr_w(self):
        data = {
            "SML": {
                "curr_w": 381,
            }
        }
        path = "$.SML.curr_w"
        self.assertEqual(extract_json_value(data, path), 381)

    def test_extract_nonexistent_path(self):
        data = {
            "SML": {
                "curr_w": 381,
            }
        }
        path = "$.SML.nonexistent"
        with self.assertRaises(ValueError):
            extract_json_value(data, path)

    def test_extract_float_value(self):
        data = {
            "SML": {
                "curr_w": 381.75,
            }
        }
        path = "$.SML.curr_w"
        self.assertEqual(extract_json_value(data, path), 381)

    def test_extract_from_array(self):
        data = {
            "SML": {
                "measurements": [{"curr_w": 100.5}, {"curr_w": 200.75}, {"curr_w": 300}]
            }
        }
        path = "$.SML.measurements[1].curr_w"
        self.assertEqual(extract_json_value(data, path), 200)


class TestPowermeters(unittest.TestCase):

    @patch("smartmeter.session.get")
    def test_tasmota_get_powermeter_watts(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"StatusSNS": {"ENERGY": {"Power": 123}}}
        mock_get.return_value = mock_response

        tasmota = Tasmota(
            "192.168.1.1", "user", "pass", "StatusSNS", "ENERGY", "Power", "", "", False
        )
        self.assertEqual(tasmota.get_powermeter_watts(), [123])

    @patch("smartmeter.session.get")
    def test_shelly1pm_get_powermeter_watts(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"meters": [{"power": 456}]}
        mock_get.return_value = mock_response

        shelly1pm = Shelly1PM("192.168.1.2", "user", "pass", "")
        self.assertEqual(shelly1pm.get_powermeter_watts(), [456])

    @patch("smartmeter.session.get")
    def test_shellyem_get_powermeter_watts(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "emeters": [{"power": 789}, {"power": 1011}, {"power": 1213}]
        }
        mock_get.return_value = mock_response

        shellyem = ShellyEM("192.168.1.3", "user", "pass", "")
        self.assertEqual(shellyem.get_powermeter_watts(), [789, 1011, 1213])

    @patch("smartmeter.session.get")
    def test_esphome_get_powermeter_watts(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"value": 234}
        mock_get.return_value = mock_response

        esphome = ESPHome("192.168.1.4", "80", "sensor", "power")
        self.assertEqual(esphome.get_powermeter_watts(), [234])

    @patch("smartmeter.session.get")
    def test_shrdzm_get_powermeter_watts(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"1.7.0": 5000, "2.7.0": 2000}
        mock_get.return_value = mock_response

        shrdzm = Shrdzm("192.168.1.5", "user", "pass")
        self.assertEqual(shrdzm.get_powermeter_watts(), [3000])

    @patch("smartmeter.session.get")
    def test_emlog_get_powermeter_watts(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"Leistung170": 1500, "Leistung270": 500}
        mock_get.return_value = mock_response

        emlog = Emlog("192.168.1.6", "1", True)
        self.assertEqual(emlog.get_powermeter_watts(), [1000])

    @patch("smartmeter.session.get")
    def test_iobroker_get_powermeter_watts(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": "power1", "val": 600},
            {"id": "power2", "val": 300},
        ]
        mock_get.return_value = mock_response

        iobroker = IoBroker("192.168.1.7", "8087", "power1", True, "power1", "power2")
        self.assertEqual(iobroker.get_powermeter_watts(), [300])

    @patch("smartmeter.session.get")
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
        )
        self.assertEqual(homeassistant.get_powermeter_watts(), [800])

    @patch("smartmeter.session.get")
    def test_vzlogger_get_powermeter_watts(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": [{"tuples": [[None, 900]]}]}
        mock_get.return_value = mock_response

        vzlogger = VZLogger("192.168.1.9", "8088", "uuid")
        self.assertEqual(vzlogger.get_powermeter_watts(), [900])

    @patch("smartmeter.session.get")
    def test_amisreader_get_powermeter_watts(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"saldo": 1200}
        mock_get.return_value = mock_response

        amisreader = AmisReader("192.168.1.10")
        self.assertEqual(amisreader.get_powermeter_watts(), [1200])

    @patch("smartmeter.session.get")
    def test_shellyplus1pm_get_powermeter_watts(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"apower": 150}
        mock_get.return_value = mock_response

        shellyplus1pm = ShellyPlus1PM("192.168.1.11", "user", "pass", "")
        self.assertEqual(shellyplus1pm.get_powermeter_watts(), [150])

    @patch("smartmeter.session.get")
    def test_shelly3em_get_powermeter_watts(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "emeters": [{"power": 100}, {"power": 200}, {"power": 300}]
        }
        mock_get.return_value = mock_response

        shellyem = Shelly3EM("192.168.1.12", "user", "pass", "")
        self.assertEqual(shellyem.get_powermeter_watts(), [100, 200, 300])

    @patch("smartmeter.session.get")
    def test_shelly3empro_get_powermeter_watts(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"total_act_power": 450}
        mock_get.return_value = mock_response

        shelly3empro = Shelly3EMPro("192.168.1.13", "user", "pass", "")
        self.assertEqual(shelly3empro.get_powermeter_watts(), [450])

    @patch("smartmeter.ModbusTcpClient")
    def test_modbuspowermeter_get_powermeter_watts(self, MockModbusTcpClient):
        mock_client = MockModbusTcpClient.return_value
        mock_client.read_holding_registers.return_value.isError.return_value = False
        mock_client.read_holding_registers.return_value.registers = [500]

        modbuspowermeter = ModbusPowermeter("192.168.1.14", 502, 1, 0, 1)
        self.assertEqual(modbuspowermeter.get_powermeter_watts(), [500])


if __name__ == "__main__":
    unittest.main()
