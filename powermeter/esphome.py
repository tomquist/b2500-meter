from .base import Powermeter
import requests


class ESPHome(Powermeter):
    def __init__(self, ip: str, port: str, domain: str, id: str):
        self.ip = ip
        self.port = port
        self.domain = domain
        self.id = id
        self.session = requests.Session()

    def get_json(self, path):
        url = f"http://{self.ip}:{self.port}{path}"
        return self.session.get(url, timeout=10).json()

    def get_powermeter_watts(self):
        ParsedData = self.get_json(f"/{self.domain}/{self.id}")
        return [int(ParsedData["value"])]
