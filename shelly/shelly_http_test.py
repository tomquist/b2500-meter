import unittest
import json
import socket
import struct
import threading
import hashlib
import base64
import os
import time
from http.client import HTTPConnection

from shelly.shelly_http import (
    ShellyHttpServer,
    build_device_info,
    build_em_status,
    build_emdata_status,
    build_shelly_status,
    build_shelly_config,
)


class FakeShellyRef:
    """Minimal stand-in for the Shelly object used by the HTTP handler."""

    def __init__(self, device_id="shellypro3em-aabbccddeeff", mac="AABBCCDDEEFF"):
        self.device_id = device_id
        self.mac = mac
        self._powers = [100.0, -50.0, 25.0]

    def get_powers(self):
        return list(self._powers)

    def get_cached_powers(self):
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


class TestBuildShellyConfig(unittest.TestCase):
    def test_config_structure(self):
        config = build_shelly_config("AABBCCDDEEFF")
        self.assertIn("em:0", config)
        self.assertIn("emdata:0", config)
        self.assertIn("sys", config)
        self.assertEqual(config["sys"]["device"]["mac"], "AABBCCDDEEFF")
        self.assertEqual(config["em:0"]["ct_type"], "120A")
        self.assertEqual(config["sys"]["device"]["profile"], "triphase")


def _wait_for_server(port, timeout=5):
    """Wait until the server is accepting connections."""
    import time
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            s = socket.socket()
            s.settimeout(0.5)
            s.connect(("127.0.0.1", port))
            s.close()
            return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"Server on port {port} not ready after {timeout}s")


class TestShellyHttpServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = _free_port()
        cls.shelly = FakeShellyRef()
        cls.server = ShellyHttpServer(cls.shelly, cls.port)
        cls.server.start()
        _wait_for_server(cls.port)

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

    def test_shelly_get_config(self):
        status, data = self._get("/rpc/Shelly.GetConfig")
        self.assertEqual(status, 200)
        self.assertIn("em:0", data)
        self.assertIn("sys", data)
        self.assertEqual(data["sys"]["device"]["mac"], "AABBCCDDEEFF")

    def test_shelly_get_components(self):
        status, data = self._get("/rpc/Shelly.GetComponents")
        self.assertEqual(status, 200)
        self.assertEqual(data["components"], [])
        self.assertEqual(data["total"], 0)

    def test_not_found(self):
        status, data = self._get("/nonexistent")
        self.assertEqual(status, 404)

    def test_power_values_update(self):
        self.shelly._powers = [500.0, -200.0, 100.0]
        status, data = self._get("/rpc/EM.GetStatus?id=0")
        self.assertAlmostEqual(data["a_act_power"], 500.0)
        self.assertAlmostEqual(data["total_act_power"], 400.0)
        self.shelly._powers = [100.0, -50.0, 25.0]


class TestShellyWebSocket(unittest.TestCase):
    """Test WebSocket JSON-RPC endpoint."""

    @classmethod
    def setUpClass(cls):
        cls.port = _free_port()
        cls.shelly = FakeShellyRef()
        cls.server = ShellyHttpServer(cls.shelly, cls.port)
        cls.server.start()
        _wait_for_server(cls.port)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def _ws_connect(self):
        """Perform WebSocket handshake and return the socket."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect(("127.0.0.1", self.port))

        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET /rpc HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{self.port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n"
            f"\r\n"
        )
        s.sendall(request.encode())

        # Read the HTTP response
        resp = b""
        while b"\r\n\r\n" not in resp:
            resp += s.recv(4096)

        self.assertIn(b"101", resp)
        self.assertIn(b"Upgrade: websocket", resp)
        return s

    def _ws_send(self, sock, data):
        """Send a masked WebSocket text frame."""
        payload = json.dumps(data).encode()
        frame = bytearray([0x81])  # FIN + text
        mask_key = os.urandom(4)
        length = len(payload)
        if length < 126:
            frame.append(0x80 | length)
        elif length < 65536:
            frame.append(0x80 | 126)
            frame.extend(struct.pack("!H", length))
        else:
            frame.append(0x80 | 127)
            frame.extend(struct.pack("!Q", length))
        frame.extend(mask_key)
        frame.extend(bytearray(b ^ mask_key[i % 4] for i, b in enumerate(payload)))
        sock.sendall(bytes(frame))

    def _ws_recv(self, sock):
        """Read one WebSocket frame and return parsed JSON."""
        header = sock.recv(2)
        self.assertEqual(len(header), 2)
        length = header[1] & 0x7F
        if length == 126:
            length = struct.unpack("!H", sock.recv(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", sock.recv(8))[0]

        data = b""
        while len(data) < length:
            chunk = sock.recv(length - len(data))
            if not chunk:
                break
            data += chunk
        return json.loads(data)

    def _ws_close(self, sock):
        """Send a close frame and close the socket."""
        frame = bytearray([0x88, 0x80])  # FIN + close, masked, 0 length
        frame.extend(os.urandom(4))  # mask key
        try:
            sock.sendall(bytes(frame))
        except Exception:
            pass
        sock.close()

    def test_ws_handshake(self):
        sock = self._ws_connect()
        self._ws_close(sock)

    def test_ws_get_device_info(self):
        sock = self._ws_connect()
        self._ws_send(sock, {
            "id": 1,
            "src": "test-client",
            "method": "Shelly.GetDeviceInfo",
        })
        resp = self._ws_recv(sock)
        self.assertEqual(resp["id"], 1)
        self.assertIn("result", resp)
        self.assertEqual(resp["result"]["model"], "SPEM-003CEBEU")
        self.assertEqual(resp["src"], "shellypro3em-aabbccddeeff")
        self.assertEqual(resp["dst"], "test-client")
        self._ws_close(sock)

    def test_ws_em_get_status(self):
        sock = self._ws_connect()
        self._ws_send(sock, {
            "id": 2,
            "src": "test",
            "method": "EM.GetStatus",
            "params": {"id": 0},
        })
        resp = self._ws_recv(sock)
        self.assertEqual(resp["id"], 2)
        result = resp["result"]
        self.assertAlmostEqual(result["a_act_power"], 100.0)
        self.assertAlmostEqual(result["total_act_power"], 75.0)
        self._ws_close(sock)

    def test_ws_get_config(self):
        sock = self._ws_connect()
        self._ws_send(sock, {
            "id": 3,
            "src": "test",
            "method": "Shelly.GetConfig",
        })
        resp = self._ws_recv(sock)
        self.assertEqual(resp["id"], 3)
        self.assertIn("em:0", resp["result"])
        self.assertIn("sys", resp["result"])
        self._ws_close(sock)

    def test_ws_unknown_method(self):
        sock = self._ws_connect()
        self._ws_send(sock, {
            "id": 4,
            "src": "test",
            "method": "Unknown.Method",
        })
        resp = self._ws_recv(sock)
        self.assertEqual(resp["id"], 4)
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["code"], -114)
        self._ws_close(sock)

    def test_ws_notify_status(self):
        """After the first RPC exchange, the server should push NotifyStatus."""
        sock = self._ws_connect()
        # Send any RPC to trigger the notify loop
        self._ws_send(sock, {
            "id": 1,
            "src": "test",
            "method": "Shelly.GetDeviceInfo",
        })
        # Read the RPC response
        resp = self._ws_recv(sock)
        self.assertEqual(resp["id"], 1)

        # Wait for a NotifyStatus push (WS_NOTIFY_INTERVAL=5s, but we override)
        # The notify loop will fire after WS_NOTIFY_INTERVAL seconds
        sock.settimeout(8)
        try:
            notify = self._ws_recv(sock)
            self.assertEqual(notify["method"], "NotifyStatus")
            self.assertIn("em:0", notify["params"])
            self.assertIn("emdata:0", notify["params"])
        except socket.timeout:
            self.fail("Did not receive NotifyStatus within timeout")
        finally:
            self._ws_close(sock)


if __name__ == "__main__":
    unittest.main()
