from .base import Powermeter
import requests
from requests.auth import HTTPDigestAuth


class Shelly(Powermeter):
    def __init__(self, ip: str, user: str, password: str, emeterindex: str):
        self.ip = ip
        self.user = user
        self.password = password
        self.emeterindex = emeterindex
        self.session = requests.Session()

    def get_json(self, path):
        url = f"http://{self.ip}{path}"
        headers = {"content-type": "application/json"}
        return self.session.get(
            url, headers=headers, auth=(self.user, self.password), timeout=10
        ).json()

    def get_rpc_json(self, path):
        url = f"http://{self.ip}/rpc{path}"
        headers = {"content-type": "application/json"}
        return self.session.get(
            url,
            headers=headers,
            auth=HTTPDigestAuth(self.user, self.password),
            timeout=10,
        ).json()

    def get_powermeter_watts(self):
        raise NotImplementedError()


class Shelly1PM(Shelly):
    def get_powermeter_watts(self):
        status = self.get_json("/status")
        if self.emeterindex:
            return [int(self.get_json(f"/meter/{self.emeterindex}")["power"])]
        else:
            return [int(meter["power"]) for meter in status["meters"]]


class ShellyPlus1PM(Shelly):
    def get_powermeter_watts(self):
        return [int(self.get_rpc_json("/Switch.GetStatus?id=0")["apower"])]


class ShellyEM(Shelly):
    def get_powermeter_watts(self):
        if self.emeterindex:
            return [int(self.get_json(f"/emeter/{self.emeterindex}")["power"])]
        else:
            status = self.get_json("/status")
            return [int(emeter["power"]) for emeter in status["emeters"]]


class Shelly3EM(Shelly):

    def get_powermeter_watts(self):
        status = self.get_json("/status")
        # Return an array of all power values
        return [int(emeter["power"]) for emeter in status["emeters"]]


class Shelly3EMPro(Shelly):
    def get_powermeter_watts(self):
        response = self.get_rpc_json("/EM.GetStatus?id=0")
        return [int(response["total_act_power"])]
