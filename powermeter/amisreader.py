from .base import Powermeter
import requests


class AmisReader(Powermeter):
    def __init__(self, ip: str):
        self.ip = ip
        self.session = requests.Session()

    def get_json(self, path):
        url = f"http://{self.ip}{path}"
        return self.session.get(url, timeout=10).json()

    def get_powermeter_watts(self):
        response = self.get_json("/rest")
        return [int(response["saldo"])]
