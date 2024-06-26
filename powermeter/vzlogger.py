from .base import Powermeter
import requests


class VZLogger(Powermeter):
    def __init__(self, ip: str, port: str, uuid: str):
        self.ip = ip
        self.port = port
        self.uuid = uuid
        self.session = requests.Session()

    def get_json(self):
        url = f"http://{self.ip}:{self.port}/{self.uuid}"
        return self.session.get(url, timeout=10).json()

    def get_powermeter_watts(self):
        return [int(self.get_json()["data"][0]["tuples"][0][1])]
