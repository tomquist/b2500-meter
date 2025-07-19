import unittest
import socket
import json
import threading
import time
from ipaddress import IPv4Network

from config import ClientFilter
from powermeter import Powermeter, ThrottledPowermeter
from shelly.shelly import Shelly


class DummyPowermeter(Powermeter):
    def get_powermeter_watts(self):
        return [1.0]


class TestShellyUDP(unittest.TestCase):
    def test_multiple_requests_with_throttling(self):
        pm = ThrottledPowermeter(DummyPowermeter(), throttle_interval=0.2)
        cf = ClientFilter([IPv4Network("127.0.0.1/32")])

        tmp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        tmp.bind(("", 0))
        port = tmp.getsockname()[1]
        tmp.close()

        shelly = Shelly([(pm, cf)], udp_port=port, device_id="test")
        shelly.start()
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            responses = []

            def send_req(i):
                req = {
                    "id": i,
                    "src": "cli",
                    "method": "EM.GetStatus",
                    "params": {"id": 0},
                }
                client.sendto(json.dumps(req).encode(), ("127.0.0.1", port))
                data, _ = client.recvfrom(1024)
                responses.append(json.loads(data.decode())["id"])

            threads = []
            start = time.time()
            for i in range(3):
                t = threading.Thread(target=send_req, args=(i,))
                t.start()
                threads.append(t)
            for t in threads:
                t.join()
            duration = time.time() - start
            self.assertEqual(sorted(responses), [0, 1, 2])
            self.assertLess(duration, 0.6)
        finally:
            client.close()
            # send dummy packet to unblock server if waiting on recv
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.sendto(b"{}", ("127.0.0.1", port))
            shelly.stop()


if __name__ == "__main__":
    unittest.main()
