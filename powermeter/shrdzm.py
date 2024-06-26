from .base import Powermeter
import requests


class Shrdzm(Powermeter):
    def __init__(self, ip: str, user: str, password: str):
        self.ip = ip
        self.user = user
        self.password = password
        self.session = requests.Session()

    def get_json(self, path):
        url = f"http://{self.ip}{path}"
        return self.session.get(url, timeout=10).json()

    def get_powermeter_watts(self):
        response = self.get_json(
            f"/getLastData?user={self.user}&password={self.password}"
        )
        return [int(int(response["1.7.0"]) - int(response["2.7.0"]))]
