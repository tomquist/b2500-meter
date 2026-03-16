import unittest
import json
import socket
import threading
from http.client import HTTPConnection

from shelly.shelly_http import (
    ShellyHttpServer,
    build_device_info,
    build_em_status,
    build_emdata_status,
    build_shelly_status,
)


class FakeShellyRef:
    """Minimal stand-in for the Shelly object used by the HTTP handler."""

    def __init__(self, device_id="shellypro3em-aabbccddeeff", mac="AABBCCDDEEFF"):
        self.device_id = device_id
        self.mac = mac
        self._powers = [100.0, -50.0, 25.0]

    def get_powers(self):
        return list(self._powers)


def _free_port():
    s = socket.socket()
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class TestBuildDeviceInfo(unittest.TestCase):
    def test_device_info_fields(self):
        info = build_device_info("shellypro3em-aabbccddeeff", "AABBCCDDEEFF")
        self.assertEqual(info["id"], "shellypro3em-aabbccddeeff")
        self.assertEqual(info["mac"], "AABBCCDDEEFF")
        self.assertEqual(info["model"], "SPEM-003CEBEU")
        self.assertEqual(info["gen"], 2)
        self.assertFalse(info["auth_en"])


class TestBuildEmStatus(unittest.TestCase):
    def test_three_phase(self):
        status = build_em_status([100.0, -50.0, 25.0])
        self.assertAlmostEqual(status["a_act_power"], 100.0)
        self.assertAlmostEqual(status["b_act_power"], -50.0)
        self.assertAlmostEqual(status["c_act_power"], 25.0)
        self.assertAlmostEqual(status["total_act_power"], 75.0)
        self.assertGreater(status["a_current"], 0)
        self.assertEqual(status["a_voltage"], 230.0)

    def test_single_phase_padded(self):
        status = build_em_status([200.0])
        self.assertAlmostEqual(status["a_act_power"], 200.0)
        self.assertAlmostEqual(status["b_act_power"], 0.0)
        self.assertAlmostEqual(status["c_act_power"], 0.0)

    def test_zero_power(self):
        status = build_em_status([0, 0, 0])
        self.assertEqual(status["a_pf"], 0.0)
        self.assertEqual(status["total_act_power"], 0.0)


class TestBuildEmdataStatus(unittest.TestCase):
    def test_all_zeros(self):
        status = build_emdata_status()
        self.assertEqual(status["total_act"], 0.0)
        self.assertEqual(status["a_total_act_energy"], 0.0)


class TestBuildShellyStatus(unittest.TestCase):
    def test_combined_status(self):
        status = build_shelly_status([100, -50, 25], "AABBCCDDEEFF")
        self.assertIn("sys", status)
        self.assertIn("em:0", status)
        self.assertIn("emdata:0", status)
        self.assertEqual(status["sys"]["mac"], "AABBCCDDEEFF")


class TestShellyHttpServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = _free_port()
        cls.shelly = FakeShellyRef()
        cls.server = ShellyHttpServer(cls.shelly, cls.port)
        cls.server.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def _get(self, path):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", path)
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        return resp.status, json.loads(body)

    def test_shelly_endpoint(self):
        status, data = self._get("/shelly")
        self.assertEqual(status, 200)
        self.assertEqual(data["id"], "shellypro3em-aabbccddeeff")
        self.assertEqual(data["gen"], 2)

    def test_device_info_endpoint(self):
        status, data = self._get("/rpc/Shelly.GetDeviceInfo")
        self.assertEqual(status, 200)
        self.assertEqual(data["model"], "SPEM-003CEBEU")

    def test_em_get_status(self):
        status, data = self._get("/rpc/EM.GetStatus?id=0")
        self.assertEqual(status, 200)
        self.assertAlmostEqual(data["a_act_power"], 100.0)
        self.assertAlmostEqual(data["b_act_power"], -50.0)
        self.assertAlmostEqual(data["c_act_power"], 25.0)
        self.assertAlmostEqual(data["total_act_power"], 75.0)

    def test_emdata_get_status(self):
        status, data = self._get("/rpc/EMData.GetStatus?id=0")
        self.assertEqual(status, 200)
        self.assertEqual(data["total_act"], 0.0)

    def test_shelly_get_status(self):
        status, data = self._get("/rpc/Shelly.GetStatus")
        self.assertEqual(status, 200)
        self.assertIn("sys", data)
        self.assertIn("em:0", data)
        self.assertIn("emdata:0", data)

    def test_not_found(self):
        status, data = self._get("/nonexistent")
        self.assertEqual(status, 404)

    def test_power_values_update(self):
        self.shelly._powers = [500.0, -200.0, 100.0]
        status, data = self._get("/rpc/EM.GetStatus?id=0")
        self.assertAlmostEqual(data["a_act_power"], 500.0)
        self.assertAlmostEqual(data["total_act_power"], 400.0)
        self.shelly._powers = [100.0, -50.0, 25.0]


if __name__ == "__main__":
    unittest.main()
