import configparser
from ipaddress import IPv4Network, IPv4Address
from typing import List, Union, Tuple
from config.logger import logger

from powermeter import (
    Powermeter,
    Tasmota,
    Shelly1PM,
    ShellyPlus1PM,
    ShellyEM,
    Shelly3EM,
    Shelly3EMPro,
    Shrdzm,
    Emlog,
    IoBroker,
    HomeAssistant,
    VZLogger,
    AmisReader,
    ModbusPowermeter,
    MqttPowermeter,
    Script,
    ESPHome,
    ThrottledPowermeter,
)

SHELLY_SECTION = "SHELLY"
TASMOTA_SECTION = "TASMOTA"
SHRDZM_SECTION = "SHRDZM"
EMLOG_SECTION = "EMLOG"
IOBROKER_SECTION = "IOBROKER"
HOMEASSISTANT_SECTION = "HOMEASSISTANT"
VZLOGGER_SECTION = "VZLOGGER"
SCRIPT_SECTION = "SCRIPT"
ESPHOME_SECTION = "ESPHOME"
AMIS_READER_SECTION = "AMIS_READER"
MODBUS_SECTION = "MODBUS"


class ClientFilter:
    def __init__(self, netmasks: List[IPv4Network]):
        self.netmasks = netmasks

    def matches(self, client_ip) -> bool:
        try:
            client_ip_addr = IPv4Address(client_ip)
            for netmask in self.netmasks:
                if client_ip_addr in netmask:
                    return True
        except ValueError as e:
            logger.error(f"Error: {e}")
            return False


def read_all_powermeter_configs(
    config: configparser.ConfigParser,
) -> List[Tuple[Powermeter, ClientFilter]]:
    powermeters = []
    global_throttle_interval = config.getfloat(
        "GENERAL", "THROTTLE_INTERVAL", fallback=0.0
    )

    for section in config.sections():
        powermeter = create_powermeter(section, config)
        if powermeter is not None:
            section_throttle_interval = config.getfloat(
                section, "THROTTLE_INTERVAL", fallback=global_throttle_interval
            )

            if section_throttle_interval > 0:
                throttle_source = (
                    "section-specific"
                    if config.has_option(section, "THROTTLE_INTERVAL")
                    else "global"
                )
                print(
                    f"Applying {throttle_source} throttling ({section_throttle_interval}s) to {section}"
                )
                powermeter = ThrottledPowermeter(powermeter, section_throttle_interval)

            client_filter = create_client_filter(section, config)
            powermeters.append((powermeter, client_filter))
    return powermeters


def create_client_filter(
    section: str, config: configparser.ConfigParser
) -> ClientFilter:
    netmasks = config.get(section, "NETMASK", fallback="0.0.0.0/0")
    netmasks = [IPv4Network(netmask) for netmask in netmasks.split(",")]
    return ClientFilter(netmasks)


# Helper function to create a powermeter instance
def create_powermeter(
    section: str, config: configparser.ConfigParser
) -> Union[Powermeter, None]:
    if section.startswith(SHELLY_SECTION):
        return create_shelly_powermeter(section, config)
    elif section.startswith(TASMOTA_SECTION):
        return create_tasmota_powermeter(section, config)
    elif section.startswith(SHRDZM_SECTION):
        return create_shrdzm_powermeter(section, config)
    elif section.startswith(EMLOG_SECTION):
        return create_emlog_powermeter(section, config)
    elif section.startswith(IOBROKER_SECTION):
        return create_iobroker_powermeter(section, config)
    elif section.startswith(HOMEASSISTANT_SECTION):
        return create_homeassistant_powermeter(section, config)
    elif section.startswith(VZLOGGER_SECTION):
        return create_vzlogger_powermeter(section, config)
    elif section.startswith(SCRIPT_SECTION):
        return create_script_powermeter(section, config)
    elif section.startswith(ESPHOME_SECTION):
        return create_esphome_powermeter(section, config)
    elif section.startswith(AMIS_READER_SECTION):
        return create_amisreader_powermeter(section, config)
    elif section.startswith(MODBUS_SECTION):
        return create_modbus_powermeter(section, config)
    elif section.startswith("MQTT"):
        return create_mqtt_powermeter(section, config)
    else:
        return None


def create_shelly_powermeter(
    section: str, config: configparser.ConfigParser
) -> Powermeter:
    shelly_type = config.get(section, "TYPE", fallback="")
    shelly_ip = config.get(section, "IP", fallback="")
    shelly_user = config.get(section, "USER", fallback="")
    shelly_pass = config.get(section, "PASS", fallback="")
    shelly_meterindex = config.get(section, "METER_INDEX", fallback=None)
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


def create_amisreader_powermeter(
    section: str, config: configparser.ConfigParser
) -> Powermeter:
    return AmisReader(config.get(section, "IP", fallback=""))


def create_script_powermeter(
    section: str, config: configparser.ConfigParser
) -> Powermeter:
    return Script(config.get(section, "COMMAND", fallback=""))


def create_mqtt_powermeter(
    section: str, config: configparser.ConfigParser
) -> Powermeter:
    return MqttPowermeter(
        config.get(section, "BROKER", fallback=""),
        config.getint(section, "PORT", fallback=1883),
        config.get(section, "TOPIC", fallback=""),
        config.get(section, "JSON_PATH", fallback=None),
        config.get(section, "USERNAME", fallback=None),
        config.get(section, "PASSWORD", fallback=None),
    )


def create_modbus_powermeter(
    section: str, config: configparser.ConfigParser
) -> Powermeter:
    return ModbusPowermeter(
        config.get(section, "HOST", fallback=""),
        config.getint(section, "PORT", fallback=502),
        config.getint(section, "UNIT_ID", fallback=1),
        config.getint(section, "ADDRESS", fallback=0),
        config.getint(section, "COUNT", fallback=1),
        config.get(section, "DATA_TYPE", fallback="UINT16"),
        config.get(section, "BYTE_ORDER", fallback="BIG"),
        config.get(section, "WORD_ORDER", fallback="BIG"),
    )


def create_esphome_powermeter(
    section: str, config: configparser.ConfigParser
) -> Powermeter:
    return ESPHome(
        config.get(section, "IP", fallback=""),
        config.get(section, "PORT", fallback=""),
        config.get(section, "DOMAIN", fallback=""),
        config.get(section, "ID", fallback=""),
    )


def create_vzlogger_powermeter(
    section: str, config: configparser.ConfigParser
) -> Powermeter:
    return VZLogger(
        config.get(section, "IP", fallback=""),
        config.get(section, "PORT", fallback=""),
        config.get(section, "UUID", fallback=""),
    )


def create_homeassistant_powermeter(
    section: str, config: configparser.ConfigParser
) -> Powermeter:
    # Split entity strings on commas and strip whitespace
    def parse_entities(value: str) -> Union[str, List[str]]:
        if not value:
            return ""
        entities = [entity.strip() for entity in value.split(",")]
        # Return single string if only one entity, otherwise return list
        return entities[0] if len(entities) == 1 else entities

    current_power_entity = parse_entities(
        config.get(section, "CURRENT_POWER_ENTITY", fallback="")
    )
    power_input_alias = parse_entities(
        config.get(section, "POWER_INPUT_ALIAS", fallback="")
    )
    power_output_alias = parse_entities(
        config.get(section, "POWER_OUTPUT_ALIAS", fallback="")
    )

    return HomeAssistant(
        config.get(section, "IP", fallback=""),
        config.get(section, "PORT", fallback=""),
        config.getboolean(section, "HTTPS", fallback=False),
        config.get(section, "ACCESSTOKEN", fallback=""),
        current_power_entity,
        config.getboolean(section, "POWER_CALCULATE", fallback=False),
        power_input_alias,
        power_output_alias,
        config.get(section, "API_PATH_PREFIX", fallback=None),
    )


def create_iobroker_powermeter(
    section: str, config: configparser.ConfigParser
) -> Powermeter:
    return IoBroker(
        config.get(section, "IP", fallback=""),
        config.get(section, "PORT", fallback=""),
        config.get(section, "CURRENT_POWER_ALIAS", fallback=""),
        config.getboolean(section, "POWER_CALCULATE", fallback=False),
        config.get(section, "POWER_INPUT_ALIAS", fallback=""),
        config.get(section, "POWER_OUTPUT_ALIAS", fallback=""),
    )


def create_emlog_powermeter(
    section: str, config: configparser.ConfigParser
) -> Powermeter:
    return Emlog(
        config.get(section, "IP", fallback=""),
        config.get(section, "METER_INDEX", fallback=""),
        config.getboolean(section, "JSON_POWER_CALCULATE", fallback=False),
    )


def create_shrdzm_powermeter(
    section: str, config: configparser.ConfigParser
) -> Powermeter:
    return Shrdzm(
        config.get(section, "IP", fallback=""),
        config.get(section, "USER", fallback=""),
        config.get(section, "PASS", fallback=""),
    )


def create_tasmota_powermeter(
    section: str, config: configparser.ConfigParser
) -> Powermeter:
    return Tasmota(
        config.get(section, "IP", fallback=""),
        config.get(section, "USER", fallback=""),
        config.get(section, "PASS", fallback=""),
        config.get(section, "JSON_STATUS", fallback=""),
        config.get(section, "JSON_PAYLOAD_MQTT_PREFIX", fallback=""),
        config.get(section, "JSON_POWER_MQTT_LABEL", fallback=""),
        config.get(section, "JSON_POWER_INPUT_MQTT_LABEL", fallback=""),
        config.get(section, "JSON_POWER_OUTPUT_MQTT_LABEL", fallback=""),
        config.getboolean(section, "JSON_POWER_CALCULATE", fallback=False),
    )
