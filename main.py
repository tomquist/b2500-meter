import configparser
import argparse
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, List, Tuple
from config.config_loader import read_all_powermeter_configs, ClientFilter
from ct001 import CT001
from ct002 import CT002, UDP_PORT
from powermeter import Powermeter
from shelly import Shelly
from collections import OrderedDict
from config.logger import logger, setLogLevel
from health_service import start_health_service, stop_health_service
from marstek_api import MarstekConfig, ensure_managed_fake_device, MarstekApiError

# CT002/CT003 phase assignment is auto-managed by emulator runtime.


def get_ct_section(device_type: str, cfg: configparser.ConfigParser) -> str:
    section = "CT002"
    if device_type == "ct003" and cfg.has_section("CT003"):
        section = "CT003"
    return section


def test_powermeter(powermeter: Powermeter, client_filter: ClientFilter):
    """Test powermeter configuration with minimal retry logic for edge cases."""
    max_retries = 3
    retry_delay = 5  # seconds

    for attempt in range(max_retries + 1):
        try:
            logger.debug(
                f"Testing powermeter configuration... (attempt {attempt + 1}/{max_retries + 1})"
            )
            powermeter.wait_for_message(
                timeout=30
            )  # Reduced timeout since HA should be ready
            value = powermeter.get_powermeter_watts()
            value_with_units = " | ".join([f"{v}W" for v in value])
            powermeter_name = powermeter.__class__.__name__
            filter_description = ", ".join([str(n) for n in client_filter.netmasks])
            logger.info(
                f"Successfully fetched {powermeter_name} powermeter value (filter {filter_description}): {value_with_units}"
            )
            return  # Success, exit the function
        except Exception as e:
            logger.debug(f"Error on attempt {attempt + 1}: {e}")

            if attempt < max_retries:
                logger.info(f"Retrying powermeter test in {retry_delay} seconds...")
                time.sleep(retry_delay)
                continue
            else:
                # Last attempt failed
                logger.error(
                    f"Failed to test powermeter after {max_retries + 1} attempts: {e}"
                )
                exit(1)


def run_device(
    device_type: str,
    cfg: configparser.ConfigParser,
    args: argparse.Namespace,
    powermeters: List[Tuple[Powermeter, ClientFilter]],
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

    elif device_type in ["ct002", "ct003"]:
        ct_section = get_ct_section(device_type, cfg)
        ct_type = "HME-4" if device_type == "ct002" else "HME-3"
        ct_mac = cfg.get(ct_section, "CT_MAC", fallback="")
        ct_udp_port = cfg.getint(ct_section, "UDP_PORT", fallback=UDP_PORT)
        wifi_rssi = cfg.getint(ct_section, "WIFI_RSSI", fallback=-50)
        dedupe_time_window = cfg.getint(ct_section, "DEDUPE_TIME_WINDOW", fallback=0)
        consumer_ttl = cfg.getint(ct_section, "CONSUMER_TTL", fallback=120)
        debug_status = cfg.getboolean(ct_section, "DEBUG_STATUS", fallback=False)
        if os.environ.get("DEBUG_STATUS", "").lower() in ("1", "true", "yes"):
            debug_status = True
        active_control = cfg.getboolean(ct_section, "ACTIVE_CONTROL", fallback=True)
        smooth_target_alpha = cfg.getfloat(
            ct_section, "SMOOTH_TARGET_ALPHA", fallback=0.08
        )
        max_smooth_step = cfg.getint(ct_section, "MAX_SMOOTH_STEP", fallback=0)
        fair_distribution = cfg.getboolean(
            ct_section, "FAIR_DISTRIBUTION", fallback=True
        )
        balance_gain = cfg.getfloat(ct_section, "BALANCE_GAIN", fallback=0.2)
        error_boost_threshold = cfg.getint(
            ct_section, "ERROR_BOOST_THRESHOLD", fallback=150
        )
        error_boost_max = cfg.getfloat(ct_section, "ERROR_BOOST_MAX", fallback=0.5)
        error_reduce_threshold = cfg.getint(
            ct_section, "ERROR_REDUCE_THRESHOLD", fallback=20
        )
        balance_deadband = cfg.getint(ct_section, "BALANCE_DEADBAND", fallback=15)
        deadband = cfg.getint(ct_section, "DEADBAND", fallback=20)
        max_correction_per_step = cfg.getint(
            ct_section, "MAX_CORRECTION_PER_STEP", fallback=80
        )
        max_target_step = cfg.getint(ct_section, "MAX_TARGET_STEP", fallback=0)
        saturation_detection = cfg.getboolean(
            ct_section, "SATURATION_DETECTION", fallback=True
        )
        saturation_alpha = cfg.getfloat(ct_section, "SATURATION_ALPHA", fallback=0.15)
        min_target_for_saturation = cfg.getint(
            ct_section, "MIN_TARGET_FOR_SATURATION", fallback=20
        )

        logger.debug(f"{device_type.upper()} Settings for {device_id}:")
        logger.debug(f"CT Type: {ct_type}")
        logger.debug(f"CT MAC: {ct_mac}")
        logger.debug(f"CT UDP Port: {ct_udp_port}")
        logger.debug(f"WiFi RSSI: {wifi_rssi}")
        logger.debug(
            "CT control model: %s",
            (
                "active control (emulator computes targets)"
                if active_control
                else "relay (forward consumer aggregates)"
            ),
        )
        if active_control:
            extras = []
            if fair_distribution:
                extras.append("fair distribution")
            if saturation_detection:
                extras.append("saturation detection")
            logger.info(
                "Active control enabled (alpha=%.2f): smooth target + load split%s",
                smooth_target_alpha,
                " + " + " + ".join(extras) if extras else "",
            )

        device = CT002(
            udp_port=ct_udp_port,
            ct_type=ct_type,
            ct_mac=ct_mac,
            wifi_rssi=wifi_rssi,
            dedupe_time_window=dedupe_time_window,
            consumer_ttl=consumer_ttl,
            debug_status=debug_status,
            active_control=active_control,
            smooth_target_alpha=smooth_target_alpha,
            max_smooth_step=max_smooth_step,
            fair_distribution=fair_distribution,
            balance_gain=balance_gain,
            error_boost_threshold=error_boost_threshold,
            error_boost_max=error_boost_max,
            error_reduce_threshold=error_reduce_threshold,
            balance_deadband=balance_deadband,
            deadband=deadband,
            max_correction_per_step=max_correction_per_step,
            max_target_step=max_target_step,
            saturation_detection=saturation_detection,
            saturation_alpha=saturation_alpha,
            min_target_for_saturation=min_target_for_saturation,
        )

        def update_readings(addr, _fields=None, _consumer_id=None):
            powermeter = None
            for pm, client_filter in powermeters:
                if client_filter.matches(addr[0]):
                    powermeter = pm
                    break
            if powermeter is None:
                logger.debug(f"No powermeter found for client {addr[0]}")
                return None
            values = powermeter.get_powermeter_watts()
            value1 = values[0] if len(values) > 0 else 0
            value2 = values[1] if len(values) > 1 else 0
            value3 = values[2] if len(values) > 2 else 0

            return [value1, value2, value3]

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
    parser.add_argument(
        "-t", "--skip-powermeter-test", action="store_true", default=None
    )
    parser.add_argument(
        "-d",
        "--device-types",
        nargs="+",
        choices=[
            "ct001",
            "ct002",
            "ct003",
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
        default=os.environ.get("LOG_LEVEL", "warning"),
        help="Provide logging level. Example --loglevel debug. Can also be set via LOG_LEVEL env var",
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

    ct_ports = []
    for device_type in device_types:
        if device_type in ["ct002", "ct003"]:
            section = get_ct_section(device_type, cfg)
            ct_ports.append(cfg.getint(section, "UDP_PORT", fallback=UDP_PORT))
    if len(ct_ports) != len(set(ct_ports)):
        raise ValueError(
            "Multiple CT002/CT003 devices are configured with the same UDP port. "
            "Set UDP_PORT in [CT002]/[CT003] to avoid conflicts."
        )

    logger.info(f"Device Types: {device_types}")
    logger.info(f"Device IDs: {device_ids}")
    logger.info(f"Skip Test: {skip_test}")

    # Apply command line throttling override if specified
    if args.throttle_interval is not None:
        if not cfg.has_section("GENERAL"):
            cfg.add_section("GENERAL")
        cfg.set("GENERAL", "THROTTLE_INTERVAL", str(args.throttle_interval))

    # Start health check server for watchdog monitoring
    if cfg.getboolean("GENERAL", "ENABLE_HEALTH_CHECK", fallback=True):
        logger.info("Starting health check service...")
        if start_health_service():
            logger.info("Health check service started successfully")
        else:
            logger.error("Failed to start health check service")

    # Optional Marstek cloud registration for managed fake CT devices
    marstek_enabled = cfg.getboolean("MARSTEK", "ENABLE", fallback=False)
    if marstek_enabled:
        mailbox = cfg.get("MARSTEK", "MAILBOX", fallback="")
        password = cfg.get("MARSTEK", "PASSWORD", fallback="")
        base_url = cfg.get("MARSTEK", "BASE_URL", fallback="https://eu.hamedata.com")
        timezone_name = cfg.get("MARSTEK", "TIMEZONE", fallback="Europe/Berlin")

        if not mailbox or not password:
            logger.warning(
                "MARSTEK.ENABLE is true, but MAILBOX/PASSWORD missing; skipping fake-device auto-registration"
            )
        else:
            marstek_cfg = MarstekConfig(
                base_url=base_url,
                mailbox=mailbox,
                password=password,
                timezone=timezone_name,
            )
            try:
                for dt in ("ct002", "ct003"):
                    if dt in device_types:
                        ensure_managed_fake_device(marstek_cfg, dt)
            except MarstekApiError as exc:
                logger.error("Marstek auto-registration failed: %s", exc)
            except Exception as exc:
                logger.error("Unexpected Marstek auto-registration error: %s", exc)

    runtime_device_types = list(device_types)
    runtime_device_ids = list(device_ids)

    # Create powermeter
    powermeters = read_all_powermeter_configs(cfg)
    if not skip_test:
        for powermeter, client_filter in powermeters:
            test_powermeter(powermeter, client_filter)

    # Run devices in parallel
    try:
        if not runtime_device_types:
            logger.warning("No runnable device types configured after filtering.")
            return

        with ThreadPoolExecutor(max_workers=len(runtime_device_types)) as executor:
            futures = []
            for device_type, device_id in zip(runtime_device_types, runtime_device_ids):
                futures.append(
                    executor.submit(
                        run_device, device_type, cfg, args, powermeters, device_id
                    )
                )
            # end for

            # Wait for all devices to complete
            for future in futures:
                future.result()
    finally:
        # Ensure health service is properly stopped on exit
        logger.info("Stopping health check service...")
        stop_health_service()


# end main

if __name__ == "__main__":
    main()
