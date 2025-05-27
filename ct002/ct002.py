import socket
import threading
import time
import re

SOH = 0x01
STX = 0x02
ETX = 0x03
SEPARATOR = '|'
UDP_PORT = 12345

# Field labels for response (from reference)
RESPONSE_LABELS = [
    "meter_dev_type", "meter_mac_code", "hhm_dev_type", "hhm_mac_code",
    "A_phase_power", "B_phase_power", "C_phase_power", "total_power",
    "A_chrg_nb", "B_chrg_nb", "C_chrg_nb", "ABC_chrg_nb", "wifi_rssi", "info_idx",
    "x_chrg_power", "A_chrg_power", "B_chrg_power", "C_chrg_power", "ABC_chrg_power",
    "x_dchrg_power", "A_dchrg_power", "B_dchrg_power", "C_dchrg_power", "ABC_dchrg_power"
]

class CTEmulator:
    def __init__(self, device_type="HMG-50", battery_mac="001122334455", ct_mac="009c17abcdef", ct_type="HME-4", poll_interval=1, discovery_battery_macs=None, dedupe_time_window=10):
        self.device_type = device_type
        self.battery_mac = battery_mac
        self.ct_mac = ct_mac
        self.ct_type = ct_type
        self.poll_interval = poll_interval
        self._udp_thread = None
        self._stop = False
        self._value = [0, 0, 0]
        self._value_mutex = threading.Lock()
        if discovery_battery_macs is None:
            self.discovery_battery_macs = ["001122334455"]
        else:
            self.discovery_battery_macs = discovery_battery_macs
        self.dedupe_time_window = dedupe_time_window
        self._last_response_time = {}
        self.before_send = None

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        with self._value_mutex:
            self._value = value

    def validate_mac(self, mac):
        return re.fullmatch(r"[0-9a-fA-F]{12}", mac) is not None

    def calculate_checksum(self, data_bytes):
        xor = 0
        for b in data_bytes:
            xor ^= b
        return xor

    def parse_ct002_request(self, data):
        # Validate SOH, STX, ETX, length, checksum
        if len(data) < 10:
            return None, "Too short"
        if data[0] != SOH or data[1] != STX:
            return None, "Missing SOH/STX"
        sep_index = data.find(b'|', 2)
        if sep_index == -1:
            return None, "No separator after length"
        try:
            length = int(data[2:sep_index].decode('ascii'))
        except ValueError:
            return None, "Invalid length field"
        if len(data) != length:
            return None, f"Length mismatch (expected {length}, got {len(data)})"
        if data[-3] != ETX:
            return None, "Missing ETX"
        # Checksum
        xor = 0
        for b in data[:length-2]:
            xor ^= b
        expected_checksum = f"{xor:02x}".encode('ascii')
        actual_checksum = data[-2:]
        # Accept both '03' and ' 3' as valid for 0x03
        if actual_checksum.lower() != expected_checksum:
            if actual_checksum[0:1] == b' ' and actual_checksum[1:2] == expected_checksum[1:2]:
                pass  # Accept space-padded single digit
            else:
                return None, f"Checksum mismatch (expected {expected_checksum}, got {actual_checksum})"
        # Parse fields
        try:
            message = data[4:-3].decode('ascii')
        except UnicodeDecodeError:
            return None, "Invalid ASCII encoding"
        fields = message.split('|')[1:]  # first char is '|'
        return fields, None

    def build_ct002_response(self, request_fields):
        values = self.value if self.value else [0, 0, 0]
        # meter_dev_type and meter_mac_code from request, hhm_dev_type and hhm_mac_code from emulator config
        response_fields = [
            request_fields[0],  # meter_dev_type (from request)
            request_fields[1],  # meter_mac_code (from request)
            self.ct_type,       # hhm_dev_type (from emulator)
            self.ct_mac,        # hhm_mac_code (from emulator)
            str(values[0]),     # A_phase_power
            str(values[1]),     # B_phase_power
            str(values[2]),     # C_phase_power
            str(sum(values)),   # total_power
        ] + ["0"] * (len(RESPONSE_LABELS) - 8)
        message_str = SEPARATOR + SEPARATOR.join(response_fields)
        message_bytes = message_str.encode('ascii')
        base_size = 1 + 1 + len(message_bytes) + 1 + 2
        for length_digits in range(1, 5):
            total_length = base_size + length_digits
            if len(str(total_length)) == length_digits:
                break
        length_str = str(total_length).encode('ascii')
        payload = bytearray([SOH, STX]) + length_str + message_bytes + bytearray([ETX])
        checksum = f"{self.calculate_checksum(payload):02x}".encode('ascii')
        payload += checksum
        return payload

    def format_ct_response_readable(self, data):
        # Show control characters as labels, printable ASCII as-is
        def safe_char(byte):
            if byte == SOH:
                return '<SOH>'
            elif byte == STX:
                return '<STX>'
            elif byte == ETX:
                return '<ETX>'
            elif 32 <= byte <= 126:
                return chr(byte)
            else:
                return f'<0x{byte:02X}>'
        return ''.join(safe_char(b) for b in data)

    def udp_server(self):
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_sock.bind(("", UDP_PORT))
        print(f"CTEmulator UDP server is listening on port {UDP_PORT}...")
        try:
            while not self._stop:
                udp_sock.settimeout(1.0)
                try:
                    data, addr = udp_sock.recvfrom(1024)
                except socket.timeout:
                    continue
                # Try CT001 (plain ASCII 'hame')
                try:
                    decoded = data.decode()
                    if decoded == "hame":
                        current_time = time.time()
                        if (
                            addr not in self._last_response_time
                            or (current_time - self._last_response_time[addr]) > self.dedupe_time_window
                        ):
                            print(f"Received 'hame' from {addr}")
                            udp_sock.sendto(b"ack", addr)
                            self._last_response_time[addr] = current_time
                            print(f"Sent 'ack' to {addr}")
                        else:
                            print(f"Received 'hame' from {addr} but ignored due to dedupe window")
                        continue
                except UnicodeDecodeError:
                    pass  # Not a plain ASCII message
                # Try CT002 protocol
                fields, error = self.parse_ct002_request(data)
                if error:
                    print(f"Invalid CT002 request from {addr}: {error}")
                    continue
                # Discovery logic: only respond if CT MAC matches and battery MAC is valid
                if len(fields) < 4:
                    print(f"CT002 request from {addr} does not have enough fields for discovery check")
                    continue
                req_battery_mac = fields[1]
                req_ct_mac = fields[3]
                if req_ct_mac.lower() != self.ct_mac.lower() and req_ct_mac != "000000000000":
                    print(f"Ignoring CT002 request from {addr}: CT MAC mismatch (got {req_ct_mac}, expected {self.ct_mac} or 000000000000)")
                    continue
                # Accept any battery MAC
                # if req_battery_mac not in self.discovery_battery_macs and req_battery_mac != self.battery_mac:
                #     print(f"Ignoring CT002 request from {addr}: Battery MAC {req_battery_mac} not in discovery list or not our battery MAC")
                #     continue
                print(f"Valid CT002 discovery/query request from {addr}: {fields}")
                if self.before_send:
                    self.before_send(addr)
                response = self.build_ct002_response(fields)
                print(f"CT002 response to {addr}: {response.hex()} | {self.format_ct_response_readable(response)}")
                udp_sock.sendto(response, addr)
                print(f"Sent CT002 response to {addr}")
        finally:
            udp_sock.close()

    def handle_tcp_client(self, conn, addr):
        print(f"TCP connection established with {addr}")
        try:
            data = conn.recv(1024)
            decoded = data.decode()
            if decoded == "hello":
                print("Received 'hello'")
                last_send_time = 0
                while not self._stop:
                    current_time = time.time()
                    time_since_last_send = current_time - last_send_time
                    if time_since_last_send >= self.poll_interval:
                        if self.before_send:
                            self.before_send(addr)
                        with self._value_mutex:
                            if self.value is None:
                                print(f"No value to send to {addr}")
                                break
                            value1, value2, value3 = self.value
                        value1 = round(value1)
                        value2 = round(value2)
                        value3 = round(value3)
                        message = f"HM:{value1}|{value2}|{value3}"
                        try:
                            conn.send(message.encode())
                            last_send_time = current_time
                            print(f"Sent message to {addr}: {message}")
                        except BrokenPipeError:
                            print(f"Connection with {addr} broken. Waiting for a new connection.")
                            break
                        time.sleep(self.poll_interval)
                    else:
                        time.sleep(0.01)
            else:
                print(f"Received unknown TCP message: {decoded}")
        finally:
            conn.close()
            print(f"Connection with {addr} closed")

    def tcp_server(self):
        tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_sock.bind(("", UDP_PORT))
        tcp_sock.listen(5)
        print("CTEmulator TCP server is listening...")
        try:
            while not self._stop:
                conn, addr = tcp_sock.accept()
                client_thread = threading.Thread(
                    target=self.handle_tcp_client, args=(conn, addr)
                )
                client_thread.start()
        finally:
            print("Stop listening for TCP connections")
            tcp_sock.close()

    def start(self):
        if self._udp_thread or hasattr(self, '_tcp_thread') and self._tcp_thread:
            return
        self._stop = False
        self._udp_thread = threading.Thread(target=self.udp_server)
        self._tcp_thread = threading.Thread(target=self.tcp_server)
        self._udp_thread.start()
        self._tcp_thread.start()

    def join(self):
        if self._udp_thread:
            self._udp_thread.join()
        if hasattr(self, '_tcp_thread') and self._tcp_thread:
            self._tcp_thread.join()

    def stop(self):
        self._stop = True
        if self._udp_thread:
            self._udp_thread.join()
        if hasattr(self, '_tcp_thread') and self._tcp_thread:
            self._tcp_thread.join()
        self._udp_thread = None
        if hasattr(self, '_tcp_thread'):
            self._tcp_thread = None 