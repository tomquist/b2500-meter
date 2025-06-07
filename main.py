import configparser
import argparse
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from config.config_loader import read_all_powermeter_configs, ClientFilter
from ct001 import CT001
from powermeter import Powermeter
from shelly import Shelly
from collections import OrderedDict
from ct002 import CTEmulator


def test_powermeter(powermeter, client_filter):
    try:
        print("Testing powermeter configuration...")
        powermeter.wait_for_message(timeout=120)
        value = powermeter.get_powermeter_watts()
        value_with_units = " | ".join([f"{v}W" for v in value])
        powermeter_name = powermeter.__class__.__name__
        filter_description = ", ".join([str(n) for n in client_filter.netmasks])
        print(
            f"Successfully fetched {powermeter_name} powermeter value (filter {filter_description}): {value_with_units}"
        )
    except Exception as e:
        print(f"Error: {e}")
        exit(1)


def run_device(
    device_type: str,
    cfg: configparser.ConfigParser,
    args: argparse.Namespace,
    powermeters: list[(Powermeter, ClientFilter)],
    device_id: Optional[str] = None,
):
    print(f"Starting device: {device_type}")

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

        print(f"CT001 Settings for {device_id}:")
        print(f"Disable Sum Phases: {disable_sum}")
        print(f"Disable Absolute Values: {disable_absolute}")
        print(f"Poll Interval: {poll_interval}")

        device = CT001(poll_interval=poll_interval)

        def update_readings(addr):
            powermeter = None
            for pm, client_filter in powermeters:
                if client_filter.matches(addr[0]):
                    powermeter = pm
                    break
            if powermeter is None:
                print(f"No powermeter found for client {addr[0]}")
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

    elif device_type == "ct002":
        # CT002-specific config (can be extended to use config/args)
        device_type_str = cfg.get("GENERAL", "CT002_DEVICE_TYPE", fallback="HMG-50")
        battery_mac = cfg.get("GENERAL", "CT002_BATTERY_MAC", fallback="001122334455")
        ct_mac = cfg.get("GENERAL", "CT002_CT_MAC", fallback="009c17abcdef")
        ct_type = cfg.get("GENERAL", "CT002_CT_TYPE", fallback="HME-4")
        poll_interval = (
            args.poll_interval
            if args.poll_interval is not None
            else cfg.getint("GENERAL", "POLL_INTERVAL", fallback=1)
        )
        print(f"CT002 Settings for {device_id}:")
        print(f"Device Type: {device_type_str}")
        print(f"Battery MAC: {battery_mac}")
        print(f"CT MAC: {ct_mac}")
        print(f"CT Type: {ct_type}")
        print(f"Poll Interval: {poll_interval}")
        device = CTEmulator(
            device_type=device_type_str,
            battery_mac=battery_mac,
            ct_mac=ct_mac,
            ct_type=ct_type,
            poll_interval=poll_interval,
        )
        def update_readings(addr):
            powermeter = None
            for pm, client_filter in powermeters:
                if client_filter.matches(addr[0]):
                    powermeter = pm
                    break
            if powermeter is None:
                print(f"No powermeter found for client {addr[0]}")
                device.value = None
                return
            values = powermeter.get_powermeter_watts()
            value1 = values[0] if len(values) > 0 else 0
            value2 = values[1] if len(values) > 1 else 0
            value3 = values[2] if len(values) > 2 else 0
            device.value = [value1, value2, value3]
        device.before_send = update_readings

    elif device_type == "shellypro3em_old":
        print(f"Shelly Pro 3EM Settings:")
        print(f"Device ID: {device_id}")
        device = Shelly(powermeters=powermeters, device_id=device_id, udp_port=1010)

    elif device_type == "shellypro3em_new":
        print(f"Shelly Pro 3EM Settings:")
        print(f"Device ID: {device_id}")
        device = Shelly(powermeters=powermeters, device_id=device_id, udp_port=2220)

    elif device_type == "shellyemg3":
        print(f"Shelly EM Gen3 Settings:")
        print(f"Device ID: {device_id}")
        device = Shelly(powermeters=powermeters, device_id=device_id, udp_port=2222)

    elif device_type == "shellyproem50":
        print(f"Shelly Pro EM 50 Settings:")
        print(f"Device ID: {device_id}")
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
    parser.add_argument("-t", "--skip-powermeter-test", type=bool)
    parser.add_argument(
        "-d",
        "--device-types",
        nargs="+",
        choices=[
            "ct001",
            "ct002",
            "shellypro3em",
            "shellyemg3",
            "shellyproem50",
            "shellypro3em_old",
            "shellypro3em_new",
        ],
        help="List of device types to emulate",
    )
    parser.add_argument("--device-ids", nargs="+", help="List of device IDs")

    # B2500-specific arguments
    parser.add_argument("-s", "--disable-sum", type=bool)
    parser.add_argument("-a", "--disable-absolute", type=bool)
    parser.add_argument("-p", "--poll-interval", type=int)

    args = parser.parse_args()
    cfg = configparser.ConfigParser(dict_type=OrderedDict)
    cfg.read(args.config)

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

    print(f"Device Types: {device_types}")
    print(f"Device IDs: {device_ids}")
    print(f"Skip Test: {skip_test}")

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

        # Wait for all devices to complete
        for future in futures:
            future.result()


if __name__ == "__main__":
    main()
