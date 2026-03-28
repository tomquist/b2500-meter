import unittest
from unittest.mock import patch

from b2500_meter.powermeter import ModbusPowermeter


class TestPowermeters(unittest.TestCase):
    @patch("b2500_meter.powermeter.modbus.ModbusTcpClient")
    def test_modbuspowermeter_get_powermeter_watts(self, MockModbusTcpClient):
        mock_client = MockModbusTcpClient.return_value
        mock_client.read_holding_registers.return_value.isError.return_value = False
        mock_client.read_holding_registers.return_value.registers = [500]

        modbuspowermeter = ModbusPowermeter("192.168.1.14", 502, 1, 0, 1)
        self.assertEqual(modbuspowermeter.get_powermeter_watts(), [500.0])
        MockModbusTcpClient.assert_called_with("192.168.1.14", port=502)
        mock_client.read_holding_registers.assert_called_once_with(0, 1, slave=1)

    @patch("b2500_meter.powermeter.modbus.ModbusTcpClient")
    def test_modbuspowermeter_float32(self, MockModbusTcpClient):
        mock_client = MockModbusTcpClient.return_value
        mock_client.read_holding_registers.return_value.isError.return_value = False
        mock_client.read_holding_registers.return_value.registers = [0x4120, 0x0000]

        modbuspowermeter = ModbusPowermeter(
            "192.168.1.14",
            502,
            1,
            0,
            2,
            data_type="FLOAT32",
            byte_order="BIG",
            word_order="BIG",
        )
        self.assertEqual(modbuspowermeter.get_powermeter_watts(), [10.0])
        mock_client.read_holding_registers.assert_called_once_with(0, 2, slave=1)

    @patch("b2500_meter.powermeter.modbus.ModbusTcpClient")
    def test_modbuspowermeter_input_registers(self, MockModbusTcpClient):
        mock_client = MockModbusTcpClient.return_value
        mock_client.read_input_registers.return_value.isError.return_value = False
        mock_client.read_input_registers.return_value.registers = [500]

        modbuspowermeter = ModbusPowermeter(
            "192.168.1.14", 502, 1, 0, 1, register_type="INPUT"
        )
        self.assertEqual(modbuspowermeter.get_powermeter_watts(), [500.0])
        mock_client.read_input_registers.assert_called_once_with(0, 1, slave=1)


if __name__ == "__main__":
    unittest.main()
