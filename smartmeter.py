import socket
import threading
import time
import random
import configparser
from requests.sessions import Session
from requests.auth import HTTPBasicAuth
from requests.auth import HTTPDigestAuth
import subprocess

# Define ports
UDP_PORT = 12345
TCP_PORT = 12345

# Initialize session for HTTP requests
session = Session()

# Powermeter classes
class Powermeter:
    def GetPowermeterWatts(self) -> int:
        raise NotImplementedError()

class Tasmota(Powermeter):
    def __init__(self, ip: str, user: str, password: str, json_status: str, json_payload_mqtt_prefix: str, json_power_mqtt_label: str, json_power_input_mqtt_label: str, json_power_output_mqtt_label: str, json_power_calculate: bool):
        self.ip = ip
        self.user = user
        self.password = password
        self.json_status = json_status
        self.json_payload_mqtt_prefix = json_payload_mqtt_prefix
        self.json_power_mqtt_label = json_power_mqtt_label
        self.json_power_input_mqtt_label = json_power_input_mqtt_label
        self.json_power_output_mqtt_label = json_power_output_mqtt_label
        self.json_power_calculate = json_power_calculate

    def GetJson(self, path):      
        url = f'http://{self.ip}{path}'
        return session.get(url, timeout=10).json()

    def GetPowermeterWatts(self):
        if not self.user:
            ParsedData = self.GetJson('/cm?cmnd=status%2010')
        else:
            ParsedData = self.GetJson(f'/cm?user={self.user}&password={self.password}&cmnd=status%2010')
        if not self.json_power_calculate:
            return int(ParsedData[self.json_status][self.json_payload_mqtt_prefix][self.json_power_mqtt_label])
        else:
            input = ParsedData[self.json_status][self.json_payload_mqtt_prefix][self.json_power_input_mqtt_label]
            output = ParsedData[self.json_status][self.json_payload_mqtt_prefix][self.json_power_output_mqtt_label]
            return int(input) - int(output)

class Shelly(Powermeter):
    def __init__(self, ip: str, user: str, password: str, emeterindex: str):
        self.ip = ip
        self.user = user
        self.password = password
        self.emeterindex = emeterindex

    def GetJson(self, path):
        url = f'http://{self.ip}{path}'
        headers = {"content-type": "application/json"}
        return session.get(url, headers=headers, auth=(self.user, self.password), timeout=10).json()

    def GetRpcJson(self, path):
        url = f'http://{self.ip}/rpc{path}'
        headers = {"content-type": "application/json"}
        return session.get(url, headers=headers, auth=HTTPDigestAuth(self.user, self.password), timeout=10).json()

    def GetPowermeterWatts(self) -> int:
        raise NotImplementedError()

class Shelly1PM(Shelly):
    def GetPowermeterWatts(self):
        return int(self.GetJson('/status')['meters'][0]['power'])

class ShellyPlus1PM(Shelly):
    def GetPowermeterWatts(self):
        return int(self.GetRpcJson('/Switch.GetStatus?id=0')['apower'])

class ShellyEM(Shelly):
    def GetPowermeterWatts(self):
        if self.emeterindex:
            return int(self.GetJson(f'/emeter/{self.emeterindex}')['power'])
        else:
            return sum(int(emeter['power']) for emeter in self.GetJson('/status')['emeters'])

class Shelly3EM(Shelly):
    def GetPowermeterWatts(self):
        return int(self.GetJson('/status')['total_power'])

class Shelly3EMPro(Shelly):
    def GetPowermeterWatts(self):
        return int(self.GetRpcJson('/EM.GetStatus?id=0')['total_act_power'])

class ESPHome(Powermeter):
    def __init__(self, ip: str, port: str, domain: str, id: str):
        self.ip = ip
        self.port = port
        self.domain = domain
        self.id = id

    def GetJson(self, path):
        url = f'http://{self.ip}:{self.port}{path}'
        return session.get(url, timeout=10).json()

    def GetPowermeterWatts(self):
        ParsedData = self.GetJson(f'/{self.domain}/{self.id}')
        return int(ParsedData['value'])

class Shrdzm(Powermeter):
    def __init__(self, ip: str, user: str, password: str):
        self.ip = ip
        self.user = user
        self.password = password

    def GetJson(self, path):
        url = f'http://{self.ip}{path}'
        return session.get(url, timeout=10).json()

    def GetPowermeterWatts(self):
        ParsedData = self.GetJson(f'/getLastData?user={self.user}&password={self.password}')
        return int(int(ParsedData['1.7.0']) - int(ParsedData['2.7.0']))

class Emlog(Powermeter):
    def __init__(self, ip: str, meterindex: str, json_power_calculate: bool):
        self.ip = ip
        self.meterindex = meterindex
        self.json_power_calculate = json_power_calculate

    def GetJson(self, path):
        url = f'http://{self.ip}{path}'
        return session.get(url, timeout=10).json()

    def GetPowermeterWatts(self):
        ParsedData = self.GetJson(f'/pages/getinformation.php?heute&meterindex={self.meterindex}')
        if not self.json_power_calculate:
            return int(ParsedData['Leistung170'])
        else:
            input = ParsedData['Leistung170']
            output = ParsedData['Leistung270']
            return int(input) - int(output)

class IoBroker(Powermeter):
    def __init__(self, ip: str, port: str, current_power_alias: str, power_calculate: bool, power_input_alias: str, power_output_alias: str):
        self.ip = ip
        self.port = port
        self.current_power_alias = current_power_alias
        self.power_calculate = power_calculate
        self.power_input_alias = power_input_alias
        self.power_output_alias = power_output_alias

    def GetJson(self, path):
        url = f'http://{self.ip}:{self.port}{path}'
        return session.get(url, timeout=10).json()

    def GetPowermeterWatts(self):
        if not self.power_calculate:
            ParsedData = self.GetJson(f'/getBulk/{self.current_power_alias}')
            for item in ParsedData:
                if item['id'] == self.current_power_alias:
                    return int(item['val'])
        else:
            ParsedData = self.GetJson(f'/getBulk/{self.power_input_alias},{self.power_output_alias}')
            for item in ParsedData:
                if item['id'] == self.power_input_alias:
                    input = int(item['val'])
                if item['id'] == self.power_output_alias:
                    output = int(item['val'])
            return input - output

class HomeAssistant(Powermeter):
    def __init__(self, ip: str, port: str, use_https: bool, access_token: str, current_power_entity: str, power_calculate: bool, power_input_alias: str, power_output_alias: str):
        self.ip = ip
        self.port = port
        self.use_https = use_https
        self.access_token = access_token
        self.current_power_entity = current_power_entity
        self.power_calculate = power_calculate
        self.power_input_alias = power_input_alias
        self.power_output_alias = power_output_alias

    def GetJson(self, path):
        if self.use_https:
            url = f"https://{self.ip}:{self.port}{path}"
        else:
            url = f"http://{self.ip}:{self.port}{path}"
        headers = {"Authorization": "Bearer " + self.access_token, "content-type": "application/json"}
        return session.get(url, headers=headers, timeout=10).json()

    def GetPowermeterWatts(self):
        if not self.power_calculate:
            ParsedData = self.GetJson(f"/api/states/{self.current_power_entity}")
            return int(ParsedData['state'])
        else:
            ParsedData = self.GetJson(f"/api/states/{self.power_input_alias}")
            input = int(ParsedData['state'])
            ParsedData = self.GetJson(f"/api/states/{self.power_output_alias}")
            output = int(ParsedData['state'])
            return input - output

class VZLogger(Powermeter):
    def __init__(self, ip: str, port: str, uuid: str):
        self.ip = ip
        self.port = port
        self.uuid = uuid

    def GetJson(self):
        url = f"http://{self.ip}:{self.port}/{self.uuid}"
        return session.get(url, timeout=10).json()

    def GetPowermeterWatts(self):
        return int(self.GetJson()['data'][0]['tuples'][0][1])

class AmisReader(Powermeter):
    def __init__(self, ip: str):
        self.ip = ip

    def GetJson(self, path):
        url = f'http://{self.ip}{path}'
        return session.get(url, timeout=10).json()

    def GetPowermeterWatts(self):
        ParsedData = self.GetJson('/rest')
        return int(ParsedData['saldo'])

class Script(Powermeter):
    def __init__(self, file: str, ip: str, user: str, password: str):
        self.file = file
        self.ip = ip
        self.user = user
        self.password = password

    def GetPowermeterWatts(self):
        power = subprocess.check_output([self.file, self.ip, self.user, self.password])
        return int(power)

# Helper function to create a powermeter instance
def CreatePowermeter(config) -> Powermeter:
    shelly_ip = config.get('SHELLY', 'SHELLY_IP', fallback='')
    shelly_user = config.get('SHELLY', 'SHELLY_USER', fallback='')
    shelly_pass = config.get('SHELLY', 'SHELLY_PASS', fallback='')
    shelly_emeterindex = config.get('SHELLY', 'EMETER_INDEX', fallback='')
    if config.getboolean('SELECT_POWERMETER', 'USE_SHELLY_EM', fallback=False):
        return ShellyEM(shelly_ip, shelly_user, shelly_pass, shelly_emeterindex)
    elif config.getboolean('SELECT_POWERMETER', 'USE_SHELLY_3EM', fallback=False):
        return Shelly3EM(shelly_ip, shelly_user, shelly_pass, shelly_emeterindex)
    elif config.getboolean('SELECT_POWERMETER', 'USE_SHELLY_3EM_PRO', fallback=False):
        return Shelly3EMPro(shelly_ip, shelly_user, shelly_pass, shelly_emeterindex)
    elif config.getboolean('SELECT_POWERMETER', 'USE_TASMOTA', fallback=False):
        return Tasmota(
            config.get('TASMOTA', 'TASMOTA_IP', fallback=''),
            config.get('TASMOTA', 'TASMOTA_USER', fallback=''),
            config.get('TASMOTA', 'TASMOTA_PASS', fallback=''),
            config.get('TASMOTA', 'TASMOTA_JSON_STATUS', fallback=''),
            config.get('TASMOTA', 'TASMOTA_JSON_PAYLOAD_MQTT_PREFIX', fallback=''),
            config.get('TASMOTA', 'TASMOTA_JSON_POWER_MQTT_LABEL', fallback=''),
            config.get('TASMOTA', 'TASMOTA_JSON_POWER_INPUT_MQTT_LABEL', fallback=''),
            config.get('TASMOTA', 'TASMOTA_JSON_POWER_OUTPUT_MQTT_LABEL', fallback=''),
            config.getboolean('TASMOTA', 'TASMOTA_JSON_POWER_CALCULATE', fallback=False)
        )
    elif config.getboolean('SELECT_POWERMETER', 'USE_SHRDZM', fallback=False):
        return Shrdzm(
            config.get('SHRDZM', 'SHRDZM_IP', fallback=''),
            config.get('SHRDZM', 'SHRDZM_USER', fallback=''),
            config.get('SHRDZM', 'SHRDZM_PASS', fallback='')
        )
    elif config.getboolean('SELECT_POWERMETER', 'USE_EMLOG', fallback=False):
        return Emlog(
            config.get('EMLOG', 'EMLOG_IP', fallback=''),
            config.get('EMLOG', 'EMLOG_METERINDEX', fallback=''),
            config.getboolean('EMLOG', 'EMLOG_JSON_POWER_CALCULATE', fallback=False)
        )
    elif config.getboolean('SELECT_POWERMETER', 'USE_IOBROKER', fallback=False):
        return IoBroker(
            config.get('IOBROKER', 'IOBROKER_IP', fallback=''),
            config.get('IOBROKER', 'IOBROKER_PORT', fallback=''),
            config.get('IOBROKER', 'IOBROKER_CURRENT_POWER_ALIAS', fallback=''),
            config.getboolean('IOBROKER', 'IOBROKER_POWER_CALCULATE', fallback=False),
            config.get('IOBROKER', 'IOBROKER_POWER_INPUT_ALIAS', fallback=''),
            config.get('IOBROKER', 'IOBROKER_POWER_OUTPUT_ALIAS', fallback='')
        )
    elif config.getboolean('SELECT_POWERMETER', 'USE_HOMEASSISTANT', fallback=False):
        return HomeAssistant(
            config.get('HOMEASSISTANT', 'HA_IP', fallback=''),
            config.get('HOMEASSISTANT', 'HA_PORT', fallback=''),
            config.getboolean('HOMEASSISTANT', 'HA_HTTPS', fallback=False),
            config.get('HOMEASSISTANT', 'HA_ACCESSTOKEN', fallback=''),
            config.get('HOMEASSISTANT', 'HA_CURRENT_POWER_ENTITY', fallback=''),
            config.getboolean('HOMEASSISTANT', 'HA_POWER_CALCULATE', fallback=False),
            config.get('HOMEASSISTANT', 'HA_POWER_INPUT_ALIAS', fallback=''),
            config.get('HOMEASSISTANT', 'HA_POWER_OUTPUT_ALIAS', fallback='')
        )
    elif config.getboolean('SELECT_POWERMETER', 'USE_VZLOGGER', fallback=False):
        return VZLogger(
            config.get('VZLOGGER', 'VZL_IP', fallback=''),
            config.get('VZLOGGER', 'VZL_PORT', fallback=''),
            config.get('VZLOGGER', 'VZL_UUID', fallback='')
        )
    elif config.getboolean('SELECT_POWERMETER', 'USE_SCRIPT', fallback=False):
        return Script(
            config.get('SCRIPT', 'SCRIPT_FILE', fallback=''),
            config.get('SCRIPT', 'SCRIPT_IP', fallback=''),
            config.get('SCRIPT', 'SCRIPT_USER', fallback=''),
            config.get('SCRIPT', 'SCRIPT_PASS', fallback='')
        )
    elif config.getboolean('SELECT_POWERMETER', 'USE_AMIS_READER', fallback=False):
        return AmisReader(
            config.get('AMIS_READER', 'AMIS_READER_IP', fallback='')
        )
    else:
        raise Exception("Error: no powermeter defined!")

# Load configuration
config = configparser.ConfigParser()
config.read("powermeter_config.ini")
powermeter = CreatePowermeter(config)

# UDP server function
def udp_server():
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.bind(("", UDP_PORT))
    
    while True:
        data, addr = udp_sock.recvfrom(1024)
        if data.decode() == "hame":
            udp_sock.sendto(b"ack", addr)
            print(f"Received 'hame' from {addr}, sent 'ack'")

# TCP server function
def tcp_server():
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_sock.bind(("", TCP_PORT))
    tcp_sock.listen(1)
    print("TCP server is listening...")

    while True:
        conn, addr = tcp_sock.accept()
        print(f"TCP connection established with {addr}")
        try:
            data = conn.recv(1024)
            if data.decode() == "hello":
                print("Received 'hello'")
                while True:
                    random_value = powermeter.GetPowermeterWatts()
                    message = f"HM:{random_value}|0|0"
                    try:
                        conn.send(message.encode())
                        print(f"Sent message: {message}")
                        time.sleep(1)
                    except BrokenPipeError:
                        print(f"Connection with {addr} broken. Waiting for a new connection.")
                        break
        finally:
            conn.close()

# Run UDP and TCP servers in separate threads
udp_thread = threading.Thread(target=udp_server, daemon=True)
tcp_thread = threading.Thread(target=tcp_server, daemon=True)

udp_thread.start()
tcp_thread.start()

# Keep the main thread running
udp_thread.join()
tcp_thread.join()
