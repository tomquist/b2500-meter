import json
import unittest
from unittest.mock import patch, MagicMock

from .homewizard import HomeWizardPowermeter


class TestHomeWizardPowermeter(unittest.TestCase):
    def _create_powermeter(self):
        with patch("powermeter.homewizard.websocket.WebSocketApp"):
            with patch("threading.Thread"):
                pm = HomeWizardPowermeter("192.168.1.1", "ABCD1234", "aabbccddee")
        return pm

    def test_on_message_authorization_requested(self):
        pm = self._create_powermeter()
        ws = MagicMock()
        pm._on_message(
            ws,
            json.dumps(
                {
                    "type": "authorization_requested",
                    "data": {"api_version": "2.0.0"},
                }
            ),
        )
        ws.send.assert_called_once_with(
            json.dumps({"type": "authorization", "data": "ABCD1234"})
        )

    def test_on_message_authorized(self):
        pm = self._create_powermeter()
        ws = MagicMock()
        pm._on_message(ws, json.dumps({"type": "authorized"}))
        ws.send.assert_called_once_with(
            json.dumps({"type": "subscribe", "data": "measurement"})
        )

    def test_on_message_measurement_three_phase(self):
        pm = self._create_powermeter()
        ws = MagicMock()
        pm._on_message(
            ws,
            json.dumps(
                {
                    "type": "measurement",
                    "data": {
                        "power_w": -543,
                        "power_l1_w": -200,
                        "power_l2_w": -143,
                        "power_l3_w": -200,
                    },
                }
            ),
        )
        self.assertEqual(pm.get_powermeter_watts(), [-200, -143, -200])

    def test_on_message_measurement_single_phase(self):
        pm = self._create_powermeter()
        ws = MagicMock()
        pm._on_message(
            ws,
            json.dumps(
                {
                    "type": "measurement",
                    "data": {
                        "power_w": 500,
                    },
                }
            ),
        )
        self.assertEqual(pm.get_powermeter_watts(), [500])

    def test_on_message_measurement_missing_phases(self):
        pm = self._create_powermeter()
        ws = MagicMock()
        pm._on_message(
            ws,
            json.dumps(
                {
                    "type": "measurement",
                    "data": {
                        "power_w": -543,
                        "power_l1_w": -543,
                    },
                }
            ),
        )
        self.assertEqual(pm.get_powermeter_watts(), [-543, 0, 0])

    def test_on_message_measurement_no_power_fields(self):
        pm = self._create_powermeter()
        ws = MagicMock()
        pm._on_message(
            ws,
            json.dumps(
                {
                    "type": "measurement",
                    "data": {
                        "energy_import_kwh": 1234.5,
                    },
                }
            ),
        )
        with self.assertRaises(ValueError):
            pm.get_powermeter_watts()

    def test_on_message_error(self):
        pm = self._create_powermeter()
        ws = MagicMock()
        pm._on_message(
            ws,
            json.dumps(
                {
                    "type": "error",
                    "data": {"message": "user:not-authorized"},
                }
            ),
        )
        with self.assertRaises(ValueError):
            pm.get_powermeter_watts()

    def test_on_message_malformed_json(self):
        pm = self._create_powermeter()
        ws = MagicMock()
        pm._on_message(ws, "not valid json")
        with self.assertRaises(ValueError):
            pm.get_powermeter_watts()

    def test_get_powermeter_watts_no_data(self):
        pm = self._create_powermeter()
        with self.assertRaises(ValueError):
            pm.get_powermeter_watts()

    def test_get_powermeter_watts_returns_copy(self):
        pm = self._create_powermeter()
        ws = MagicMock()
        pm._on_message(
            ws,
            json.dumps(
                {
                    "type": "measurement",
                    "data": {"power_w": 100},
                }
            ),
        )
        result = pm.get_powermeter_watts()
        result.append(999)
        self.assertEqual(pm.get_powermeter_watts(), [100])

    def test_negative_power_preserved(self):
        pm = self._create_powermeter()
        ws = MagicMock()
        pm._on_message(
            ws,
            json.dumps(
                {
                    "type": "measurement",
                    "data": {"power_w": -1500},
                }
            ),
        )
        self.assertEqual(pm.get_powermeter_watts(), [-1500])


if __name__ == "__main__":
    unittest.main()
