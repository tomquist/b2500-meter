from .base import Powermeter
import json
import paho.mqtt.client as mqtt
from jsonpath_ng import parse
import time


def extract_json_value(data, path):
    jsonpath_expr = parse(path)
    match = jsonpath_expr.find(data)
    if match:
        return float(match[0].value)
    else:
        raise ValueError("No match found for the JSON path")


class MqttPowermeter(Powermeter):
    def __init__(
        self,
        broker: str,
        port: int,
        topic: str,
        json_path: str = None,
        username: str = None,
        password: str = None,
    ):
        self.broker = broker
        self.port = port
        self.topic = topic
        self.json_path = json_path
        self.username = username
        self.password = password
        self.value = None

        # Initialize MQTT client
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if self.username and self.password:
            self.client.username_pw_set(self.username, self.password)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        # Connect to the broker
        self.client.connect(self.broker, self.port, 60)
        self.client.loop_start()

    def on_connect(self, client, userdata, flags, reason_code, properties):
        print(f"Connected with result code {reason_code}")
        # Subscribe to the topic
        client.subscribe(self.topic)

    def on_message(self, client, userdata, msg):
        payload = msg.payload.decode()
        if self.json_path:
            try:
                data = json.loads(payload)
                self.value = extract_json_value(data, self.json_path)
            except json.JSONDecodeError:
                print("Failed to decode JSON")
        else:
            self.value = float(payload)

    def get_powermeter_watts(self):
        if self.value is not None:
            return [self.value]
        else:
            raise ValueError("No value received from MQTT")

    def wait_for_message(self, timeout=5):
        start_time = time.time()
        while self.value is None:
            if time.time() - start_time > timeout:
                raise TimeoutError("Timeout waiting for MQTT message")
            time.sleep(1)
