from .base import Powermeter
import requests


class Tasmota(Powermeter):
    def __init__(
        self,
        ip: str,
        user: str,
        password: str,
        json_status: str,
        json_payload_mqtt_prefix: str,
        json_power_mqtt_label: str,
        json_power_input_mqtt_label: str,
        json_power_output_mqtt_label: str,
        json_power_calculate: bool,
    ):
        self.ip = ip
        self.user = user
        self.password = password
        self.json_status = json_status
        self.json_payload_mqtt_prefix = json_payload_mqtt_prefix
        self.json_power_mqtt_label = json_power_mqtt_label
        self.json_power_input_mqtt_label = json_power_input_mqtt_label
        self.json_power_output_mqtt_label = json_power_output_mqtt_label
        self.json_power_calculate = json_power_calculate
        self.session = requests.Session()

    def get_json(self, path):
        url = f"http://{self.ip}{path}"
        return self.session.get(url, timeout=10).json()

    def get_powermeter_watts(self):
        if not self.user:
            response = self.get_json("/cm?cmnd=status%2010")
        else:
            response = self.get_json(
                f"/cm"
                f"?user={self.user}"
                f"&password={self.password}"
                f"&cmnd=status%2010"
            )
        value = response[self.json_status][self.json_payload_mqtt_prefix]
        if not self.json_power_calculate:
            return [int(value[self.json_power_mqtt_label])]
        else:
            power_in = value[self.json_power_input_mqtt_label]
            power_out = value[self.json_power_output_mqtt_label]
            return [int(power_in) - int(power_out)]
