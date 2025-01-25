import configparser
import argparse
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from config.config_loader import create_powermeter
from ct001 import CT001
from shelly import Shelly


def test_powermeter(powermeter):
    try:
        print("Testing powermeter configuration...")
        powermeter.wait_for_message(timeout=120)
        value = powermeter.get_powermeter_watts()
        value_with_units = " | ".join([f"{v}W" for v in value])
        print(f"Successfully fetched powermeter value: {value_with_units}")
    except Exception as e:
        print(f"Error: {e}")
        exit(1)


def run_device(device_type: str, cfg: configparser.ConfigParser, args: argparse.Namespace,
               powermeter, device_id: Optional[str] = None):
    print(f"Starting device: {device_type}")

    if device_type == "ct001":
        disable_sum = (args.disable_sum if args.disable_sum is not None
                       else cfg.getboolean("GENERAL", "DISABLE_SUM_PHASES", fallback=False))
        disable_absolute = (args.disable_absolute if args.disable_absolute is not None
                            else cfg.getboolean("GENERAL", "DISABLE_ABSOLUTE_VALUES", fallback=False))
        poll_interval = (args.poll_interval if args.poll_interval is not None
                         else cfg.getint("GENERAL", "POLL_INTERVAL", fallback=1))

        print(f"CT001 Settings for {device_id}:")
        print(f"Disable Sum Phases: {disable_sum}")
        print(f"Disable Absolute Values: {disable_absolute}")
        print(f"Poll Interval: {poll_interval}")

        device = CT001(poll_interval=poll_interval)

        def update_readings(addr):
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

    elif device_type == "shellypro3em":
        print(f"Shelly Pro 3EM Settings:")
        print(f"Device ID: {device_id}")
        device = Shelly(powermeter=powermeter, device_id=device_id, udp_port=1010)

    elif device_type == "shellyemg3":
        print(f"Shelly EM Gen3 Settings:")
        print(f"Device ID: {device_id}")
        device = Shelly(powermeter=powermeter, device_id=device_id, udp_port=2222)

    elif device_type == "shellyproem50":
        print(f"Shelly Pro EM 50 Settings:")
        print(f"Device ID: {device_id}")
        device = Shelly(powermeter=powermeter, device_id=device_id, udp_port=2223)

    else:
        raise ValueError(f"Unsupported device type: {device_type}")

    try:
        device.start()
        device.join()
    finally:
        device.stop()


def main():
    parser = argparse.ArgumentParser(description="Power meter device emulator")
    parser.add_argument("-c", "--config", default="config.ini", help="Path to the configuration file")
    parser.add_argument("-t", "--skip-powermeter-test", type=bool)
    parser.add_argument("-d", "--device-types", nargs="+",
                        choices=["ct001", "shellypro3em", "shellyemg3", "shellyproem50"],
                        help="List of device types to emulate")
    parser.add_argument("--device-ids", nargs="+", help="List of device IDs")

    # B2500-specific arguments
    parser.add_argument("-s", "--disable-sum", type=bool)
    parser.add_argument("-a", "--disable-absolute", type=bool)
    parser.add_argument("-p", "--poll-interval", type=int)

    args = parser.parse_args()
    cfg = configparser.ConfigParser()
    cfg.read(args.config)

    # Load general settings
    device_types = (args.device_types if args.device_types is not None
                    else [dt.strip() for dt in cfg.get("GENERAL", "DEVICE_TYPE",
                         fallback="ct001").split(",")])
    skip_test = (args.skip_powermeter_test if args.skip_powermeter_test is not None
                 else cfg.getboolean("GENERAL", "SKIP_POWERMETER_TEST", fallback=False))

    device_ids = args.device_ids if args.device_ids is not None else []
    # Fill missing device IDs with default format
    while len(device_ids) < len(device_types):
        device_type = device_types[len(device_ids)]
        if device_type in ["shellypro3em", "shellyemg3", "shellyproem50"]:
            device_ids.append(f"{device_type}-ec4609c439c{len(device_ids) + 1}")
        else:
            device_ids.append(f"device-{len(device_ids) + 1}")

    print(f"Device Types: {device_types}")
    print(f"Device IDs: {device_ids}")
    print(f"Skip Test: {skip_test}")

    # Create powermeter
    powermeter = create_powermeter(cfg)
    if not skip_test:
        test_powermeter(powermeter)

    # Run devices in parallel
    with ThreadPoolExecutor(max_workers=len(device_types)) as executor:
        futures = []
        for device_type, device_id in zip(device_types, device_ids):
            futures.append(executor.submit(run_device, device_type, cfg, args, powermeter, device_id))

        # Wait for all devices to complete
        for future in futures:
            future.result()


if __name__ == "__main__":
    main()