import configparser
import argparse
from config.config_loader import create_powermeter
from b2500 import B2500

# Define ports
UDP_PORT = 12345
TCP_PORT = 12345


def test_powermeter(powermeter):
    try:
        print("Testing powermeter configuration...")
        # Wait for the MQTT client to receive the first message
        powermeter.wait_for_message(timeout=120)
        value = powermeter.get_powermeter_watts()
        value_with_units = " | ".join([f"{v}W" for v in value])
        print(f"Successfully fetched powermeter value: {value_with_units}")
    except Exception as e:
        print(f"Error: {e}")
        exit(1)


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Power meter configuration")
    parser.add_argument(
        "-c",
        "--config",
        default="config.ini",
        help="Path to the configuration file",
        type=str,
    )
    parser.add_argument(
        "-s", "--disable-sum", help="Disable sum of all phases", type=bool, default=None
    )
    parser.add_argument(
        "-a",
        "--disable-absolute",
        help="Disable absolute values",
        type=bool,
        default=None,
    )
    parser.add_argument(
        "-t",
        "--skip-powermeter-test",
        help="Skip powermeter test on start",
        type=bool,
        default=None,
    )
    parser.add_argument(
        "-p", "--poll-interval", help="Poll interval in seconds", type=int
    )
    args = parser.parse_args()

    # Load configuration
    cfg = configparser.ConfigParser()
    cfg.read(args.config)
    powermeter = create_powermeter(cfg)
    disable_sum_phases = (
        args.disable_sum
        if args.disable_sum is not None
        else cfg.getboolean("GENERAL", "DISABLE_SUM_PHASES", fallback=False)
    )
    disable_absolut_values = (
        args.disable_absolute
        if args.disable_absolute is not None
        else cfg.getboolean("GENERAL", "DISABLE_ABSOLUTE_VALUES", fallback=False)
    )
    skip_test = (
        args.skip_powermeter_test
        if args.skip_powermeter_test is not None
        else cfg.getboolean("GENERAL", "SKIP_POWERMETER_TEST", fallback=False)
    )
    poll_interval = (
        args.poll_interval
        if args.poll_interval is not None
        else cfg.getint("GENERAL", "POLL_INTERVAL", fallback=1)
    )

    print(f"General Settings:")
    print(f"Disable Sum Phases: {disable_sum_phases}")
    print(f"Disable Absolute Values: {disable_absolut_values}")
    print(f"Skip Test: {skip_test}")
    print(f"Poll Interval: {poll_interval}")

    # Fetch powermeter values once to check if the configuration is correct
    if not skip_test:
        test_powermeter(powermeter)

    smart_meter = B2500(poll_interval=poll_interval)

    try:
        listen(smart_meter, powermeter, disable_sum_phases, disable_absolut_values)
    finally:
        smart_meter.stop()


def listen(smart_meter, powermeter, disable_sum_phases, disable_absolut_values):
    def update_readings(addr):
        values = powermeter.get_powermeter_watts()
        value1 = values[0] if len(values) > 0 else 0
        value2 = values[1] if len(values) > 1 else 0
        value3 = values[2] if len(values) > 2 else 0
        if not disable_sum_phases:
            value1 = value1 + value2 + value3
            value2 = 0
            value3 = 0

        if not disable_absolut_values:
            value1 = abs(value1)
            value2 = abs(value2)
            value3 = abs(value3)

        smart_meter.value = [value1, value2, value3]

    smart_meter.before_send = update_readings
    smart_meter.start()
    smart_meter.join()


if __name__ == "__main__":
    main()
