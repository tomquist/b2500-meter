import json
import socket
import threading
import time
import unittest
from ipaddress import IPv4Network

from b2500_meter.config import ClientFilter
from b2500_meter.powermeter import Powermeter, ThrottledPowermeter
from b2500_meter.shelly.shelly import Shelly


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
            # Give the UDP server thread a brief moment to bind before sending requests.
            # Without this, first packets can be dropped and recvfrom() may block forever.
            time.sleep(0.05)

            responses = []
            errors = []
            responses_lock = threading.Lock()

            def send_req(i):
                req = {
                    "id": i,
                    "src": "cli",
                    "method": "EM.GetStatus",
                    "params": {"id": 0},
                }

                client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                client.settimeout(1.0)
                try:
                    client.sendto(json.dumps(req).encode(), ("127.0.0.1", port))
                    data, _ = client.recvfrom(1024)
                    with responses_lock:
                        responses.append(json.loads(data.decode())["id"])
                except TimeoutError:
                    with responses_lock:
                        errors.append(f"timeout for request id={i}")
                finally:
                    client.close()

            threads = []
            start = time.time()
            for i in range(3):
                t = threading.Thread(target=send_req, args=(i,))
                t.start()
                threads.append(t)
            for t in threads:
                t.join(timeout=2.0)
                self.assertFalse(t.is_alive(), "request thread did not finish")

            duration = time.time() - start
            self.assertEqual(errors, [])
            self.assertEqual(sorted(responses), [0, 1, 2])
            self.assertLess(duration, 0.6)
        finally:
            shelly.stop()


if __name__ == "__main__":
    unittest.main()
