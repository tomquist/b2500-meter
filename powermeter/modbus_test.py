import unittest
from unittest.mock import patch
from powermeter import ModbusPowermeter


class TestPowermeters(unittest.TestCase):

    @patch("powermeter.modbus.ModbusTcpClient")
    def test_modbuspowermeter_get_powermeter_watts(self, MockModbusTcpClient):
        mock_client = MockModbusTcpClient.return_value
        mock_client.read_holding_registers.return_value.isError.return_value = False
        mock_client.read_holding_registers.return_value.registers = [500]

        modbuspowermeter = ModbusPowermeter("192.168.1.14", 502, 1, 0, 1)
        self.assertEqual(modbuspowermeter.get_powermeter_watts(), [500])
        MockModbusTcpClient.assert_called_with("192.168.1.14", port=502)


if __name__ == "__main__":
    unittest.main()
