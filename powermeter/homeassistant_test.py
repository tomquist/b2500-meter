import json
import unittest
from unittest.mock import patch, MagicMock

from .homeassistant import HomeAssistant


class TestHomeAssistant(unittest.TestCase):
    def _create_powermeter(self, **overrides):
        defaults = dict(
            ip="192.168.1.8",
            port="8123",
            use_https=False,
            access_token="token",
            current_power_entity="sensor.current_power",
            power_calculate=False,
            power_input_alias="",
            power_output_alias="",
            path_prefix=None,
        )
        defaults.update(overrides)
        with patch("powermeter.homeassistant.websocket.WebSocketApp"):
            with patch("powermeter.homeassistant.threading.Thread"):
                pm = HomeAssistant(**defaults)
        return pm

    def _simulate_auth_and_states(self, pm, states):
        ws = MagicMock()
        pm._on_message(ws, json.dumps({"type": "auth_required"}))
        pm._on_message(ws, json.dumps({"type": "auth_ok"}))
        pm._on_message(
            ws,
            json.dumps(
                {
                    "id": pm._get_states_id,
                    "type": "result",
                    "success": True,
                    "result": states,
                }
            ),
        )
        return ws

    # Auth flow tests

    def test_auth_required_sends_token(self):
        pm = self._create_powermeter()
        ws = MagicMock()
        pm._on_message(ws, json.dumps({"type": "auth_required"}))
        ws.send.assert_called_once_with(
            json.dumps({"type": "auth", "access_token": "token"})
        )

    def test_auth_ok_sends_get_states_and_subscribe(self):
        pm = self._create_powermeter()
        ws = MagicMock()
        pm._on_message(ws, json.dumps({"type": "auth_required"}))
        ws.send.reset_mock()

        pm._on_message(ws, json.dumps({"type": "auth_ok"}))

        calls = ws.send.call_args_list
        self.assertEqual(len(calls), 2)

        get_states_msg = json.loads(calls[0][0][0])
        self.assertEqual(get_states_msg["type"], "get_states")

        subscribe_msg = json.loads(calls[1][0][0])
        self.assertEqual(subscribe_msg["type"], "subscribe_trigger")
        self.assertEqual(subscribe_msg["trigger"]["platform"], "state")
        self.assertIn("sensor.current_power", subscribe_msg["trigger"]["entity_id"])

    def test_auth_invalid_does_not_crash(self):
        pm = self._create_powermeter()
        ws = MagicMock()
        pm._on_message(
            ws,
            json.dumps({"type": "auth_invalid", "message": "bad token"}),
        )
        # Should not raise

    # get_states tests

    def test_get_states_populates_value(self):
        pm = self._create_powermeter()
        self._simulate_auth_and_states(
            pm, [{"entity_id": "sensor.current_power", "state": "1000"}]
        )
        self.assertEqual(pm.get_powermeter_watts(), [1000.0])

    def test_get_states_failure(self):
        pm = self._create_powermeter()
        ws = MagicMock()
        pm._on_message(ws, json.dumps({"type": "auth_required"}))
        pm._on_message(ws, json.dumps({"type": "auth_ok"}))
        pm._on_message(
            ws,
            json.dumps(
                {
                    "id": pm._get_states_id,
                    "type": "result",
                    "success": False,
                    "error": {"code": "unknown", "message": "something broke"},
                }
            ),
        )

        with self.assertRaises(ValueError):
            pm.get_powermeter_watts()

    def test_get_states_ignores_untracked_entities(self):
        pm = self._create_powermeter()
        self._simulate_auth_and_states(
            pm,
            [
                {"entity_id": "sensor.current_power", "state": "500"},
                {"entity_id": "sensor.temperature", "state": "22"},
            ],
        )
        self.assertEqual(pm.get_powermeter_watts(), [500.0])

    # Trigger event tests

    def test_trigger_event_updates_value(self):
        pm = self._create_powermeter()
        self._simulate_auth_and_states(
            pm, [{"entity_id": "sensor.current_power", "state": "100"}]
        )
        self.assertEqual(pm.get_powermeter_watts(), [100.0])

        ws = MagicMock()
        pm._on_message(
            ws,
            json.dumps(
                {
                    "id": 2,
                    "type": "event",
                    "event": {
                        "variables": {
                            "trigger": {
                                "entity_id": "sensor.current_power",
                                "to_state": {
                                    "entity_id": "sensor.current_power",
                                    "state": "200",
                                },
                            }
                        }
                    },
                }
            ),
        )
        self.assertEqual(pm.get_powermeter_watts(), [200.0])

    def test_trigger_event_ignores_untracked_entity(self):
        pm = self._create_powermeter()
        self._simulate_auth_and_states(
            pm, [{"entity_id": "sensor.current_power", "state": "100"}]
        )

        ws = MagicMock()
        pm._on_message(
            ws,
            json.dumps(
                {
                    "id": 2,
                    "type": "event",
                    "event": {
                        "variables": {
                            "trigger": {
                                "entity_id": "sensor.other",
                                "to_state": {
                                    "entity_id": "sensor.other",
                                    "state": "999",
                                },
                            }
                        }
                    },
                }
            ),
        )
        self.assertEqual(pm.get_powermeter_watts(), [100.0])

    # Error condition tests

    def test_sensor_has_no_state(self):
        pm = self._create_powermeter()
        with self.assertRaises(ValueError) as context:
            pm.get_powermeter_watts()

        self.assertEqual(
            str(context.exception),
            "Home Assistant sensor sensor.current_power has no state",
        )

    def test_sensor_state_none(self):
        pm = self._create_powermeter()
        self._simulate_auth_and_states(
            pm, [{"entity_id": "sensor.current_power", "state": None}]
        )

        with self.assertRaises(ValueError) as context:
            pm.get_powermeter_watts()

        self.assertEqual(
            str(context.exception),
            "Home Assistant sensor sensor.current_power has no state",
        )

    def test_sensor_state_not_numeric(self):
        pm = self._create_powermeter()
        self._simulate_auth_and_states(
            pm,
            [{"entity_id": "sensor.current_power", "state": "unavailable"}],
        )

        with self.assertRaises(ValueError) as context:
            pm.get_powermeter_watts()

        self.assertEqual(
            str(context.exception),
            "Home Assistant sensor sensor.current_power has no state",
        )

    def test_malformed_json_message(self):
        pm = self._create_powermeter()
        ws = MagicMock()
        pm._on_message(ws, "not valid json")
        # Should not raise; value stays absent
        with self.assertRaises(ValueError):
            pm.get_powermeter_watts()

    # Three-phase tests

    def test_three_phase_direct(self):
        pm = self._create_powermeter(
            current_power_entity=[
                "sensor.power_phase1",
                "sensor.power_phase2",
                "sensor.power_phase3",
            ]
        )
        self._simulate_auth_and_states(
            pm,
            [
                {"entity_id": "sensor.power_phase1", "state": "100"},
                {"entity_id": "sensor.power_phase2", "state": "200"},
                {"entity_id": "sensor.power_phase3", "state": "300"},
            ],
        )
        self.assertEqual(pm.get_powermeter_watts(), [100.0, 200.0, 300.0])

    # Power calculate tests

    def test_power_calculate_mode(self):
        pm = self._create_powermeter(
            current_power_entity="",
            power_calculate=True,
            power_input_alias="sensor.power_input",
            power_output_alias="sensor.power_output",
        )
        self._simulate_auth_and_states(
            pm,
            [
                {"entity_id": "sensor.power_input", "state": "1000"},
                {"entity_id": "sensor.power_output", "state": "200"},
            ],
        )
        self.assertEqual(pm.get_powermeter_watts(), [800.0])

    def test_three_phase_calculated(self):
        pm = self._create_powermeter(
            current_power_entity="",
            power_calculate=True,
            power_input_alias=[
                "sensor.power_in_1",
                "sensor.power_in_2",
                "sensor.power_in_3",
            ],
            power_output_alias=[
                "sensor.power_out_1",
                "sensor.power_out_2",
                "sensor.power_out_3",
            ],
        )
        self._simulate_auth_and_states(
            pm,
            [
                {"entity_id": "sensor.power_in_1", "state": "1000"},
                {"entity_id": "sensor.power_out_1", "state": "200"},
                {"entity_id": "sensor.power_in_2", "state": "2000"},
                {"entity_id": "sensor.power_out_2", "state": "300"},
                {"entity_id": "sensor.power_in_3", "state": "3000"},
                {"entity_id": "sensor.power_out_3", "state": "400"},
            ],
        )
        self.assertEqual(pm.get_powermeter_watts(), [800.0, 1700.0, 2600.0])

    def test_power_alias_length_mismatch(self):
        pm = self._create_powermeter(
            current_power_entity="",
            power_calculate=True,
            power_input_alias=["sensor.power_in_1", "sensor.power_in_2"],
            power_output_alias=["sensor.power_out_1"],
        )
        # Populate values so we get past the "no state" check
        self._simulate_auth_and_states(
            pm,
            [
                {"entity_id": "sensor.power_in_1", "state": "100"},
                {"entity_id": "sensor.power_in_2", "state": "200"},
                {"entity_id": "sensor.power_out_1", "state": "50"},
            ],
        )

        with self.assertRaises(ValueError) as context:
            pm.get_powermeter_watts()

        self.assertEqual(
            str(context.exception),
            "Home Assistant power_input_alias and" " power_output_alias lengths differ",
        )

    # WebSocket URL tests

    def test_ws_url_http(self):
        pm = self._create_powermeter()
        self.assertEqual(pm._build_ws_url(), "ws://192.168.1.8:8123/api/websocket")

    def test_ws_url_https(self):
        pm = self._create_powermeter(use_https=True)
        self.assertEqual(pm._build_ws_url(), "wss://192.168.1.8:8123/api/websocket")

    def test_ws_url_with_path_prefix(self):
        pm = self._create_powermeter(path_prefix="/prefix")
        self.assertEqual(
            pm._build_ws_url(),
            "ws://192.168.1.8:8123/prefix/api/websocket",
        )

    # wait_for_message test

    def test_wait_for_message_returns_when_data_available(self):
        pm = self._create_powermeter()
        self._simulate_auth_and_states(
            pm, [{"entity_id": "sensor.current_power", "state": "100"}]
        )
        # Should return immediately, not raise
        pm.wait_for_message(timeout=1)

    def test_wait_for_message_timeout(self):
        pm = self._create_powermeter()
        with self.assertRaises(TimeoutError):
            pm.wait_for_message(timeout=0)

    # Subscribe trigger entity list test

    def test_subscribe_trigger_contains_all_entities_calculate_mode(self):
        pm = self._create_powermeter(
            current_power_entity="",
            power_calculate=True,
            power_input_alias="sensor.power_input",
            power_output_alias="sensor.power_output",
        )
        ws = MagicMock()
        pm._on_message(ws, json.dumps({"type": "auth_required"}))
        ws.send.reset_mock()
        pm._on_message(ws, json.dumps({"type": "auth_ok"}))

        subscribe_msg = json.loads(ws.send.call_args_list[1][0][0])
        entity_ids = subscribe_msg["trigger"]["entity_id"]
        self.assertIn("sensor.power_input", entity_ids)
        self.assertIn("sensor.power_output", entity_ids)


if __name__ == "__main__":
    unittest.main()
