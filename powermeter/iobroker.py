from .base import Powermeter
import requests


class IoBroker(Powermeter):
    def __init__(
        self,
        ip: str,
        port: str,
        current_power_alias: str,
        power_calculate: bool,
        power_input_alias: str,
        power_output_alias: str,
    ):
        self.ip = ip
        self.port = port
        self.current_power_alias = current_power_alias
        self.power_calculate = power_calculate
        self.power_input_alias = power_input_alias
        self.power_output_alias = power_output_alias
        self.session = requests.Session()

    def get_json(self, path):
        url = f"http://{self.ip}:{self.port}{path}"
        return self.session.get(url, timeout=10).json()

    def get_powermeter_watts(self):
        if not self.power_calculate:
            response = self.get_json(f"/getBulk/{self.current_power_alias}")
            for item in response:
                if item["id"] == self.current_power_alias:
                    return [int(item["val"])]
        else:
            response = self.get_json(
                f"/getBulk/{self.power_input_alias},{self.power_output_alias}"
            )
            power_in = 0
            power_out = 0
            for item in response:
                if item["id"] == self.power_input_alias:
                    power_in = int(item["val"])
                if item["id"] == self.power_output_alias:
                    power_out = int(item["val"])
            return [power_in - power_out]
