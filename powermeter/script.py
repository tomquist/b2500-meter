from .base import Powermeter
import subprocess


class Script(Powermeter):
    def __init__(self, command: str):
        self.script = command

    def get_powermeter_watts(self):
        power = (
            subprocess.check_output(self.script, shell=True)
            .decode()
            .strip()
            .split("\n")
        )
        return [float(p) for p in power]
