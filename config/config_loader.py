import configparser
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
)

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
MODBUS_SECTION = "MODBUS"


# Helper function to create a powermeter instance
def create_powermeter(config: configparser.ConfigParser) -> Powermeter:
    if config.has_section(SHELLY_SECTION):
        return create_shelly_powermeter(config)
    elif config.has_section(TASMOTA_SECTION):
        return create_tasmota_powermeter(config)
    elif config.has_section(SHRDZM_SECTION):
        return create_shrdzm_powermeter(config)
    elif config.has_section(EMLOG_SECTION):
        return create_emlog_powermeter(config)
    elif config.has_section(IOBROKER_SECTION):
        return create_iobroker_powermeter(config)
    elif config.has_section(HOMEASSITANT_SECTION):
        return create_homeassistant_powermeter(config)
    elif config.has_section(VZLOGGER_SECTION):
        return create_vzlogger_powermeter(config)
    elif config.has_section(SCRIPT_SECTION):
        return create_script_powermeter(config)
    elif config.has_section(ESPHOME_SECTION):
        return create_esphome_powermeter(config)
    elif config.has_section(AMIS_READER_SECTION):
        return create_amisreader_powermeter(config)
    elif config.has_section(MODBUS_SECTION):
        return create_modbus_powermeter(config)
    elif config.has_section("MQTT"):
        return create_mqtt_powermeter(config)
    else:
        raise Exception("Error: no powermeter defined!")


def create_shelly_powermeter(config):
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


def create_amisreader_powermeter(config):
    return AmisReader(config.get(AMIS_READER_SECTION, "IP", fallback=""))


def create_script_powermeter(config):
    return Script(config.get(SCRIPT_SECTION, "COMMAND", fallback=""))


def create_mqtt_powermeter(config):
    return MqttPowermeter(
        config.get("MQTT", "BROKER", fallback=""),
        config.getint("MQTT", "PORT", fallback=1883),
        config.get("MQTT", "TOPIC", fallback=""),
        config.get("MQTT", "JSON_PATH", fallback=None),
        config.get("MQTT", "USERNAME", fallback=None),
        config.get("MQTT", "PASSWORD", fallback=None),
    )


def create_modbus_powermeter(config):
    return ModbusPowermeter(
        config.get(MODBUS_SECTION, "HOST", fallback=""),
        config.getint(MODBUS_SECTION, "PORT", fallback=502),
        config.getint(MODBUS_SECTION, "UNIT_ID", fallback=1),
        config.getint(MODBUS_SECTION, "ADDRESS", fallback=0),
        config.getint(MODBUS_SECTION, "COUNT", fallback=1),
    )


def create_esphome_powermeter(config):
    return ESPHome(
        config.get(ESPHOME_SECTION, "IP", fallback=""),
        config.get(ESPHOME_SECTION, "PORT", fallback=""),
        config.get(ESPHOME_SECTION, "DOMAIN", fallback=""),
        config.get(ESPHOME_SECTION, "ID", fallback=""),
    )


def create_vzlogger_powermeter(config):
    return VZLogger(
        config.get(VZLOGGER_SECTION, "IP", fallback=""),
        config.get(VZLOGGER_SECTION, "PORT", fallback=""),
        config.get(VZLOGGER_SECTION, "UUID", fallback=""),
    )


def create_homeassistant_powermeter(config):
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


def create_iobroker_powermeter(config):
    return IoBroker(
        config.get(IOBROKER_SECTION, "IP", fallback=""),
        config.get(IOBROKER_SECTION, "PORT", fallback=""),
        config.get(IOBROKER_SECTION, "CURRENT_POWER_ALIAS", fallback=""),
        config.getboolean(IOBROKER_SECTION, "POWER_CALCULATE", fallback=False),
        config.get(IOBROKER_SECTION, "POWER_INPUT_ALIAS", fallback=""),
        config.get(IOBROKER_SECTION, "POWER_OUTPUT_ALIAS", fallback=""),
    )


def create_emlog_powermeter(config):
    return Emlog(
        config.get(EMLOG_SECTION, "IP", fallback=""),
        config.get(EMLOG_SECTION, "METER_INDEX", fallback=""),
        config.getboolean(EMLOG_SECTION, "JSON_POWER_CALCULATE", fallback=False),
    )


def create_shrdzm_powermeter(config):
    return Shrdzm(
        config.get(SHRDZM_SECTION, "IP", fallback=""),
        config.get(SHRDZM_SECTION, "USER", fallback=""),
        config.get(SHRDZM_SECTION, "PASS", fallback=""),
    )


def create_tasmota_powermeter(config):
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
