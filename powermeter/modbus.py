from .base import Powermeter
from pymodbus.client import ModbusTcpClient
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.constants import Endian


DATA_TYPE_DECODERS = {
    "FLOAT32": "decode_32bit_float",
    "INT16": "decode_16bit_int",
    "UINT16": "decode_16bit_uint",
    "INT32": "decode_32bit_int",
    "UINT32": "decode_32bit_uint",
}

BYTE_ORDERS = {
    "BIG": Endian.BIG,
    "LITTLE": Endian.LITTLE,
}


class ModbusPowermeter(Powermeter):
    def __init__(
        self,
        host,
        port,
        unit_id,
        address,
        count,
        data_type="UINT16",
        byte_order="BIG",
        word_order="BIG",
    ):
        self.host = host
        self.port = port
        self.unit_id = unit_id
        self.address = address
        self.count = count
        self.data_type = data_type.upper()
        self.byte_order = byte_order.upper()
        self.word_order = word_order.upper()

        self._byte_order = BYTE_ORDERS.get(self.byte_order, Endian.BIG)
        self._word_order = BYTE_ORDERS.get(self.word_order, Endian.BIG)
        self._decode_method = DATA_TYPE_DECODERS.get(self.data_type)
        if not self._decode_method:
            raise ValueError(f"Unsupported data type: {data_type}")

        self.client = ModbusTcpClient(host, port=port)

    def get_powermeter_watts(self):
        result = self.client.read_holding_registers(
            self.address, self.count, unit=self.unit_id
        )
        if result.isError():
            raise Exception("Error reading Modbus data")
        decoder = BinaryPayloadDecoder.fromRegisters(
            result.registers,
            byteorder=self._byte_order,
            wordorder=self._word_order,
        )
        value = getattr(decoder, self._decode_method)()
        return [float(value)]
