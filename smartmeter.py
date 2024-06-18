import socket
import threading
import time
import configparser
from requests.sessions import Session
from requests.auth import HTTPDigestAuth
import subprocess
import json
import paho.mqtt.client as mqtt

# Define ports
UDP_PORT = 12345
TCP_PORT = 12345

# Initialize session for HTTP requests
session = Session()


# Powermeter classes
class Powermeter:
    def get_powermeter_watts(self) -> tuple[int, ...]:
        raise NotImplementedError()


class Tasmota(Powermeter):
    def __init__(
        self,
        ip: str,
        user: str,
        password: str,
        json_status: str,
        json_payload_mqtt_prefix: str,
        json_power_mqtt_label: str,
        json_power_input_mqtt_label: str,
        json_power_output_mqtt_label: str,
        json_power_calculate: bool,
    ):
        self.ip = ip
        self.user = user
        self.password = password
        self.json_status = json_status
        self.json_payload_mqtt_prefix = json_payload_mqtt_prefix
        self.json_power_mqtt_label = json_power_mqtt_label
        self.json_power_input_mqtt_label = json_power_input_mqtt_label
        self.json_power_output_mqtt_label = json_power_output_mqtt_label
        self.json_power_calculate = json_power_calculate

    def get_json(self, path):
        url = f"http://{self.ip}{path}"
        return session.get(url, timeout=10).json()

    def get_powermeter_watts(self):
        if not self.user:
            response = self.get_json("/cm?cmnd=status%2010")
        else:
            response = self.get_json(
                f"/cm"
                f"?user={self.user}"
                f"&password={self.password}"
                f"&cmnd=status%2010"
            )
        value = response[self.json_status][self.json_payload_mqtt_prefix]
        if not self.json_power_calculate:
            return [int(value[self.json_power_mqtt_label])]
        else:
            power_in = value[self.json_power_input_mqtt_label]
            power_out = value[self.json_power_output_mqtt_label]
            return [int(power_in) - int(power_out)]


class Shelly(Powermeter):
    def __init__(self, ip: str, user: str, password: str, emeterindex: str):
        self.ip = ip
        self.user = user
        self.password = password
        self.emeterindex = emeterindex

    def get_json(self, path):
        url = f"http://{self.ip}{path}"
        headers = {"content-type": "application/json"}
        return session.get(
            url, headers=headers, auth=(self.user, self.password), timeout=10
        ).json()

    def get_rpc_json(self, path):
        url = f"http://{self.ip}/rpc{path}"
        headers = {"content-type": "application/json"}
        return session.get(
            url,
            headers=headers,
            auth=HTTPDigestAuth(self.user, self.password),
            timeout=10,
        ).json()

    def get_powermeter_watts(self) -> tuple[int, ...]:
        raise NotImplementedError()


class Shelly1PM(Shelly):
    def get_powermeter_watts(self):
        status = self.get_json("/status")
        if self.emeterindex:
            return [int(self.get_json(f"/meter/{self.emeterindex}")["power"])]
        else:
            return [int(meter["power"]) for meter in status["meters"]]


class ShellyPlus1PM(Shelly):
    def get_powermeter_watts(self):
        return [int(self.get_rpc_json("/Switch.GetStatus?id=0")["apower"])]


class ShellyEM(Shelly):
    def get_powermeter_watts(self):
        if self.emeterindex:
            return [int(self.get_json(f"/emeter/{self.emeterindex}")["power"])]
        else:
            status = self.get_json("/status")
            return [int(emeter["power"]) for emeter in status["emeters"]]


class Shelly3EM(Shelly):

    def get_powermeter_watts(self):
        status = self.get_json("/status")
        # Return an array of all power values
        return [int(emeter["power"]) for emeter in status["emeters"]]


class Shelly3EMPro(Shelly):
    def get_powermeter_watts(self):
        response = self.get_rpc_json("/EM.GetStatus?id=0")
        return [int(response["total_act_power"])]


class ESPHome(Powermeter):
    def __init__(self, ip: str, port: str, domain: str, id: str):
        self.ip = ip
        self.port = port
        self.domain = domain
        self.id = id

    def get_json(self, path):
        url = f"http://{self.ip}:{self.port}{path}"
        return session.get(url, timeout=10).json()

    def get_powermeter_watts(self):
        ParsedData = self.get_json(f"/{self.domain}/{self.id}")
        return [int(ParsedData["value"])]


class Shrdzm(Powermeter):
    def __init__(self, ip: str, user: str, password: str):
        self.ip = ip
        self.user = user
        self.password = password

    def get_json(self, path):
        url = f"http://{self.ip}{path}"
        return session.get(url, timeout=10).json()

    def get_powermeter_watts(self):
        response = self.get_json(
            f"/getLastData?user={self.user}&password={self.password}"
        )
        return [int(int(response["1.7.0"]) - int(response["2.7.0"]))]


class Emlog(Powermeter):
    def __init__(self, ip: str, meterindex: str, json_power_calculate: bool):
        self.ip = ip
        self.meterindex = meterindex
        self.json_power_calculate = json_power_calculate

    def get_json(self, path):
        url = f"http://{self.ip}{path}"
        return session.get(url, timeout=10).json()

    def get_powermeter_watts(self):
        response = self.get_json(
            f"/pages/getinformation.php?heute&meterindex={self.meterindex}"
        )
        if not self.json_power_calculate:
            return [int(response["Leistung170"])]
        else:
            power_in = response["Leistung170"]
            power_out = response["Leistung270"]
            return [int(power_in) - int(power_out)]


class IoBroker(Powermeter):
    def __init__(
        self,
        ip: str,
        port: str,
        current_power_alias: str,
        power_calculate: bool,
        power_input_alias: str,
        power_output_alias: str,
    ):
        self.ip = ip
        self.port = port
        self.current_power_alias = current_power_alias
        self.power_calculate = power_calculate
        self.power_input_alias = power_input_alias
        self.power_output_alias = power_output_alias

    def get_json(self, path):
        url = f"http://{self.ip}:{self.port}{path}"
        return session.get(url, timeout=10).json()

    def get_powermeter_watts(self):
        if not self.power_calculate:
            response = self.get_json(f"/getBulk/{self.current_power_alias}")
            for item in response:
                if item["id"] == self.current_power_alias:
                    return [int(item["val"])]
        else:
            response = self.get_json(
                f"/getBulk/{self.power_input_alias},{self.power_output_alias}"
            )
            power_in = 0
            power_out = 0
            for item in response:
                if item["id"] == self.power_input_alias:
                    power_in = int(item["val"])
                if item["id"] == self.power_output_alias:
                    power_out = int(item["val"])
            return [power_in - power_out]


class HomeAssistant(Powermeter):
    def __init__(
        self,
        ip: str,
        port: str,
        use_https: bool,
        access_token: str,
        current_power_entity: str,
        power_calculate: bool,
        power_input_alias: str,
        power_output_alias: str,
    ):
        self.ip = ip
        self.port = port
        self.use_https = use_https
        self.access_token = access_token
        self.current_power_entity = current_power_entity
        self.power_calculate = power_calculate
        self.power_input_alias = power_input_alias
        self.power_output_alias = power_output_alias

    def get_json(self, path):
        if self.use_https:
            url = f"https://{self.ip}:{self.port}{path}"
        else:
            url = f"http://{self.ip}:{self.port}{path}"
        headers = {
            "Authorization": "Bearer " + self.access_token,
            "content-type": "application/json",
        }
        return session.get(url, headers=headers, timeout=10).json()

    def get_powermeter_watts(self):
        if not self.power_calculate:
            path = f"/api/states/{self.current_power_entity}"
            response = self.get_json(path)
            return [int(response["state"])]
        else:
            response = self.get_json(f"/api/states/{self.power_input_alias}")
            power_in = int(response["state"])
            response = self.get_json(f"/api/states/{self.power_output_alias}")
            power_out = int(response["state"])
            return [power_in - power_out]


class VZLogger(Powermeter):
    def __init__(self, ip: str, port: str, uuid: str):
        self.ip = ip
        self.port = port
        self.uuid = uuid

    def get_json(self):
        url = f"http://{self.ip}:{self.port}/{self.uuid}"
        return session.get(url, timeout=10).json()

    def get_powermeter_watts(self):
        return [int(self.get_json()["data"][0]["tuples"][0][1])]


class AmisReader(Powermeter):
    def __init__(self, ip: str):
        self.ip = ip

    def get_json(self, path):
        url = f"http://{self.ip}{path}"
        return session.get(url, timeout=10).json()

    def get_powermeter_watts(self):
        response = self.get_json("/rest")
        return [int(response["saldo"])]


def extract_json_value(data, path):
    keys = path.split(".")
    for key in keys:
        data = data[key]
    return int(float(data))


class MqttPowermeter(Powermeter):
    def __init__(
        self,
        broker: str,
        port: int,
        topic: str,
        json_path: str = None,
        username: str = None,
        password: str = None,
    ):
        self.broker = broker
        self.port = port
        self.topic = topic
        self.json_path = json_path
        self.username = username
        self.password = password
        self.value = None

        # Initialize MQTT client
        self.client = mqtt.Client()
        if self.username and self.password:
            self.client.username_pw_set(self.username, self.password)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        # Connect to the broker
        self.client.connect(self.broker, self.port, 60)
        self.client.loop_start()

    def on_connect(self, client, userdata, flags, rc):
        print(f"Connected with result code {rc}")
        # Subscribe to the topic
        client.subscribe(self.topic)

    def on_message(self, client, userdata, msg):
        payload = msg.payload.decode()
        if self.json_path:
            try:
                data = json.loads(payload)
                self.value = extract_json_value(data, self.json_path)
            except json.JSONDecodeError:
                print("Failed to decode JSON")
        else:
            self.value = int(float(payload))

    def get_powermeter_watts(self):
        if self.value is not None:
            return [self.value]
        else:
            raise ValueError("No value received from MQTT")


class Script(Powermeter):
    def __init__(self, command: str):
        self.script = command

    def get_powermeter_watts(self):
        power = (
            subprocess.check_output(self.script, shell=True)
            .decode()
            .strip()
            .split("\n")
        )
        return [int(p) for p in power]


SHELLY_SECTION = "SHELLY"
TASMOTA_SECTION = "TASMOTA"
SHRDZM_SECTION = "SHRDZM"
EMLOG_SECTION = "EMLOG"
IOBROKER_SECTION = "IOBROKER"
HOMEASSITANT_SECTION = "HOMEASSISTANT"
VZLOGGER_SECTION = "VZLOGGER"
SCRIPT_SECTION = "SCRIPT"
ESPHOME_SECTION = "ESPHOME"
AMIS_READER_SECTION = "AMIS_READER"


# Helper function to create a powermeter instance
def create_powermeter(config: configparser.ConfigParser) -> Powermeter:
    if config.has_section("SHELLY"):
        shelly_type = config.get(SHELLY_SECTION, "TYPE", fallback="")
        shelly_ip = config.get(SHELLY_SECTION, "IP", fallback="")
        shelly_user = config.get(SHELLY_SECTION, "USER", fallback="")
        shelly_pass = config.get(SHELLY_SECTION, "PASS", fallback="")
        shelly_meterindex = config.get(SHELLY_SECTION, "METER_INDEX", fallback=None)
        if shelly_type == "1PM":
            return Shelly1PM(shelly_ip, shelly_user, shelly_pass, shelly_meterindex)
        elif shelly_type == "PLUS1PM":
            return ShellyPlus1PM(shelly_ip, shelly_user, shelly_pass, shelly_meterindex)
        elif shelly_type == "EM" or shelly_type == "3EM":
            return ShellyEM(shelly_ip, shelly_user, shelly_pass, shelly_meterindex)
        elif shelly_type == "3EMPro":
            return Shelly3EMPro(shelly_ip, shelly_user, shelly_pass, shelly_meterindex)
        else:
            raise Exception(f"Error: unknown Shelly type '{shelly_type}'")
    elif config.has_section(TASMOTA_SECTION):
        return Tasmota(
            config.get(TASMOTA_SECTION, "IP", fallback=""),
            config.get(TASMOTA_SECTION, "USER", fallback=""),
            config.get(TASMOTA_SECTION, "PASS", fallback=""),
            config.get(TASMOTA_SECTION, "JSON_STATUS", fallback=""),
            config.get(TASMOTA_SECTION, "JSON_PAYLOAD_MQTT_PREFIX", fallback=""),
            config.get(TASMOTA_SECTION, "JSON_POWER_MQTT_LABEL", fallback=""),
            config.get(TASMOTA_SECTION, "JSON_POWER_INPUT_MQTT_LABEL", fallback=""),
            config.get(TASMOTA_SECTION, "JSON_POWER_OUTPUT_MQTT_LABEL", fallback=""),
            config.getboolean(TASMOTA_SECTION, "JSON_POWER_CALCULATE", fallback=False),
        )
    elif config.has_section(SHRDZM_SECTION):
        return Shrdzm(
            config.get(SHRDZM_SECTION, "IP", fallback=""),
            config.get(SHRDZM_SECTION, "USER", fallback=""),
            config.get(SHRDZM_SECTION, "PASS", fallback=""),
        )
    elif config.has_section(EMLOG_SECTION):
        return Emlog(
            config.get(EMLOG_SECTION, "IP", fallback=""),
            config.get(EMLOG_SECTION, "METER_INDEX", fallback=""),
            config.getboolean(EMLOG_SECTION, "JSON_POWER_CALCULATE", fallback=False),
        )
    elif config.has_section(IOBROKER_SECTION):
        return IoBroker(
            config.get(IOBROKER_SECTION, "IP", fallback=""),
            config.get(IOBROKER_SECTION, "PORT", fallback=""),
            config.get(IOBROKER_SECTION, "CURRENT_POWER_ALIAS", fallback=""),
            config.getboolean(IOBROKER_SECTION, "POWER_CALCULATE", fallback=False),
            config.get(IOBROKER_SECTION, "POWER_INPUT_ALIAS", fallback=""),
            config.get(IOBROKER_SECTION, "POWER_OUTPUT_ALIAS", fallback=""),
        )
    elif config.has_section(HOMEASSITANT_SECTION):
        return HomeAssistant(
            config.get(HOMEASSITANT_SECTION, "IP", fallback=""),
            config.get(HOMEASSITANT_SECTION, "PORT", fallback=""),
            config.getboolean(HOMEASSITANT_SECTION, "HTTPS", fallback=False),
            config.get(HOMEASSITANT_SECTION, "ACCESSTOKEN", fallback=""),
            config.get(HOMEASSITANT_SECTION, "CURRENT_POWER_ENTITY", fallback=""),
            config.getboolean(HOMEASSITANT_SECTION, "POWER_CALCULATE", fallback=False),
            config.get(HOMEASSITANT_SECTION, "POWER_INPUT_ALIAS", fallback=""),
            config.get(HOMEASSITANT_SECTION, "POWER_OUTPUT_ALIAS", fallback=""),
        )
    elif config.has_section(VZLOGGER_SECTION):
        return VZLogger(
            config.get(VZLOGGER_SECTION, "IP", fallback=""),
            config.get(VZLOGGER_SECTION, "PORT", fallback=""),
            config.get(VZLOGGER_SECTION, "UUID", fallback=""),
        )
    elif config.has_section(SCRIPT_SECTION):
        return Script(config.get(SCRIPT_SECTION, "COMMAND", fallback=""))
    elif config.has_section(ESPHOME_SECTION):
        return ESPHome(
            config.get(ESPHOME_SECTION, "IP", fallback=""),
            config.get(ESPHOME_SECTION, "PORT", fallback=""),
            config.get(ESPHOME_SECTION, "DOMAIN", fallback=""),
            config.get(ESPHOME_SECTION, "ID", fallback=""),
        )
    elif config.has_section(AMIS_READER_SECTION):
        return AmisReader(config.get(AMIS_READER_SECTION, "IP", fallback=""))
    elif config.has_section("MQTT"):
        return MqttPowermeter(
            config.get("MQTT", "BROKER", fallback=""),
            config.getint("MQTT", "PORT", fallback=1883),
            config.get("MQTT", "TOPIC", fallback=""),
            config.get("MQTT", "JSON_PATH", fallback=None),
            config.get("MQTT", "USERNAME", fallback=None),
            config.get("MQTT", "PASSWORD", fallback=None),
        )
    else:
        raise Exception("Error: no powermeter defined!")


# Load configuration
cfg = configparser.ConfigParser()
cfg.read("config.ini")
powermeter = create_powermeter(cfg)
disable_sum_phases = cfg.getboolean("GENERAL", "DISABLE_SUM_PHASES", fallback=False)
allow_negative_values = cfg.getboolean(
    "GENERAL", "ALLOW_NEGATIVE_VALUES", fallback=False
)

# Time in seconds within which duplicate messages are ignored
DEDUPE_TIME_WINDOW = 10


# UDP server function
def udp_server():
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.bind(("", UDP_PORT))

    # Dictionary to keep track of the last response time for each address
    last_response_time = {}

    while True:
        data, addr = udp_sock.recvfrom(1024)
        decoded = data.decode()
        current_time = time.time()

        if decoded == "hame":
            # Check if we have responded to this address recently
            if (
                addr not in last_response_time
                or (current_time - last_response_time[addr]) > DEDUPE_TIME_WINDOW
            ):
                response_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                local_ip = udp_sock.getsockname()[0]
                response_sock.bind((local_ip, 0))
                response_sock.sendto(b"ack", addr)
                response_sock.close()

                last_response_time[addr] = current_time
                print(f"Received 'hame' from {addr}, sent 'ack'")
            else:
                print(f"Received 'hame' from {addr} but ignored due to dedupe window")
        else:
            print(f"Received unknown UDP message: {decoded}")


# Function to handle individual TCP client connections
def handle_tcp_client(conn, addr):
    print(f"TCP connection established with {addr}")
    try:
        data = conn.recv(1024)
        decoded = data.decode()
        if decoded == "hello":
            print("Received 'hello'")
            while True:
                values = powermeter.get_powermeter_watts()
                value1 = values[0] if len(values) > 0 else 0
                value2 = values[1] if len(values) > 1 else 0
                value3 = values[2] if len(values) > 2 else 0
                if not disable_sum_phases:
                    value1 += value2 + value3
                    value2 = value3 = 0
                if not allow_negative_values:
                    value1 = max(value1, 0)
                    value2 = max(value2, 0)
                    value3 = max(value3, 0)

                message = f"HM:{value1}|{value2}|{value3}"
                try:
                    conn.send(message.encode())
                    print(f"Sent message: {message}")
                    time.sleep(1)
                except BrokenPipeError:
                    print(
                        f"Connection with {addr} broken. Waiting for a new connection."
                    )
                    break
        else:
            print(f"Received unknown TCP message: {decoded}")
    finally:
        conn.close()


# TCP server function
def tcp_server():
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_sock.bind(("", TCP_PORT))
    tcp_sock.listen(5)
    print("TCP server is listening...")

    while True:
        conn, addr = tcp_sock.accept()
        client_thread = threading.Thread(
            target=handle_tcp_client, args=(conn, addr), daemon=True
        )
        client_thread.start()


# Run UDP and TCP servers in separate threads
udp_thread = threading.Thread(target=udp_server, daemon=True)
tcp_thread = threading.Thread(target=tcp_server, daemon=True)

udp_thread.start()
tcp_thread.start()

# Keep the main thread running
udp_thread.join()
tcp_thread.join()
