import unittest
from unittest.mock import MagicMock, patch
from .mqtt import extract_json_value, MqttPowermeter


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
        self.assertEqual(extract_json_value(data, path), 381.75)

    def test_extract_from_array(self):
        data = {
            "SML": {
                "measurements": [{"curr_w": 100.5}, {"curr_w": 200.75}, {"curr_w": 300}]
            }
        }
        path = "$.SML.measurements[1].curr_w"
        self.assertEqual(extract_json_value(data, path), 200.75)


class TestMqttPowermeter(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        with patch("paho.mqtt.client.Client", return_value=self.mock_client):
            self.pm_single = MqttPowermeter(
                broker="localhost",
                port=1883,
                topics="topic/single",
                json_paths="$.value"
            )
            self.pm_multi_topic = MqttPowermeter(
                broker="localhost",
                port=1883,
                topics=["topic/1", "topic/2"],
                json_paths=None
            )
            self.pm_multi_path = MqttPowermeter(
                broker="localhost",
                port=1883,
                topics=["topic/single", "topic/single"],
                json_paths=["$.p1", "$.p2"]
            )
            self.pm_mixed = MqttPowermeter(
                broker="localhost",
                port=1883,
                topics=["topic/A", "topic/B"],
                json_paths=["$.val", None]
            )

    def test_single_phase_legacy(self):
        msg = MagicMock()
        msg.topic = "topic/single"
        msg.payload = b'{"value": 123.4}'
        self.pm_single.on_message(None, None, msg)
        self.assertEqual(self.pm_single.get_powermeter_watts(), [123.4])

    def test_multi_topic_raw(self):
        msg1 = MagicMock()
        msg1.topic = "topic/1"
        msg1.payload = b'100'

        msg2 = MagicMock()
        msg2.topic = "topic/2"
        msg2.payload = b'200'

        self.pm_multi_topic.on_message(None, None, msg1)
        # Should raise ValueError because not all values are present
        with self.assertRaises(ValueError):
             self.pm_multi_topic.get_powermeter_watts()

        self.pm_multi_topic.on_message(None, None, msg2)
        self.assertEqual(self.pm_multi_topic.get_powermeter_watts(), [100.0, 200.0])

    def test_single_topic_multi_path(self):
        msg = MagicMock()
        msg.topic = "topic/single"
        msg.payload = b'{"p1": 50, "p2": 60}'

        self.pm_multi_path.on_message(None, None, msg)
        self.assertEqual(self.pm_multi_path.get_powermeter_watts(), [50.0, 60.0])

    def test_mixed(self):
        msg1 = MagicMock()
        msg1.topic = "topic/A"
        msg1.payload = b'{"val": 10.5}'

        msg2 = MagicMock()
        msg2.topic = "topic/B"
        msg2.payload = b'20.5'

        self.pm_mixed.on_message(None, None, msg1)
        self.pm_mixed.on_message(None, None, msg2)

        self.assertEqual(self.pm_mixed.get_powermeter_watts(), [10.5, 20.5])


if __name__ == "__main__":
    unittest.main()
