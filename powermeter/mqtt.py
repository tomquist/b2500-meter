from .base import Powermeter
import json
import paho.mqtt.client as mqtt
from jsonpath_ng import parse
import time
from typing import List, Union, Optional
from config.logger import logger


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
        topics: Union[str, List[str]],
        json_paths: Union[str, List[Optional[str]], None] = None,
        username: str = None,
        password: str = None,
    ):
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password

        # Normalize inputs to lists
        if isinstance(topics, str):
            self.topics = [topics]
        else:
            self.topics = topics

        if json_paths is None:
            self.json_paths = [None] * len(self.topics)
        elif isinstance(json_paths, str):
            self.json_paths = [json_paths]
        else:
            self.json_paths = json_paths

        # Ensure topics and json_paths have the same length
        if len(self.topics) != len(self.json_paths):
            raise ValueError("Number of topics and JSON paths must match")

        self.values = [None] * len(self.topics)

        # Map unique topics to phase indices
        self.topic_map = {}
        for idx, topic in enumerate(self.topics):
            if topic not in self.topic_map:
                self.topic_map[topic] = []
            self.topic_map[topic].append(idx)

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
        logger.info(f"Connected with result code {reason_code}")
        # Subscribe to all unique topics
        for topic in self.topic_map.keys():
            client.subscribe(topic)

    def on_message(self, client, userdata, msg):
        payload = msg.payload.decode()
        topic = msg.topic

        if topic in self.topic_map:
            for idx in self.topic_map[topic]:
                json_path = self.json_paths[idx]
                if json_path:
                    try:
                        data = json.loads(payload)
                        self.values[idx] = extract_json_value(data, json_path)
                    except json.JSONDecodeError:
                        logger.error("Failed to decode JSON")
                    except Exception as e:
                        logger.error(f"Error extracting value for index {idx}: {e}")
                else:
                    try:
                        self.values[idx] = float(payload)
                    except ValueError:
                         logger.error(f"Failed to convert payload to float: {payload}")


    def get_powermeter_watts(self):
        # Return list of values. If any is None, we might want to return 0 or handle it.
        # Original behavior threw ValueError if self.value was None.
        # Here we check if any value is None.
        if any(v is None for v in self.values):
             raise ValueError("Not all values received from MQTT yet")
        return self.values

    def wait_for_message(self, timeout=5):
        start_time = time.time()
        while any(v is None for v in self.values):
            if time.time() - start_time > timeout:
                raise TimeoutError("Timeout waiting for MQTT message")
            time.sleep(1)
