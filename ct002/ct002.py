import socket
import threading
import time
import inspect
import json
from typing import Optional
from config.logger import logger

SOH = 0x01
STX = 0x02
ETX = 0x03
SEPARATOR = "|"
UDP_PORT = 12345

RESPONSE_LABELS = [
    "meter_dev_type",
    "meter_mac_code",
    "hhm_dev_type",
    "hhm_mac_code",
    "A_phase_power",
    "B_phase_power",
    "C_phase_power",
    "total_power",
    "A_chrg_nb",
    "B_chrg_nb",
    "C_chrg_nb",
    "ABC_chrg_nb",
    "wifi_rssi",
    "info_idx",
    "x_chrg_power",
    "A_chrg_power",
    "B_chrg_power",
    "C_chrg_power",
    "ABC_chrg_power",
    "x_dchrg_power",
    "A_dchrg_power",
    "B_dchrg_power",
    "C_dchrg_power",
    "ABC_dchrg_power",
]


def calculate_checksum(data_bytes):
    xor = 0
    for b in data_bytes:
        xor ^= b
    return xor



def calculate_checksum_payload(data_bytes):
    if len(data_bytes) < 5:
        return calculate_checksum(data_bytes)
    sep_index = data_bytes.find(b"|", 2)
    if sep_index == -1:
        return calculate_checksum(data_bytes)
    xor = 0
    for b in data_bytes[sep_index:]:
        xor ^= b
    return xor
def parse_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def compute_length(payload_without_length):
    base_size = 1 + 1 + len(payload_without_length) + 1 + 2
    for length_digits in range(1, 5):
        total_length = base_size + length_digits
        if len(str(total_length)) == length_digits:
            return total_length
    raise ValueError("Payload length too large")


def build_payload(fields):
    message_str = SEPARATOR + SEPARATOR.join(fields)
    message_bytes = message_str.encode("ascii")
    total_length = compute_length(message_bytes)
    payload = bytearray([SOH, STX])
    payload.extend(str(total_length).encode("ascii"))
    payload.extend(message_bytes)
    payload.append(ETX)
    checksum_val = calculate_checksum(payload)
    checksum = f"{checksum_val:02x}".encode("ascii")
    payload.extend(checksum)
    return payload



def parse_request_lenient(data):
    fields, error = parse_request(data)
    if error and error.startswith("Checksum mismatch"):
        # Retry checksum check but continue parsing if the structure is otherwise valid.
        try:
            sep_index = data.find(b"|", 2)
            message = data[sep_index:-3].decode("ascii")
            fields = message.split("|")[1:]
            xor = 0
            for b in data[:-2]:
                xor ^= b
            expected_checksum = f"{xor:02x}".encode("ascii")
            actual_checksum = data[-2:]
            logger.debug(
                "CT002 request checksum mismatch (expected %s, got %s)",
                expected_checksum,
                actual_checksum,
            )
            return fields, None
        except Exception as exc:
            return None, str(exc)
    return fields, error
def parse_request(data):
    if len(data) < 10:
        return None, "Too short"
    if data[0] != SOH or data[1] != STX:
        return None, "Missing SOH/STX"
    sep_index = data.find(b"|", 2)
    if sep_index == -1:
        return None, "No separator after length"
    try:
        length = int(data[2:sep_index].decode("ascii"))
    except ValueError:
        return None, "Invalid length field"
    if len(data) != length:
        return None, "Length mismatch (expected %s, got %s)" % (length, len(data))
    if data[-3] != ETX:
        return None, "Missing ETX"
    xor = 0
    for b in data[: length - 2]:
        xor ^= b
    expected_checksum = f"{xor:02x}".encode("ascii")
    actual_checksum = data[-2:]
    if actual_checksum.lower() != expected_checksum:
        # Tolerate a leading space in the checksum: some firmware versions
        # emit a space instead of the high hex nibble.
        if actual_checksum[0:1] == b" " and actual_checksum[1:2].lower() == expected_checksum[1:2]:
            pass
        else:
            return None, "Checksum mismatch (expected %s, got %s)" % (
                expected_checksum,
                actual_checksum,
            )
    try:
        message = data[sep_index:-3].decode("ascii")
    except UnicodeDecodeError:
        return None, "Invalid ASCII encoding"
    fields = message.split("|")[1:]
    return fields, None


class CT002:
    def __init__(
        self,
        udp_port=UDP_PORT,
        device_type="HMG-50",
        ct_mac="",
        ct_type="HME-4",
        wifi_rssi=-50,
        info_idx=0,
        dedupe_time_window=10,
        consumer_ttl=120,
        allow_any_ct_mac=True,
        override_path=None,
    ):
        self.udp_port = udp_port
        self.device_type = device_type
        self.ct_mac = ct_mac
        self.ct_type = ct_type
        self.wifi_rssi = wifi_rssi
        self.info_idx = info_idx
        self._phase_assignments = {}
        self.dedupe_time_window = dedupe_time_window
        self.consumer_ttl = consumer_ttl
        self.allow_any_ct_mac = allow_any_ct_mac
        self.before_send = None
        self.override_path = override_path
        self._stop = False
        self._udp_thread = None
        self._values_by_consumer = {}
        self._reports_by_consumer = {}
        self._values_lock = threading.Lock()
        self._last_response_time = {}

    def _consumer_key(self, addr, fields):
        battery_mac = fields[1] if len(fields) > 1 else ""
        if battery_mac:
            return battery_mac.lower()
        return "%s:%s" % (addr[0], addr[1])

    def set_consumer_value(self, consumer_id, values):
        with self._values_lock:
            self._values_by_consumer[consumer_id] = values

    def _get_consumer_value(self, consumer_id):
        with self._values_lock:
            return self._values_by_consumer.get(consumer_id)

    def _update_consumer_report(self, consumer_id, phase=None, power=None, charge_power=None, discharge_power=None):
        """
        Store latest per-consumer report.

        Current protocol understanding (from captures): request fields are
        ...|<phase>|<power> where phase is A/B/C and power is signed watts.

        Legacy compatibility: if callers still pass charge/discharge, keep
        approximate behavior by converting to a signed net power.
        """
        if power is None and (charge_power is not None or discharge_power is not None):
            c = parse_int(charge_power, 0)
            d = parse_int(discharge_power, 0)
            power = d - c
        if phase is None:
            phase = "A"

        with self._values_lock:
            self._reports_by_consumer[consumer_id] = {
                "phase": str(phase).upper() if phase else "A",
                "power": parse_int(power, 0),
                "timestamp": time.time(),
            }

    def _cleanup_consumers(self):
        now = time.time()
        with self._values_lock:
            stale = [
                key
                for key, report in self._reports_by_consumer.items()
                if now - report.get("timestamp", 0) > self.consumer_ttl
            ]
            for key in stale:
                self._reports_by_consumer.pop(key, None)
                self._values_by_consumer.pop(key, None)
                self._phase_assignments.pop(key, None)
        stale_addrs = [
            addr
            for addr, ts in self._last_response_time.items()
            if now - ts > self.dedupe_time_window
        ]
        for addr in stale_addrs:
            self._last_response_time.pop(addr, None)

    def _assign_phase(self, consumer_id):
        if consumer_id in self._phase_assignments:
            return self._phase_assignments[consumer_id]
        phases = ["A", "B", "C"]
        assigned = set(self._phase_assignments.values())
        for phase in phases:
            if phase not in assigned:
                self._phase_assignments[consumer_id] = phase
                logger.debug("CT002 phase auto-assign: %s -> %s", consumer_id, phase)
                return phase
        # fallback round-robin
        phase = phases[len(self._phase_assignments) % len(phases)]
        self._phase_assignments[consumer_id] = phase
        logger.debug("CT002 phase auto-assign (rr): %s -> %s", consumer_id, phase)
        return phase

    def _phase_index(self, phase):
        mapping = {"A": 0, "B": 1, "C": 2}
        return mapping.get(phase, 0)

    def _collect_other_reports_by_phase(self, consumer_id):
        by_phase = {
            "A": {"power": 0},
            "B": {"power": 0},
            "C": {"power": 0},
        }
        with self._values_lock:
            reports = list(self._reports_by_consumer.items())

        for other_id, report in reports:
            if other_id == consumer_id:
                continue
            phase = (report.get("phase") or self._assign_phase(other_id) or "A").upper()
            if phase not in by_phase:
                phase = "A"
            by_phase[phase]["power"] += parse_int(report.get("power", 0))
        return by_phase

    def _load_override(self):
        if not self.override_path:
            return None
        try:
            with open(self.override_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return data
        except Exception as exc:
            logger.debug("CT002 override load failed: %s", exc)
        return None

    def _build_response_fields(self, request_fields, values, consumer_id=None):
        if not values or len(values) != 3:
            values = [0, 0, 0]
        phase_a, phase_b, phase_c = values
        measured_total_power = phase_a + phase_b + phase_c
        meter_dev_type = request_fields[0] if len(request_fields) > 0 else self.device_type
        meter_mac = request_fields[1] if len(request_fields) > 1 else ""
        ct_type = self.ct_type
        ct_mac = self.ct_mac if self.ct_mac else (request_fields[3] if len(request_fields) > 3 else "")
        response_fields = [
            ct_type,
            ct_mac,
            meter_dev_type,
            meter_mac,
            str(round(phase_a)),
            str(round(phase_b)),
            str(round(phase_c)),
            str(round(measured_total_power)),
            "0", "0", "0", "0",  # A/B/C/ABC_chrg_nb
            str(self.wifi_rssi),
            str(self.info_idx),
            "0", "0", "0", "0", "0",  # x/A/B/C/ABC_chrg_power
            "0", "0", "0", "0", "0",  # x/A/B/C/ABC_dchrg_power
        ]

        phase_values = self._collect_other_reports_by_phase(consumer_id)
        for phase, idx in (("A", 0), ("B", 1), ("C", 2)):
            power = phase_values[phase]["power"]
            if power != 0:
                response_fields[8 + idx] = "1"
                # Observed packets carry signed per-phase values in the
                # *_chrg_power section; keep *_dchrg_power at 0 for now.
                response_fields[15 + idx] = str(power)

        response_fields += ["0"] * (len(RESPONSE_LABELS) - len(response_fields))
        override = self._load_override()
        if override:
            for idx, label in enumerate(RESPONSE_LABELS[4:], start=4):
                if label in override:
                    response_fields[idx] = str(override[label])
        return response_fields

    def _call_before_send(self, addr, fields, consumer_id):
        if not self.before_send:
            return None
        try:
            params = inspect.signature(self.before_send).parameters
            if len(params) >= 3:
                return self.before_send(addr, fields, consumer_id)
            return self.before_send(addr)
        except Exception as exc:
            logger.warning("before_send failed for %s: %s", addr, exc)
            return None

    def _validate_ct_mac(self, request_fields):
        if self.allow_any_ct_mac and not self.ct_mac:
            return True
        if len(request_fields) < 4:
            return False
        req_ct_mac = request_fields[3]
        if not req_ct_mac:
            return False
        if self.ct_mac:
            if req_ct_mac.lower() == self.ct_mac.lower():
                return True
            if self.allow_any_ct_mac and req_ct_mac == "000000000000":
                return True
            return False
        return self.allow_any_ct_mac

    def _handle_request(self, data, addr):
        logger.debug("CT002 request from %s: %s", addr, data.hex())
        fields, error = parse_request(data)
        if error:
            logger.debug("Invalid CT002 request from %s: %s", addr, error)
            return None
        if len(fields) < 4:
            logger.debug("CT002 request from %s missing required fields", addr)
            return None
        if not self._validate_ct_mac(fields):
            logger.debug(
                "Ignoring CT002 request from %s due to CT MAC mismatch (req=%s, cfg=%s, allow_any=%s)",
                addr,
                fields[3] if len(fields) > 3 else None,
                self.ct_mac,
                self.allow_any_ct_mac,
            )
            return None
        consumer_id = self._consumer_key(addr, fields)
        reported_phase = fields[4] if len(fields) > 4 else "A"
        reported_power = parse_int(fields[5] if len(fields) > 5 else 0)

        # Backward-compatible fallback for older synthetic payloads that used
        # numeric charge/discharge at positions 5/6.
        if reported_phase not in ("A", "B", "C"):
            legacy_charge = parse_int(fields[4] if len(fields) > 4 else 0)
            legacy_discharge = parse_int(fields[5] if len(fields) > 5 else 0)
            reported_phase = "A"
            reported_power = legacy_discharge - legacy_charge

        logger.debug(
            "CT002 parsed fields from %s: meter_dev_type=%s meter_mac=%s ct_type=%s ct_mac=%s phase=%s power=%s consumer_id=%s",
            addr,
            fields[0] if len(fields) > 0 else None,
            fields[1] if len(fields) > 1 else None,
            fields[2] if len(fields) > 2 else None,
            fields[3] if len(fields) > 3 else None,
            reported_phase,
            reported_power,
            consumer_id,
        )
        self._update_consumer_report(consumer_id, phase=reported_phase, power=reported_power)

        updated = self._call_before_send(addr, fields, consumer_id)
        if updated is not None:
            self.set_consumer_value(consumer_id, updated)

        values = self._get_consumer_value(consumer_id)
        if values is None:
            values = [0, 0, 0]
        try:
            response_fields = self._build_response_fields(fields, values, consumer_id)
            response = build_payload(response_fields)
        except Exception as exc:
            logger.warning("Failed to build CT002 response for %s (%s): %s", addr, fields, exc)
            return None
        logger.debug(
            "CT002 response to %s: %s (fields=%s)",
            addr,
            response.hex(),
            response_fields
        )
        return response

    def udp_server(self):
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp_sock.bind(("", self.udp_port))
        udp_sock.settimeout(1.0)
        logger.info("CT002 UDP server listening on port %s", self.udp_port)
        try:
            while not self._stop:
                self._cleanup_consumers()
                try:
                    data, addr = udp_sock.recvfrom(1024)
                except socket.timeout:
                    continue
                current_time = time.time()
                last_time = self._last_response_time.get(addr)
                if last_time and (current_time - last_time) < self.dedupe_time_window:
                    logger.debug("Ignoring request from %s due to dedupe window", addr)
                    continue
                response = self._handle_request(data, addr)
                if response:
                    udp_sock.sendto(response, addr)
                    self._last_response_time[addr] = current_time
        finally:
            udp_sock.close()

    def start(self):
        if self._udp_thread and self._udp_thread.is_alive():
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
