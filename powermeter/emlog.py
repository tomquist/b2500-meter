from .base import Powermeter
import requests


class Emlog(Powermeter):
    def __init__(self, ip: str, meterindex: str, json_power_calculate: bool):
        self.ip = ip
        self.meterindex = meterindex
        self.json_power_calculate = json_power_calculate
        self.session = requests.Session()

    def get_json(self, path):
        url = f"http://{self.ip}{path}"
        return self.session.get(url, timeout=10).json()

    def get_powermeter_watts(self):
        response = self.get_json(
            f"/pages/getinformation.php?heute&meterindex={self.meterindex}"
        )
        if not self.json_power_calculate:
            return [int(response["Leistung170"])]
        else:
            power_in = response["Leistung170"]
            power_out = response["Leistung270"]
            return [int(power_in) - int(power_out)]
