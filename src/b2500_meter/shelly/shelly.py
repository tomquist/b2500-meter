import json
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from b2500_meter.config import ClientFilter
from b2500_meter.config.logger import logger
from b2500_meter.powermeter import Powermeter

BATTERY_INACTIVE_TIMEOUT_SECONDS = 120


class Shelly:
    def __init__(
        self,
        powermeters: list[tuple[Powermeter, ClientFilter]],
        udp_port: int,
        device_id,
    ):
        self._udp_port = udp_port
        self._device_id = device_id
        self._powermeters = powermeters
        self._udp_thread: threading.Thread | None = None
        self._stop = False
        self._value_mutex = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=5)
        self._send_lock = threading.Lock()
        self._battery_state_lock = threading.Lock()
        self._battery_last_seen: dict[str, float] = {}
        self._inactive_batteries: set[str] = set()

    def _calculate_derived_values(self, power):
        decimal_point_enforcer = 0.001
        if abs(power) < 0.1:
            return decimal_point_enforcer

        return round(
            power
            + (decimal_point_enforcer if power == round(power) or power == 0 else 0),
            1,
        )

    def _create_em_response(self, request_id, powers):
        if len(powers) == 1:
            powers = [powers[0], 0, 0]
        elif len(powers) != 3:
            powers = [0, 0, 0]

        a = self._calculate_derived_values(powers[0])
        b = self._calculate_derived_values(powers[1])
        c = self._calculate_derived_values(powers[2])

        total_act_power = round(sum(powers), 3)
        total_act_power = total_act_power + (
            0.001
            if total_act_power == round(total_act_power) or total_act_power == 0
            else 0
        )

        return {
            "id": request_id,
            "src": self._device_id,
            "dst": "unknown",
            "result": {
                "a_act_power": a,
                "b_act_power": b,
                "c_act_power": c,
                "total_act_power": total_act_power,
            },
        }

    def _create_em1_response(self, request_id, powers):
        total_power = round(sum(powers), 3)
        total_power = total_power + (
            0.001 if total_power == round(total_power) or total_power == 0 else 0
        )

        return {
            "id": request_id,
            "src": self._device_id,
            "dst": "unknown",
            "result": {
                "act_power": total_power,
            },
        }

    def _track_battery_seen(self, addr):
        battery_ip = addr[0]
        now = time.time()

        with self._battery_state_lock:
            first_seen = battery_ip not in self._battery_last_seen
            was_inactive = battery_ip in self._inactive_batteries
            self._battery_last_seen[battery_ip] = now
            if was_inactive:
                self._inactive_batteries.remove(battery_ip)

        if first_seen:
            logger.info(
                "Battery detected on Shelly UDP port %s: %s",
                self._udp_port,
                battery_ip,
            )
        elif was_inactive:
            logger.info(
                "Battery reconnected on Shelly UDP port %s after inactivity: %s",
                self._udp_port,
                battery_ip,
            )

    def _log_inactive_batteries(self):
        now = time.time()
        newly_inactive_batteries = []

        with self._battery_state_lock:
            for battery_ip, last_seen in self._battery_last_seen.items():
                if (
                    now - last_seen >= BATTERY_INACTIVE_TIMEOUT_SECONDS
                    and battery_ip not in self._inactive_batteries
                ):
                    self._inactive_batteries.add(battery_ip)
                    newly_inactive_batteries.append(battery_ip)

        for battery_ip in newly_inactive_batteries:
            logger.info(
                "Battery inactive on Shelly UDP port %s for >= %ss: %s",
                self._udp_port,
                BATTERY_INACTIVE_TIMEOUT_SECONDS,
                battery_ip,
            )

    def _handle_request(self, sock, data, addr):
        request_str = data.decode()
        self._track_battery_seen(addr)
        logger.debug(f"Received UDP message: {request_str}")
        logger.debug(f"From: {addr[0]}:{addr[1]}")

        try:
            request = json.loads(request_str)
            logger.debug(f"Parsed request: {json.dumps(request, indent=2)}")
            if isinstance(request.get("params", {}).get("id"), int):
                powermeter = None
                for pm, client_filter in self._powermeters:
                    if client_filter.matches(addr[0]):
                        powermeter = pm
                        break
                if powermeter is None:
                    logger.warning(f"No powermeter found for client {addr[0]}")
                    return

                powers = powermeter.get_powermeter_watts()

                if request.get("method") == "EM.GetStatus":
                    response = self._create_em_response(request["id"], powers)
                elif request.get("method") == "EM1.GetStatus":
                    response = self._create_em1_response(request["id"], powers)
                else:
                    return

                response_json = json.dumps(response, separators=(",", ":"))
                logger.debug(f"Sending response: {response_json}")
                response_data = response_json.encode()
                with self._send_lock:
                    sock.sendto(response_data, addr)
        except json.JSONDecodeError:
            logger.error("Error: Invalid JSON")
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def udp_server(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(1.0)
        sock.bind(("", self._udp_port))
        logger.info(f"Shelly emulator listening on UDP port {self._udp_port}...")

        try:
            while not self._stop:
                try:
                    data, addr = sock.recvfrom(1024)
                except TimeoutError:
                    self._log_inactive_batteries()
                    continue

                self._executor.submit(self._handle_request, sock, data, addr)
                self._log_inactive_batteries()

        finally:
            sock.close()

    def start(self):
        if self._udp_thread:
            return
        self._stop = False
        self._udp_thread = threading.Thread(target=self.udp_server)
        self._udp_thread.start()

    def join(self):
        if self._udp_thread:
            self._udp_thread.join()

    def stop(self):
        self._stop = True
        if self._udp_thread:
            self._udp_thread.join()
            self._udp_thread = None
        self._executor.shutdown(wait=True)
