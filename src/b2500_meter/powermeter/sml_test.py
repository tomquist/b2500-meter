import configparser
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from b2500_meter.config.config_loader import create_sml_powermeter
from b2500_meter.powermeter.sml import (
    _OBIS_POWER_CURRENT,
    _OBIS_POWER_L1,
    _OBIS_POWER_L2,
    _OBIS_POWER_L3,
    EnergyStats,
    parse_sml_obis_config,
)


def _obis_value(obis: str, value: int, unit: int) -> SimpleNamespace:
    return SimpleNamespace(obis=obis, value=value, unit=unit)


def _defaults():
    return (_OBIS_POWER_CURRENT, _OBIS_POWER_L1, _OBIS_POWER_L2, _OBIS_POWER_L3)


class TestEnergyStatsFromSmlFrame(unittest.TestCase):
    def test_aggregate_only(self):
        frame = MagicMock()
        frame.get_obis.return_value = [
            _obis_value(_OBIS_POWER_CURRENT, 1500, 27),
        ]
        stats = EnergyStats.from_sml_frame(frame, *_defaults())
        self.assertEqual(stats.powers, [1500])

    def test_multiphase_when_all_phases_present(self):
        frame = MagicMock()
        frame.get_obis.return_value = [
            _obis_value(_OBIS_POWER_L1, 100, 27),
            _obis_value(_OBIS_POWER_L2, 200, 27),
            _obis_value(_OBIS_POWER_L3, 300, 27),
        ]
        stats = EnergyStats.from_sml_frame(frame, *_defaults())
        self.assertEqual(stats.powers, [100, 200, 300])

    def test_prefers_multiphase_when_aggregate_also_present(self):
        frame = MagicMock()
        frame.get_obis.return_value = [
            _obis_value(_OBIS_POWER_CURRENT, 9999, 27),
            _obis_value(_OBIS_POWER_L1, 100, 27),
            _obis_value(_OBIS_POWER_L2, 200, 27),
            _obis_value(_OBIS_POWER_L3, 300, 27),
        ]
        stats = EnergyStats.from_sml_frame(frame, *_defaults())
        self.assertEqual(stats.powers, [100, 200, 300])

    def test_falls_back_to_aggregate_if_incomplete_phases(self):
        frame = MagicMock()
        frame.get_obis.return_value = [
            _obis_value(_OBIS_POWER_CURRENT, 1500, 27),
            _obis_value(_OBIS_POWER_L1, 100, 27),
            _obis_value(_OBIS_POWER_L2, 200, 27),
        ]
        stats = EnergyStats.from_sml_frame(frame, *_defaults())
        self.assertEqual(stats.powers, [1500])

    def test_wrong_unit_raises(self):
        frame = MagicMock()
        frame.get_obis.return_value = [_obis_value(_OBIS_POWER_CURRENT, 1500, 30)]
        with self.assertRaises(ValueError) as ctx:
            EnergyStats.from_sml_frame(frame, *_defaults())
        self.assertIn("aggregate power", str(ctx.exception).lower())
        self.assertIn("1500", str(ctx.exception))


class TestParseSmlObisConfig(unittest.TestCase):
    def test_defaults_when_empty(self):
        config = configparser.ConfigParser()
        config.read_string("[SML]\n")
        t = parse_sml_obis_config("SML", config)
        self.assertEqual(t, _defaults())

    def test_override_normalized(self):
        config = configparser.ConfigParser()
        config.read_string("[SML]\nOBIS_POWER_CURRENT = 0100100700FF\n")
        oc, o1, _o2, _o3 = parse_sml_obis_config("SML", config)
        self.assertEqual(oc, "0100100700ff")
        self.assertEqual(o1, _OBIS_POWER_L1)

    def test_invalid_length_raises(self):
        config = configparser.ConfigParser()
        config.read_string("[SML]\nOBIS_POWER_CURRENT = deadbeef\n")
        with self.assertRaises(ValueError):
            parse_sml_obis_config("SML", config)


class TestCreateSmlPowermeter(unittest.TestCase):
    def test_missing_serial_raises(self):
        config = configparser.ConfigParser()
        config.read_string("[SML]\n")
        with self.assertRaises(ValueError) as ctx:
            create_sml_powermeter("SML", config)
        self.assertIn("SERIAL", str(ctx.exception))

    def test_serial_trimmed(self):
        config = configparser.ConfigParser()
        config.read_string("[SML]\nSERIAL = /dev/ttyAMA0\n")
        pm = create_sml_powermeter("SML", config)
        self.assertEqual(pm._serial_device, "/dev/ttyAMA0")

    def test_custom_obis_passed_to_sml(self):
        config = configparser.ConfigParser()
        config.read_string(
            "[SML]\n"
            "SERIAL = /dev/ttyUSB0\n"
            "OBIS_POWER_CURRENT = 0100100700ff\n"
            "OBIS_POWER_L1 = 0100240700ff\n"
            "OBIS_POWER_L2 = 0100380700ff\n"
            "OBIS_POWER_L3 = 01004c0700ff\n"
        )
        pm = create_sml_powermeter("SML", config)
        self.assertEqual(pm._obis_current, "0100100700ff")
        self.assertEqual(pm._obis_l1, "0100240700ff")
