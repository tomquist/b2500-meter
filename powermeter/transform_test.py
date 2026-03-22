import unittest
from unittest.mock import Mock
from .transform import TransformedPowermeter


class TestTransformedPowermeter(unittest.TestCase):
    def setUp(self):
        self.mock_powermeter = Mock()

    def test_identity_single_phase(self):
        self.mock_powermeter.get_powermeter_watts.return_value = [500.0]
        t = TransformedPowermeter(self.mock_powermeter, [0.0], [1.0])
        self.assertEqual(t.get_powermeter_watts(), [500.0])

    def test_identity_three_phase(self):
        self.mock_powermeter.get_powermeter_watts.return_value = [100.0, 200.0, 300.0]
        t = TransformedPowermeter(self.mock_powermeter, [0.0], [1.0])
        self.assertEqual(t.get_powermeter_watts(), [100.0, 200.0, 300.0])

    def test_offset_only_broadcast(self):
        self.mock_powermeter.get_powermeter_watts.return_value = [100.0, 200.0, 300.0]
        t = TransformedPowermeter(self.mock_powermeter, [10.0], [1.0])
        self.assertEqual(t.get_powermeter_watts(), [110.0, 210.0, 310.0])

    def test_negative_offset(self):
        self.mock_powermeter.get_powermeter_watts.return_value = [1050.0]
        t = TransformedPowermeter(self.mock_powermeter, [-50.0], [1.0])
        self.assertEqual(t.get_powermeter_watts(), [1000.0])

    def test_multiplier_only_broadcast(self):
        self.mock_powermeter.get_powermeter_watts.return_value = [100.0, 200.0, 300.0]
        t = TransformedPowermeter(self.mock_powermeter, [0.0], [2.0])
        self.assertEqual(t.get_powermeter_watts(), [200.0, 400.0, 600.0])

    def test_both_offset_and_multiplier(self):
        # 1050 * 0.95 + (-50) = 947.5
        self.mock_powermeter.get_powermeter_watts.return_value = [1050.0]
        t = TransformedPowermeter(self.mock_powermeter, [-50.0], [0.95])
        result = t.get_powermeter_watts()
        self.assertAlmostEqual(result[0], 947.5)

    def test_negative_meter_values_with_multiplier(self):
        self.mock_powermeter.get_powermeter_watts.return_value = [-100.0]
        t = TransformedPowermeter(self.mock_powermeter, [0.0], [2.0])
        self.assertEqual(t.get_powermeter_watts(), [-200.0])

    def test_per_phase_offsets(self):
        self.mock_powermeter.get_powermeter_watts.return_value = [100.0, 200.0, 300.0]
        t = TransformedPowermeter(self.mock_powermeter, [-10.0, -20.0, -30.0], [1.0])
        self.assertEqual(t.get_powermeter_watts(), [90.0, 180.0, 270.0])

    def test_per_phase_multipliers(self):
        self.mock_powermeter.get_powermeter_watts.return_value = [100.0, 200.0, 300.0]
        t = TransformedPowermeter(self.mock_powermeter, [0.0], [1.05, 1.02, 1.03])
        result = t.get_powermeter_watts()
        self.assertAlmostEqual(result[0], 105.0)
        self.assertAlmostEqual(result[1], 204.0)
        self.assertAlmostEqual(result[2], 309.0)

    def test_mixed_single_offset_per_phase_multipliers(self):
        self.mock_powermeter.get_powermeter_watts.return_value = [100.0, 200.0, 300.0]
        t = TransformedPowermeter(self.mock_powermeter, [10.0], [1.0, 2.0, 3.0])
        self.assertEqual(t.get_powermeter_watts(), [110.0, 410.0, 910.0])

    def test_phase_count_mismatch_does_not_crash(self):
        """Per-phase count != returned value count should warn, not raise."""
        self.mock_powermeter.get_powermeter_watts.return_value = [100.0]
        t = TransformedPowermeter(self.mock_powermeter, [10.0, 20.0, 30.0], [1.0])
        # Should not raise; uses cyclic indexing
        result = t.get_powermeter_watts()
        self.assertEqual(result, [110.0])

    def test_int_values_from_powermeter(self):
        """Many powermeters return int values; transform should handle them."""
        self.mock_powermeter.get_powermeter_watts.return_value = [100, 200]
        t = TransformedPowermeter(self.mock_powermeter, [0.5], [1.0])
        self.assertEqual(t.get_powermeter_watts(), [100.5, 200.5])

    def test_wait_for_message_passthrough(self):
        t = TransformedPowermeter(self.mock_powermeter, [0.0], [1.0])
        t.wait_for_message(timeout=30)
        self.mock_powermeter.wait_for_message.assert_called_once()
        call_args = self.mock_powermeter.wait_for_message.call_args
        if call_args[1]:
            self.assertEqual(call_args[1]["timeout"], 30)
        else:
            self.assertEqual(call_args[0][0], 30)

    def test_wait_for_message_default_timeout(self):
        t = TransformedPowermeter(self.mock_powermeter, [0.0], [1.0])
        t.wait_for_message()
        self.mock_powermeter.wait_for_message.assert_called_once()
        call_args = self.mock_powermeter.wait_for_message.call_args
        if call_args[1]:
            self.assertEqual(call_args[1]["timeout"], 5)
        else:
            self.assertEqual(call_args[0][0], 5)


if __name__ == "__main__":
    unittest.main()
