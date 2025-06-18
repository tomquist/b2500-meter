import configparser
import argparse
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from config.config_loader import read_all_powermeter_configs, ClientFilter
from ct001 import CT001
from powermeter import Powermeter
from shelly import Shelly
from collections import OrderedDict
from config.logger import logger, setLogLevel


def test_powermeter(powermeter: Powermeter, client_filter: ClientFilter):
    try:
        logger.debug("Testing powermeter configuration...")
        powermeter.wait_for_message(timeout=120)
        value = powermeter.get_powermeter_watts()
        value_with_units = " | ".join([f"{v}W" for v in value])
        powermeter_name = powermeter.__class__.__name__
        filter_description = ", ".join([str(n) for n in client_filter.netmasks])
        logger.debug(
            f"Successfully fetched {powermeter_name} powermeter value (filter {filter_description}): {value_with_units}"
        )
    except Exception as e:
        logger.debug(f"Error: {e}")
        exit(1)


def run_device(
    device_type: str,
    cfg: configparser.ConfigParser,
    args: argparse.Namespace,
    powermeters: list[(Powermeter, ClientFilter)],
    device_id: Optional[str] = None,
):
    logger.debug(f"Starting device: {device_type}")

    if device_type == "ct001":
        disable_sum = (
            args.disable_sum
            if args.disable_sum is not None
            else cfg.getboolean("GENERAL", "DISABLE_SUM_PHASES", fallback=False)
        )
        disable_absolute = (
            args.disable_absolute
            if args.disable_absolute is not None
            else cfg.getboolean("GENERAL", "DISABLE_ABSOLUTE_VALUES", fallback=False)
        )
        poll_interval = (
            args.poll_interval
            if args.poll_interval is not None
            else cfg.getint("GENERAL", "POLL_INTERVAL", fallback=1)
        )

        logger.debug(f"CT001 Settings for {device_id}:")
        logger.debug(f"Disable Sum Phases: {disable_sum}")
        logger.debug(f"Disable Absolute Values: {disable_absolute}")
        logger.debug(f"Poll Interval: {poll_interval}")

        device = CT001(poll_interval=poll_interval)

        def update_readings(addr):
            powermeter = None
            for pm, client_filter in powermeters:
                if client_filter.matches(addr[0]):
                    powermeter = pm
                    break
            if powermeter is None:
                logger.debug(f"No powermeter found for client {addr[0]}")
                device.value = None
                return
            values = powermeter.get_powermeter_watts()
            value1 = values[0] if len(values) > 0 else 0
            value2 = values[1] if len(values) > 1 else 0
            value3 = values[2] if len(values) > 2 else 0

            if not disable_sum:
                value1 = value1 + value2 + value3
                value2 = value3 = 0

            if not disable_absolute:
                value1, value2, value3 = map(abs, (value1, value2, value3))

            device.value = [value1, value2, value3]

        device.before_send = update_readings

    elif device_type == "shellypro3em_old":
        logger.debug(f"Shelly Pro 3EM Settings:")
        logger.debug(f"Device ID: {device_id}")
        device = Shelly(powermeters=powermeters, device_id=device_id, udp_port=1010)

    elif device_type == "shellypro3em_new":
        logger.debug(f"Shelly Pro 3EM Settings:")
        logger.debug(f"Device ID: {device_id}")
        device = Shelly(powermeters=powermeters, device_id=device_id, udp_port=2220)

    elif device_type == "shellyemg3":
        logger.debug(f"Shelly EM Gen3 Settings:")
        logger.debug(f"Device ID: {device_id}")
        device = Shelly(powermeters=powermeters, device_id=device_id, udp_port=2222)

    elif device_type == "shellyproem50":
        logger.debug(f"Shelly Pro EM 50 Settings:")
        logger.debug(f"Device ID: {device_id}")
        device = Shelly(powermeters=powermeters, device_id=device_id, udp_port=2223)

    else:
        raise ValueError(f"Unsupported device type: {device_type}")

    try:
        device.start()
        device.join()
    finally:
        device.stop()


def main():
    parser = argparse.ArgumentParser(description="Power meter device emulator")
    parser.add_argument(
        "-c", "--config", default="config.ini", help="Path to the configuration file"
    )
    parser.add_argument("-t", "--skip-powermeter-test", action="store_true", default=None)
    parser.add_argument(
        "-d",
        "--device-types",
        nargs="+",
        choices=[
            "ct001",
            "shellypro3em",
            "shellyemg3",
            "shellyproem50",
            "shellypro3em_old",
            "shellypro3em_new",
        ],
        help="List of device types to emulate",
    )
    parser.add_argument("--device-ids", nargs="+", help="List of device IDs")
    parser.add_argument(
        "-log",
        "--loglevel",
        default="warning",
        help="Provide logging level. Example --loglevel debug, default=warning",
    )

    # B2500-specific arguments
    parser.add_argument("-s", "--disable-sum", action="store_true", default=None)
    parser.add_argument("-a", "--disable-absolute", action="store_true", default=None)
    parser.add_argument("-p", "--poll-interval", type=int)
    parser.add_argument(
        "--throttle-interval",
        type=float,
        help="Throttling interval in seconds to prevent B2500 control instability",
    )

    args = parser.parse_args()
    cfg = configparser.ConfigParser(dict_type=OrderedDict)
    cfg.read(args.config)

    # configure logger
    setLogLevel(args.loglevel)
    logger.info("startet b2500-meter application")

    # Load general settings
    device_types = (
        args.device_types
        if args.device_types is not None
        else [
            dt.strip()
            for dt in cfg.get("GENERAL", "DEVICE_TYPE", fallback="ct001").split(",")
        ]
    )
    skip_test = (
        args.skip_powermeter_test
        if args.skip_powermeter_test is not None
        else cfg.getboolean("GENERAL", "SKIP_POWERMETER_TEST", fallback=False)
    )

    device_ids = args.device_ids if args.device_ids is not None else []
    # Fill missing device IDs with default format
    while len(device_ids) < len(device_types):
        device_type = device_types[len(device_ids)]
        if device_type in ["shellypro3em", "shellyemg3", "shellyproem50"]:
            device_ids.append(f"{device_type}-ec4609c439c{len(device_ids) + 1}")
        else:
            device_ids.append(f"device-{len(device_ids) + 1}")

    # For backward compatibility, replace shellypro3em with shellypro3em_old and shellypro3em_new
    if "shellypro3em" in device_types:
        shellypro3em_index = device_types.index("shellypro3em")
        device_types[shellypro3em_index] = "shellypro3em_old"
        device_types.append("shellypro3em_new")
        device_ids.append(device_ids[shellypro3em_index])

    logger.info(f"Device Types: {device_types}")
    logger.info(f"Device IDs: {device_ids}")
    logger.info(f"Skip Test: {skip_test}")

    # Apply command line throttling override if specified
    if args.throttle_interval is not None:
        if not cfg.has_section("GENERAL"):
            cfg.add_section("GENERAL")
        cfg.set("GENERAL", "THROTTLE_INTERVAL", str(args.throttle_interval))

    # Create powermeter
    powermeters = read_all_powermeter_configs(cfg)
    if not skip_test:
        for powermeter, client_filter in powermeters:
            test_powermeter(powermeter, client_filter)

    # Run devices in parallel
    with ThreadPoolExecutor(max_workers=len(device_types)) as executor:
        futures = []
        for device_type, device_id in zip(device_types, device_ids):
            futures.append(
                executor.submit(
                    run_device, device_type, cfg, args, powermeters, device_id
                )
            )
        # end for

        # Wait for all devices to complete
        for future in futures:
            future.result()


# end main

if __name__ == "__main__":
    main()
