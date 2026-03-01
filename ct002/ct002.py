import socket
import threading
import time
import inspect
from typing import Optional
from config.logger import logger

SOH = 0x01
STX = 0x02
ETX = 0x03
SEPARATOR = "|"
UDP_PORT = 12345
CLEANUP_INTERVAL_SECONDS = 5

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
        if (
            actual_checksum[0:1] == b" "
            and actual_checksum[1:2].lower() == expected_checksum[1:2]
        ):
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
        ct_mac="",
        ct_type="HME-4",
        wifi_rssi=-50,
        dedupe_time_window=0,
        consumer_ttl=120,
        debug_status=False,
        active_control=True,
        smooth_target_alpha=0.3,
        fair_distribution=True,
        balance_gain=0.3,
    ):
        self.udp_port = udp_port
        self.ct_mac = ct_mac
        self.ct_type = ct_type
        self.wifi_rssi = wifi_rssi
        self.dedupe_time_window = dedupe_time_window
        self.consumer_ttl = consumer_ttl
        self.debug_status = debug_status
        self.active_control = active_control
        self.smooth_target_alpha = max(0.01, min(1.0, smooth_target_alpha))
        self.fair_distribution = fair_distribution
        self.balance_gain = max(0.0, min(1.0, balance_gain))
        self.before_send = None
        self._info_idx_counter = 0
        self._stop = False
        self._udp_thread = None
        self._values_by_consumer = {}
        self._reports_by_consumer = {}
        self._values_lock = threading.Lock()
        self._last_response_time = {}
        self._smoothed_target = None

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

    def _update_consumer_report(self, consumer_id, phase, power):
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
        stale_addrs = [
            addr
            for addr, ts in self._last_response_time.items()
            if now - ts > self.dedupe_time_window
        ]
        for addr in stale_addrs:
            self._last_response_time.pop(addr, None)

    def _compute_smooth_target(self, values, consumer_id=None):
        """
        Active control: smooth the raw grid reading and split target across consumers.
        With fair_distribution: adjust each consumer's target to balance actual load.
        Returns [target, 0, 0] for single-phase (all in phase A).
        """
        if not values or len(values) != 3:
            return values
        raw_total = sum(parse_int(v, 0) for v in values)
        alpha = self.smooth_target_alpha
        if self._smoothed_target is None:
            self._smoothed_target = raw_total
        else:
            self._smoothed_target = (
                alpha * raw_total + (1 - alpha) * self._smoothed_target
            )
        with self._values_lock:
            reports = dict(self._reports_by_consumer)
            num_consumers = max(1, len(reports))
        fair_share = self._smoothed_target / num_consumers
        if (
            not self.fair_distribution
            or consumer_id is None
            or consumer_id not in reports
        ):
            return [fair_share, 0, 0]
        actual_self = parse_int(reports.get(consumer_id, {}).get("power", 0))
        actual_total = sum(parse_int(r.get("power", 0)) for r in reports.values())
        actual_avg = actual_total / num_consumers if num_consumers else 0
        error = actual_avg - actual_self
        target = fair_share + self.balance_gain * error
        return [target, 0, 0]

    def _collect_reports_by_phase(self):
        by_phase = {
            "A": {"chrg_power": 0, "dchrg_power": 0, "active": False},
            "B": {"chrg_power": 0, "dchrg_power": 0, "active": False},
            "C": {"chrg_power": 0, "dchrg_power": 0, "active": False},
        }
        with self._values_lock:
            reports = list(self._reports_by_consumer.items())

        for _consumer_id, report in reports:
            phase = (report.get("phase") or "A").upper()
            if phase not in by_phase:
                phase = "A"
            power = parse_int(report.get("power", 0))
            if power == 0:
                continue
            by_phase[phase]["active"] = True
            if power < 0:
                by_phase[phase]["chrg_power"] += power
            else:
                by_phase[phase]["dchrg_power"] += power
        return by_phase

    def _format_status(self, values, phase_values):
        """Concise one-line status: phase consumption and consumer charge/discharge reports."""
        if not values or len(values) != 3:
            values = [0, 0, 0]
        phases = " ".join(f"{p}:{int(v)}W" for p, v in zip("ABC", values))
        chrg = " ".join(f"{p}:{phase_values[p]['chrg_power']}" for p in "ABC")
        dchrg = " ".join(f"{p}:{phase_values[p]['dchrg_power']}" for p in "ABC")
        with self._values_lock:
            reports = list(self._reports_by_consumer.items())
        consumers = (
            " ".join(
                f"{cid[:8]}@{r.get('phase','?')}:{r.get('power',0)}"
                for cid, r in sorted(reports, key=lambda x: x[0])
            )
            or "none"
        )
        return f"phases {phases} | chrg {chrg} | dchrg {dchrg} | consumers {consumers}"

    def _build_response_fields(self, request_fields, values):
        if not values or len(values) != 3:
            values = [0, 0, 0]
        phase_a, phase_b, phase_c = values
        measured_total_power = phase_a + phase_b + phase_c
        meter_dev_type = request_fields[0] if len(request_fields) > 0 else "HMG-50"
        meter_mac = request_fields[1] if len(request_fields) > 1 else ""
        ct_type = self.ct_type
        ct_mac = (
            self.ct_mac
            if self.ct_mac
            else (request_fields[3] if len(request_fields) > 3 else "")
        )
        response_fields = [
            ct_type,
            ct_mac,
            meter_dev_type,
            meter_mac,
            str(round(phase_a)),
            str(round(phase_b)),
            str(round(phase_c)),
            str(round(measured_total_power)),
            "0",
            "0",
            "0",
            "0",  # A/B/C/ABC_chrg_nb
            str(self.wifi_rssi),
            str(self._info_idx_counter),
            "0",
            "0",
            "0",
            "0",
            "0",  # x/A/B/C/ABC_chrg_power
            "0",
            "0",
            "0",
            "0",
            "0",  # x/A/B/C/ABC_dchrg_power
        ]

        # Forward A/B/C values across all known consumers, but split per-storage
        # by sign before aggregation:
        # negative reports contribute to *_chrg_power,
        # positive reports contribute to *_dchrg_power.
        phase_values = self._collect_reports_by_phase()
        for phase, idx in (("A", 0), ("B", 1), ("C", 2)):
            if phase_values[phase]["active"]:
                response_fields[8 + idx] = "1"
            response_fields[15 + idx] = str(phase_values[phase]["chrg_power"])
            response_fields[20 + idx] = str(phase_values[phase]["dchrg_power"])

        response_fields += ["0"] * (len(RESPONSE_LABELS) - len(response_fields))
        self._info_idx_counter = (self._info_idx_counter + 1) % 256
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
        # If CT_MAC is not configured, accept all request CT MACs.
        if not self.ct_mac:
            return True
        if len(request_fields) < 4:
            return False
        req_ct_mac = request_fields[3]
        if not req_ct_mac:
            return False
        return req_ct_mac.lower() == self.ct_mac.lower()

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
                "Ignoring CT002 request from %s due to CT MAC mismatch (req=%s, cfg=%s)",
                addr,
                fields[3] if len(fields) > 3 else None,
                self.ct_mac,
            )
            return None
        consumer_id = self._consumer_key(addr, fields)
        reported_phase = (fields[4] if len(fields) > 4 else "").strip().upper()
        reported_power = parse_int(fields[5] if len(fields) > 5 else 0)

        if reported_phase not in ("A", "B", "C", "0", ""):
            logger.debug(
                "CT002 request from %s has invalid phase '%s'", addr, reported_phase
            )
            return None

        in_inspection_mode = reported_phase in ("0", "")

        logger.debug(
            "CT002 parsed fields from %s: meter_dev_type=%s meter_mac=%s ct_type=%s ct_mac=%s phase=%s power=%s consumer_id=%s%s",
            addr,
            fields[0] if len(fields) > 0 else None,
            fields[1] if len(fields) > 1 else None,
            fields[2] if len(fields) > 2 else None,
            fields[3] if len(fields) > 3 else None,
            reported_phase or "(inspection)",
            reported_power,
            consumer_id,
            " in inspection mode" if in_inspection_mode else "",
        )
        if not in_inspection_mode:
            self._update_consumer_report(
                consumer_id, phase=reported_phase, power=reported_power
            )

        updated = self._call_before_send(addr, fields, consumer_id)
        if updated is not None:
            self.set_consumer_value(consumer_id, updated)

        values = self._get_consumer_value(consumer_id)
        if values is None:
            values = [0, 0, 0]
        if self.active_control:
            values = self._compute_smooth_target(values, consumer_id)
        try:
            response_fields = self._build_response_fields(fields, values)
            response = build_payload(response_fields)
        except Exception as exc:
            logger.warning(
                "Failed to build CT002 response for %s (%s): %s", addr, fields, exc
            )
            return None
        logger.debug(
            "CT002 response to %s: %s (fields=%s)",
            addr,
            response.hex(),
            response_fields,
        )
        if self.debug_status:
            phase_values = self._collect_reports_by_phase()
            logger.info("CT002 status: %s", self._format_status(values, phase_values))
        return response

    def udp_server(self):
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp_sock.bind(("", self.udp_port))
        udp_sock.settimeout(1.0)
        logger.info("CT002 UDP server listening on port %s", self.udp_port)
        last_cleanup = time.time()
        try:
            while not self._stop:
                now = time.time()
                if now - last_cleanup >= CLEANUP_INTERVAL_SECONDS:
                    self._cleanup_consumers()
                    last_cleanup = now
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
                    for attempt in range(3):
                        try:
                            udp_sock.sendto(response, addr)
                            self._last_response_time[addr] = current_time
                            break
                        except OSError as e:
                            if attempt < 2:
                                time.sleep(0.05 * (attempt + 1))
                            else:
                                logger.info(
                                    "Could not send response to %s after %d attempts: %s",
                                    addr,
                                    attempt + 1,
                                    e,
                                )
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
