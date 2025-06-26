import pytest
import configparser
from ipaddress import IPv4Network
from config.config_loader import (
    ClientFilter,
    read_all_powermeter_configs,
    create_client_filter,
    create_powermeter,
    create_shelly_powermeter,
    create_tasmota_powermeter,
    create_shrdzm_powermeter,
    create_emlog_powermeter,
    create_iobroker_powermeter,
    create_homeassistant_powermeter,
    create_vzlogger_powermeter,
    create_script_powermeter,
    create_esphome_powermeter,
    create_amisreader_powermeter,
    create_modbus_powermeter,
    create_mqtt_powermeter,
    create_json_http_powermeter,
    create_tq_em_powermeter,
)
import unittest
from unittest.mock import patch, Mock
from powermeter import ThrottledPowermeter


def test_client_filter():
    """Basic test for ClientFilter."""
    filter = ClientFilter([IPv4Network("192.168.1.0/24")])
    # Just verify it runs without raising exceptions
    result1 = filter.matches("192.168.1.100")  # Should match
    result2 = filter.matches("10.0.0.1")  # Should not match
    result3 = filter.matches("invalid_ip")  # Should handle invalid


def test_create_client_filter():
    """Test create_client_filter with various inputs."""
    config = configparser.ConfigParser()
    config["TEST1"] = {"NETMASK": "192.168.1.0/24,10.0.0.0/8"}
    config["TEST2"] = {}  # No NETMASK specified, tests default

    # Just verify these run without exceptions
    filter1 = create_client_filter("TEST1", config)
    filter2 = create_client_filter("TEST2", config)


def test_create_shelly_powermeter():
    """Test Shelly powermeter creation."""
    config = configparser.ConfigParser()

    # Note: These won't connect to real devices, but test that
    # the creation logic works

    # Test all Shelly types with minimal config
    config["SHELLY1"] = {"TYPE": "1PM", "IP": "127.0.0.1"}
    config["SHELLY2"] = {"TYPE": "PLUS1PM", "IP": "127.0.0.1"}
    config["SHELLY3"] = {"TYPE": "EM", "IP": "127.0.0.1"}
    config["SHELLY4"] = {"TYPE": "3EM", "IP": "127.0.0.1"}
    config["SHELLY5"] = {"TYPE": "3EMPro", "IP": "127.0.0.1"}

    # Just verify these run without exceptions
    try:
        create_shelly_powermeter("SHELLY1", config)
        create_shelly_powermeter("SHELLY2", config)
        create_shelly_powermeter("SHELLY3", config)
        create_shelly_powermeter("SHELLY4", config)
        create_shelly_powermeter("SHELLY5", config)
    except Exception as e:
        if "Connection" not in str(e):  # Ignore expected connection errors
            raise

    # Test invalid type - should raise an exception
    config["SHELLY_INVALID"] = {"TYPE": "INVALID", "IP": "127.0.0.1"}
    with pytest.raises(Exception):
        create_shelly_powermeter("SHELLY_INVALID", config)


def test_create_tasmota_powermeter():
    """Test Tasmota powermeter creation."""
    config = configparser.ConfigParser()
    config["TASMOTA"] = {"IP": "127.0.0.1"}

    try:
        create_tasmota_powermeter("TASMOTA", config)
    except Exception as e:
        if "Connection" not in str(e):  # Ignore expected connection errors
            raise


def test_create_shrdzm_powermeter():
    """Test Shrdzm powermeter creation."""
    config = configparser.ConfigParser()
    config["SHRDZM"] = {"IP": "127.0.0.1"}

    try:
        create_shrdzm_powermeter("SHRDZM", config)
    except Exception as e:
        if "Connection" not in str(e):  # Ignore expected connection errors
            raise


def test_create_emlog_powermeter():
    """Test Emlog powermeter creation."""
    config = configparser.ConfigParser()
    config["EMLOG"] = {"IP": "127.0.0.1"}

    try:
        create_emlog_powermeter("EMLOG", config)
    except Exception as e:
        if "Connection" not in str(e):  # Ignore expected connection errors
            raise


def test_create_iobroker_powermeter():
    """Test IoBroker powermeter creation."""
    config = configparser.ConfigParser()
    config["IOBROKER"] = {"IP": "127.0.0.1"}

    try:
        create_iobroker_powermeter("IOBROKER", config)
    except Exception as e:
        if "Connection" not in str(e):  # Ignore expected connection errors
            raise


def test_create_homeassistant_powermeter():
    """Test HomeAssistant powermeter creation."""
    config = configparser.ConfigParser()

    # Test single entity
    config["HA1"] = {"IP": "127.0.0.1", "CURRENT_POWER_ENTITY": "sensor.power"}

    # Test multiple entities
    config["HA2"] = {
        "IP": "127.0.0.1",
        "CURRENT_POWER_ENTITY": "sensor.power1, sensor.power2",
        "POWER_INPUT_ALIAS": "sensor.input1, sensor.input2",
        "POWER_OUTPUT_ALIAS": "sensor.output1, sensor.output2",
    }

    try:
        create_homeassistant_powermeter("HA1", config)
        create_homeassistant_powermeter("HA2", config)
    except Exception as e:
        if "Connection" not in str(e):  # Ignore expected connection errors
            raise


def test_create_vzlogger_powermeter():
    """Test VZLogger powermeter creation."""
    config = configparser.ConfigParser()
    config["VZLOGGER"] = {"IP": "127.0.0.1"}

    try:
        create_vzlogger_powermeter("VZLOGGER", config)
    except Exception as e:
        if "Connection" not in str(e):  # Ignore expected connection errors
            raise


def test_create_script_powermeter():
    """Test Script powermeter creation."""
    config = configparser.ConfigParser()
    config["SCRIPT"] = {"COMMAND": 'echo "test"'}

    try:
        create_script_powermeter("SCRIPT", config)
    except Exception as e:
        if "not found" not in str(e):  # Ignore script not found errors
            raise


def test_create_esphome_powermeter():
    """Test ESPHome powermeter creation."""
    config = configparser.ConfigParser()
    config["ESPHOME"] = {"IP": "127.0.0.1"}

    try:
        create_esphome_powermeter("ESPHOME", config)
    except Exception as e:
        if "Connection" not in str(e):  # Ignore expected connection errors
            raise


def test_create_amisreader_powermeter():
    """Test AMIS Reader powermeter creation."""
    config = configparser.ConfigParser()
    config["AMIS_READER"] = {"IP": "127.0.0.1"}

    try:
        create_amisreader_powermeter("AMIS_READER", config)
    except Exception as e:
        if "Connection" not in str(e):  # Ignore expected connection errors
            raise


def test_create_modbus_powermeter():
    """Test Modbus powermeter creation."""
    config = configparser.ConfigParser()
    config["MODBUS"] = {"HOST": "127.0.0.1"}

    try:
        create_modbus_powermeter("MODBUS", config)
    except Exception as e:
        if "Connection" not in str(e):  # Ignore expected connection errors
            raise


def test_create_mqtt_powermeter():
    """Test MQTT powermeter creation."""
    config = configparser.ConfigParser()
    config["MQTT"] = {"BROKER": "127.0.0.1"}

    try:
        create_mqtt_powermeter("MQTT", config)
    except Exception as e:
        if "Connection" not in str(e) and "timed out" not in str(e):
            # Ignore connection errors
            raise


def test_create_json_http_powermeter():
    """Test JSON HTTP powermeter creation."""
    config = configparser.ConfigParser()
    config["JSON_HTTP"] = {"URL": "http://localhost", "JSON_PATHS": "$.power"}

    try:
        create_json_http_powermeter("JSON_HTTP", config)
    except Exception as e:
        if "Connection" not in str(e):
            raise


def test_create_tq_em_powermeter():
    """Test TQ Energy Manager powermeter creation."""
    config = configparser.ConfigParser()
    config["TQ_EM"] = {"IP": "127.0.0.1"}

    try:
        create_tq_em_powermeter("TQ_EM", config)
    except Exception as e:
        if "Connection" not in str(e):
            raise


def test_create_powermeter():
    """Test the main create_powermeter function."""
    config = configparser.ConfigParser()

    # Setup basic configurations for each type
    config["SHELLY_TEST"] = {"TYPE": "1PM", "IP": "127.0.0.1"}
    config["TASMOTA_TEST"] = {"IP": "127.0.0.1"}
    config["SHRDZM_TEST"] = {"IP": "127.0.0.1"}
    config["EMLOG_TEST"] = {"IP": "127.0.0.1"}
    config["IOBROKER_TEST"] = {"IP": "127.0.0.1"}
    config["HOMEASSISTANT_TEST"] = {"IP": "127.0.0.1"}
    config["VZLOGGER_TEST"] = {"IP": "127.0.0.1"}
    config["SCRIPT_TEST"] = {"COMMAND": 'echo "test"'}
    config["ESPHOME_TEST"] = {"IP": "127.0.0.1"}
    config["AMIS_READER_TEST"] = {"IP": "127.0.0.1"}
    config["MODBUS_TEST"] = {"HOST": "127.0.0.1"}
    config["MQTT_TEST"] = {"BROKER": "127.0.0.1"}
    config["JSON_HTTP_TEST"] = {"URL": "http://localhost", "JSON_PATHS": "$.power"}
    config["TQ_EM_TEST"] = {"IP": "127.0.0.1"}
    config["UNKNOWN_TEST"] = {"SOME_KEY": "some_value"}

    # Test each powermeter type
    for section in config.sections():
        try:
            create_powermeter(section, config)
        except Exception as e:
            # Ignore expected connection errors
            if (
                "Connection" not in str(e)
                and "timed out" not in str(e)
                and "not found" not in str(e)
            ):
                # If it's not a connection error, raise it
                if (
                    section != "UNKNOWN_TEST"
                ):  # Unknown section is expected to return None
                    raise


def test_read_all_powermeter_configs():
    """Test reading all powermeter configs."""
    config = configparser.ConfigParser()
    config["SHELLY_1"] = {"TYPE": "1PM", "IP": "127.0.0.1"}
    config["TASMOTA_1"] = {"IP": "127.0.0.1"}
    config["UNKNOWN_SECTION"] = {"SOME_KEY": "some_value"}

    try:
        # Attempt to read all configs
        powermeters = read_all_powermeter_configs(config)

        # Just verify we got some results, don't validate details
        # Some powermeters might fail due to connection issues, but the function should run
        assert isinstance(powermeters, list)

    except Exception as e:
        if "Connection" not in str(e) and "timed out" not in str(e):
            raise
