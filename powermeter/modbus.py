from .base import Powermeter
from pymodbus.client import ModbusTcpClient


class ModbusPowermeter(Powermeter):
    def __init__(self, host, port, unit_id, address, count):
        self.host = host
        self.port = port
        self.unit_id = unit_id
        self.address = address
        self.count = count
        self.client = ModbusTcpClient(host, port=port)

    def get_powermeter_watts(self):
        result = self.client.read_holding_registers(
            self.address, self.count, unit=self.unit_id
        )
        if result.isError():
            raise Exception("Error reading Modbus data")
        return [float(result.registers[0])]
