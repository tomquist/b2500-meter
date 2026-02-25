# B2500 Meter

This project emulates Smart Meter devices for Marstek storage systems such as the B2500, Marstek Jupiter, and Marstek Venus energy storage systems while allowing integration with almost any smart meter. It does this by emulating one or more of the following devices:
- CT001
- CT002 / CT003
- Shelly Pro 3EM
  - Uses port 1010 (B2500 firmware up to version 224) and port 2220 (B2500 firmware version 226+)
  - Can be specifically targeted with shellypro3em_old (port 1010) or shellypro3em_new (port 2220)
- Shelly EM gen3
- Shelly Pro EM50

**Note:** If your B2500 or Marstek storage system supports it, always prefer a Shelly device type over CT001 for better compatibility and reliability.

## Getting Started

The B2500 Meter project can be installed and run in several ways depending on your needs and environment:

1. **Home Assistant Add-on** (Recommended for Home Assistant users)
   - Easiest installation method if you're using Home Assistant
   - Provides a user-friendly interface for configuration
   - Integrates seamlessly with your Home Assistant installation

2. **Docker** (Recommended for standalone server deployment)
   - Containerized solution that works on any Docker-compatible system
   - Easy deployment and updates
   - Consistent environment across different platforms

3. **Direct Installation** (For development or custom setups)
   - Manual installation on Windows, macOS, or Linux
   - Requires Python environment setup
   - More flexible for customization and development

### Home Assistant Add-on Installation

1. **Add the Repository to Home Assistant**

   [![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Ftomquist%2Fb2500-meter)

3. **Install the Add-on**
   - Click on "Add-on Store" in the bottom right corner
   - The B2500 Meter add-on should appear in the add-on store
   - Click on it and then click "Install"

4. **Configure the Add-on**
   You can configure the add-on in two ways:

   A) Using the Add-on Configuration Interface:
   - After installation, go to the add-on's Configuration tab
   - For single-phase monitoring:
     - Set the `Power Input Entity ID` and optionally the `Power Output Entity ID` to the entity IDs of your power sensors
   - For three-phase monitoring:
     - Set the `Power Input Entity ID` to a comma-separated list of three entity IDs (one for each phase)
     - If using calculated power, also set the `Power Output Entity ID` to a comma-separated list of three entity IDs
     - Example: `sensor.phase1,sensor.phase2,sensor.phase3`
   - Set `Device Types` (comma-separated list) to the device types you want to emulate:
     - `ct001`: CT001 emulator
     - `ct002`: CT002 emulator (Marstek CT002 protocol)
     - `ct003`: CT003 emulator (same protocol as CT002)
     - `shellypro3em`: Shelly Pro 3EM emulator (uses both ports 1010 and 2220 for compatibility with all B2500 firmware versions)
     - `shellypro3em_old`: Shelly Pro 3EM emulator using port 1010 (for B2500 firmware up to v224)
     - `shellypro3em_new`: Shelly Pro 3EM emulator using port 2220 (for B2500 firmware v226+)
     - `shellyemg3`: Shelly EM gen3 emulator
     - `shellyproem50`: Shelly Pro EM50 emulator
     
     **Important:** Always prefer a Shelly device type over CT001 if supported by your energy storage system.
   - Click "Save" to apply the configuration

   B) Using a Custom Configuration File for Advanced Configuration:
   - Create a `config.ini` file based on the examples in the [Configuration](#configuration) section
   - Place the file in `/addon_configs/a0ef98c5_b2500_meter/`. You can do that via "File editor" Addon in Home Assistant. Make sure to disable the "Enforce Basepath" setting in the File editor Addon config to access the `/addon_configs` folder.
   - In the add-on configuration, set `Custom Config` to the filename (e.g., "config.ini" without the path)
   - When using a custom configuration file, other configuration options will be ignored

5. **Start the Add-on**
   - Go to the add-on's Info tab
   - Click "Start" to run the add-on

### Docker Installation

#### Prerequisites
- Docker installed on your system
- Docker Compose (optional, but recommended)

#### Installation Steps
1. Create a directory for the project
2. Create your `config.ini` file
3. Use the provided `docker-compose.yaml` to start the container:
   ```bash
   docker-compose up -d
   ```
   You can control the verbosity by setting the `LOG_LEVEL` environment
   variable (for example `-e LOG_LEVEL=debug`). If not set the container
   defaults to `info`.
Note: Host network mode is required because the B2500 device uses UDP broadcasts for device discovery. Without host networking, the container won't be able to receive these broadcasts properly.

### Direct Installation

#### Prerequisites

1. **Python Installation:** Make sure you have Python 3.8 or higher installed. You can download it from the [official Python website](https://www.python.org/downloads/).
2. **Configuration:** Create a `config.ini` file in the root directory of the project and add the appropriate configuration as described in the [Configuration](#configuration) section.

#### Installation Steps

1. **Open Terminal/Command Prompt**
   - Windows: Press `Win + R`, type `cmd`, press Enter
   - macOS: Press `Cmd + Space`, type `Terminal`, press Enter
   - Linux: Use your preferred terminal emulator

2. **Navigate to Project Directory**
   ```bash
   cd path/to/b2500-meter
   ```

3. **Install Dependencies**
   ```bash
   pipenv install
   ```

4. **Run the Script**
   ```bash
   pipenv run python main.py
   ```

All commands above work across Windows, macOS, and Linux. The only difference is how you open your terminal.

## Additional Notes

When the script is running, switch your B2500 to "Self-Adaptation" mode to enable the powermeter functionality.

For details on the CT002/CT003 UDP protocol used by Marstek storage systems, see [docs/ct002-ct003-protocol.md](docs/ct002-ct003-protocol.md).

## Configuration

Configuration is managed via `config.ini`. Each powermeter type has specific settings.

### General Configuration

```ini
[GENERAL]
# Comma-separated list of device types to emulate (ct001, ct002, ct003, shellypro3em, shellyemg3, shellyproem50, shellypro3em_old, shellypro3em_new)
DEVICE_TYPE = ct001
# Optional: comma-separated device IDs, same order as DEVICE_TYPE (auto-generated if omitted). Use for stable IDs across reinstalls or to match an existing device.
#DEVICE_IDS = shellypro3em-c59b15461a21
# Skip initial powermeter test on startup
SKIP_POWERMETER_TEST = False
# Sum power values of all phases and report on phase 1 (ct001/ct002/ct003 only and default is False)
DISABLE_SUM_PHASES = False
# Send absolute values (necessary for storage system) (ct001 only and default is False)
DISABLE_ABSOLUTE_VALUES = False
# Interval for sending power values in seconds (ct001 only and default is 1)
POLL_INTERVAL = 1
# Global throttling interval in seconds to prevent control instability or oscillation
# Set to 0 to disable throttling (default). Recommended: 1-3 seconds for slow data sources
# Can be overridden per powermeter section
THROTTLE_INTERVAL = 0
```

### CT002 / CT003

```ini
[CT002]
# CT type: HME-4 (CT002) or HME-3 (CT003)
CT_TYPE = HME-4
# CT MAC (12 hex digits, from Marstek app). If empty and ALLOW_ANY_CT_MAC=true,
# the emulator accepts any CT MAC and echoes the request’s CT MAC in responses.
# If set, the emulator will respond only to the configured MAC (optionally also
# 000000000000 when permissive).
CT_MAC = 001122334455
# Allow any CT MAC (permissive mode). Set to False to strictly require CT_MAC.
ALLOW_ANY_CT_MAC = True
# UDP port to bind for CT002/CT003 (default 12345).
UDP_PORT = 12345
# WiFi RSSI reported to the storage system
WIFI_RSSI = -50
# Info index reported to the storage system
INFO_IDX = 0
# Ignore repeated requests from the same client within this window (seconds)
DEDUPE_TIME_WINDOW = 10
# Forget consumers after this many seconds without updates (multi-consumer support)
CONSUMER_TTL = 120
```

Optional Marstek cloud auto-registration:
- **MARSTEK.ENABLE** — auto-create/check managed fake CT device(s) at startup
- **MARSTEK.MAILBOX / PASSWORD** — credentials used to call Marstek API
- For `ct002` a managed `HME-4` device is ensured, for `ct003` a managed `HME-3` device.
- Device fields created by b2500-meter:
  - `devid == mac` (random lowercase hex)
  - `bluetooth_name = MST-SMR_<last4(mac)>`
  - `name = B2500-Meter CT002` / `B2500-Meter CT003`
- If a matching managed device of expected type already exists, no new device is created.

### Value Transformation

You can optionally apply a linear transformation to the power values returned by any powermeter. This is useful for calibrating readings (e.g., correcting a consistent offset) or scaling values (e.g., adjusting for a CT clamp ratio).

The formula applied to each value is: `value * POWER_MULTIPLIER + POWER_OFFSET`

For example, if your meter reads 1050W and you set `POWER_MULTIPLIER=0.95` and `POWER_OFFSET=-50`, the result is `1050 * 0.95 + (-50) = 947.5W`.

Both settings are optional and can be added to any powermeter section:
- `POWER_MULTIPLIER` — Scales each power value. Default: 1 (no scaling).
- `POWER_OFFSET` — Added to each power value after the multiplier is applied. Default: 0 (no offset).

For three-phase meters, you can specify a single value (applied to all phases) or comma-separated values (one per phase):

```ini
# Single value — applies to all phases
[SHELLY_1]
TYPE = 1PM
IP = 192.168.1.100
POWER_OFFSET = -50
POWER_MULTIPLIER = 1.05

# Per-phase values — if the list length does not match the device phase count,
# values are applied cyclically and a runtime warning is emitted
[SHELLY_2]
TYPE = 3EMPro
IP = 192.168.1.101
POWER_OFFSET = -50,-30,-40
POWER_MULTIPLIER = 1.05,1.02,1.03

# Flip the sign of all readings (e.g. when import/export polarity is reversed)
[SHELLY_3]
TYPE = 1PM
IP = 192.168.1.102
POWER_MULTIPLIER = -1

# Null a single phase on a three-phase meter
[SHELLY_4]
TYPE = 3EMPro
IP = 192.168.1.103
POWER_MULTIPLIER = 1,0,1
```

**Note:** Transforms are applied before CT001's sum/absolute value operations.

### Shelly

#### Shelly 1PM
```ini
[SHELLY]
TYPE = 1PM
IP = 192.168.1.100
USER = username
PASS = password
METER_INDEX = meter1
```

#### Shelly Plus 1PM
```ini
[SHELLY]
TYPE = PLUS1PM
IP = 192.168.1.100
USER = username
PASS = password
METER_INDEX = meter1
```

#### Shelly EM
```ini
[SHELLY]
TYPE = EM
IP = 192.168.1.100
USER = username
PASS = password
METER_INDEX = meter1
```

#### Shelly 3EM
```ini
[SHELLY]
TYPE = 3EM
IP = 192.168.1.100
USER = username
PASS = password
METER_INDEX = meter1
```

#### Shelly 3EM Pro
```ini
[SHELLY]
TYPE = 3EMPro
IP = 192.168.1.100
USER = username
PASS = password
METER_INDEX = meter1
```

### Tasmota

```ini
[TASMOTA]
IP = 192.168.1.101
USER = tasmota_user
PASS = tasmota_pass
JSON_STATUS = StatusSNS
JSON_PAYLOAD_MQTT_PREFIX = SML
JSON_POWER_MQTT_LABEL = Power
JSON_POWER_INPUT_MQTT_LABEL = Power1
JSON_POWER_OUTPUT_MQTT_LABEL = Power2
JSON_POWER_CALCULATE = True
```

### Shrdzm

```ini
[SHRDZM]
IP = 192.168.1.102
USER = shrdzm_user
PASS = shrdzm_pass
```

### Emlog

```ini
[EMLOG]
IP = 192.168.1.103
METER_INDEX = 0
JSON_POWER_CALCULATE = True
```

### IoBroker

```ini
[IOBROKER]
IP = 192.168.1.104
PORT = 8087
CURRENT_POWER_ALIAS = Alias.0.power
POWER_CALCULATE = True
POWER_INPUT_ALIAS = Alias.0.power_in
POWER_OUTPUT_ALIAS = Alias.0.power_out
```

### HomeAssistant
```ini
[HOMEASSISTANT]
IP = 192.168.1.105
PORT = 8123
# Use HTTPS - if empty False is Fallback
HTTPS = ""|True|False
ACCESSTOKEN = YOUR_ACCESS_TOKEN
# The entity or entities (comma-separated for 3-phase) that provide current power
CURRENT_POWER_ENTITY = ""|sensor.current_power|sensor.phase1,sensor.phase2,sensor.phase3
# If False or Empty the power is not calculated - if empty False is Fallback
POWER_CALCULATE = ""|True|False 
# The entity ID or IDs (comma-separated for 3-phase) that provide power input
POWER_INPUT_ALIAS = ""|sensor.power_input|sensor.power_in_1,sensor.power_in_2,sensor.power_in_3
# The entity ID or IDs (comma-separated for 3-phase) that provide power output
POWER_OUTPUT_ALIAS = ""|sensor.power_output|sensor.power_out_1,sensor.power_out_2,sensor.power_out_3
# Is a Path Prefix needed?
API_PATH_PREFIX = ""|/core
# Per-powermeter throttling override (recommended: 2-3 seconds for HomeAssistant)
THROTTLE_INTERVAL = 2
```

Example: Variant 1 with a single combined input & output sensor
```ini
[HOMEASSISTANT]
IP = 192.168.1.105
PORT = 8123
HTTPS = True
ACCESSTOKEN = YOUR_ACCESS_TOKEN
CURRENT_POWER_ENTITY = sensor.current_power 
```

Example: Variant 2 with separate input & output sensors
```ini
[HOMEASSISTANT]
IP = 192.168.1.105
PORT = 8123
HTTPS = True
ACCESSTOKEN = YOUR_ACCESS_TOKEN
POWER_CALCULATE = True
POWER_INPUT_ALIAS = sensor.power_input
POWER_OUTPUT_ALIAS = sensor.power_output
```

Example: Variant 3 with three-phase power monitoring
```ini
[HOMEASSISTANT]
IP = 192.168.1.105
PORT = 8123
HTTPS = True
ACCESSTOKEN = YOUR_ACCESS_TOKEN
CURRENT_POWER_ENTITY = sensor.phase1,sensor.phase2,sensor.phase3
```

Example: Variant 4 with three-phase power calculation
```ini
[HOMEASSISTANT]
IP = 192.168.1.105
PORT = 8123
HTTPS = True
ACCESSTOKEN = YOUR_ACCESS_TOKEN
POWER_CALCULATE = True
POWER_INPUT_ALIAS = sensor.power_in_1,sensor.power_in_2,sensor.power_in_3
POWER_OUTPUT_ALIAS = sensor.power_out_1,sensor.power_out_2,sensor.power_out_3
# Per-powermeter throttling override (recommended: 2-3 seconds for HomeAssistant)
# THROTTLE_INTERVAL = 2
```

### VZLogger

```ini
[VZLOGGER]
IP = 192.168.1.106
PORT = 8080
UUID = your-uuid
```

### ESPHome

```ini
[ESPHOME]
IP = 192.168.1.107
PORT = 6052
DOMAIN = your_domain
ID = your_id
```

### AMIS Reader

```ini
[AMIS_READER]
IP = 192.168.1.108
```

### Modbus TCP

```ini
[MODBUS]
HOST = 192.168.1.100
PORT = 502
UNIT_ID = 1
ADDRESS = 0
COUNT = 1
DATA_TYPE = UINT16
BYTE_ORDER = BIG
WORD_ORDER = BIG
REGISTER_TYPE = HOLDING  # or INPUT
```

### MQTT

```ini
[MQTT]
BROKER = broker.example.com
PORT = 1883
TOPIC = home/powermeter
JSON_PATH = $.path.to.value (Optional for JSON payloads)
USERNAME = mqtt_user (Optional)
PASSWORD = mqtt_pass (Optional)
# Per-powermeter throttling override
# THROTTLE_INTERVAL = 2
```

The `JSON_PATH` option is used to extract the power value from a JSON payload. The path must be a [valid JSONPath expression](https://goessner.net/articles/JsonPath/).
If the payload is a simple integer value, you can omit this option.

### JSON HTTP

```ini
[JSON_HTTP]
URL = http://example.com/api
# Comma separated JSON paths - single path for 1-phase or three for 3-phase
JSON_PATHS = $.power
USERNAME = user (Optional)
PASSWORD = pass (Optional)
# Additional headers separated by ';' using 'Key: Value'
HEADERS = Authorization: Bearer token
```

### TQ Energy Manager

```ini
[TQ_EM]
IP = 192.168.1.100
#PASSWORD = pass
#TIMEOUT = 5.0 (Optional)
```

### HomeWizard

Reads a [HomeWizard](https://www.homewizard.com/) P1 dongle (or compatible device) over the local **WebSocket** API (`wss://`). Obtain a token once via `POST /api/user` while confirming on the device; see the [HomeWizard API docs](https://api-documentation.homewizard.com/docs/v2/).

```ini
[HOMEWIZARD]
IP = 192.168.1.110
TOKEN = YOUR_32_CHAR_HEX_TOKEN
SERIAL = your_device_serial
# Optional: disable TLS certificate verification on a trusted LAN if verification fails (default True)
# VERIFY_SSL = True
# THROTTLE_INTERVAL = 0
```

### SMA Energy Meter

Reads an [SMA Energy Meter](https://www.sma.de/) (EM 1.0/2.0) or Sunny Home Manager via the **Speedwire** multicast protocol (UDP). The listener joins the default multicast group and reports per-phase active power (L1, L2, L3). Use `SERIAL_NUMBER = 0` to auto-detect the first meter seen on the network, or set the device serial to pin a specific unit. Like other UDP-based features, this requires the host to receive multicast traffic (use Docker host networking or equivalent).

```ini
[SMA_ENERGY_METER]
MULTICAST_GROUP = 239.12.255.254
PORT = 9522
SERIAL_NUMBER = 0
# INTERFACE = 192.168.1.10
# THROTTLE_INTERVAL = 0
```

### Modbus

```ini
[MODBUS]
HOST =
PORT =
UNIT_ID =
ADDRESS =
COUNT =
DATA_TYPE = UINT16
BYTE_ORDER = BIG
WORD_ORDER = BIG
REGISTER_TYPE = HOLDING
```

### Script

You can also use a custom script to get the power values. The script should output at most 3 integer values, separated by a line break.
```ini
[SCRIPT]
COMMAND = /path/to/your/script.sh
```

### SML

```ini
[SML]
SERIAL = /dev/ttyUSB0
# Optional: override default OBIS hex registers (12 hex digits each; defaults match common German eHZ meters)
#OBIS_POWER_CURRENT = 0100100700ff
#OBIS_POWER_L1 = 0100240700ff
#OBIS_POWER_L2 = 0100380700ff
#OBIS_POWER_L3 = 01004c0700ff
```

Read from a powermeter that is connected via USB and that transmits SML (Smart Message Language) data via an IR head. **`SERIAL` is required**: local device path to the serial interface (e.g. `/dev/ttyUSB0` on Linux).

**Multi-phase:** If the meter exposes per-phase instantaneous active power for L1–L3 (`Summenwirkleistung` / default OBIS above), those three values are used automatically. Otherwise the aggregate instantaneous power register (`aktuelle Wirkleistung` / `OBIS_POWER_CURRENT`) is used as a single reading. When both are present in the same SML list, per-phase values take precedence.

**OBIS overrides:** Only needed if your meter uses different register addresses; values must be exactly 12 hexadecimal characters (lowercase or uppercase).

### Multiple Powermeters

You can configure multiple powermeters by adding additional sections with the same prefix (e.g. `[SHELLY<unique_suffix>]`). Each powermeter should specify which client IP addresses are allowed to access it using the NETMASK setting.

When a storage system requests power values, the script will check the client IP address against the NETMASK settings of each powermeter and use the first that matches.

```ini
[SHELLY_1]
TYPE = 1PM
IP = 192.168.1.100
USER = username
PASS = password
NETMASK = 192.168.1.50/32

[SHELLY_2]
TYPE = 3EM
IP = 192.168.1.101
USER = username
PASS = password
# You can specify multiple IPs by separating them with a comma:
NETMASK = 192.168.1.51/32,192.168.1.52/32

[HOMEASSISTANT_1]
IP = 192.168.1.105
PORT = 8123
HTTPS = True
ACCESSTOKEN = YOUR_ACCESS_TOKEN
CURRENT_POWER_ENTITY = sensor.current_power
# No NETMASK specified - will match all clients (0.0.0.0/0)
```

## Node-RED Implementation

This project also provides a Node-RED implementation, allowing integration with various smart meters. The Node-RED flow is available in the `nodered.json` file. Note that the Node-RED implementation only supports emulating a CT001.

### Installation and Setup

1. **Import the Node-RED Flow**
   - Open your Node-RED dashboard.
   - Navigate to the menu in the top right corner, select "Import" and then "Clipboard".
   - Copy the content of `nodered.json` and paste it into the import dialog, then click "Import".

2. **Hooking Powermeter Readings**
   - Ensure your powermeter readings are available as a Node-RED message with the power values in the payload.
   - Connect the output of your powermeter reading nodes to the input node of the subflow named "B2500". The subflow can handle:
     - An array of 3 numbers or strings containing numbers, representing the power values of each phase, e.g. `[100, 200, 300]`.
     - A single number or string containing a number, which will be interpreted as the value for the first phase, with the other two phases set to 0.
   - Ensure that a fresh powermeter reading is sent to the flow every second.

3. **Running the Flow**
   - Deploy the flow by clicking the "Deploy" button on the top right corner of the Node-RED dashboard.
   - The flow will now listen for powermeter readings and handle the UDP and TCP communications as configured.

# Frequently Asked Questions (FAQ)

## General Usage and Setup

### The emulator starts and shows "listening" message but nothing else happens. Is this a problem?

A: No, this is expected behavior. The emulator waits for the storage system to request data and only polls when requested. Without an active request from your Marstek device, you won't see further activity.

### My Marstek device can't find the emulated powermeter. What could be wrong?

A: Common causes include:
- **Firmware issues:** See the firmware requirements in the Device section below
- **Network setup:** Ensure both devices are on the same subnet (255.255.255.0)
- **Bluetooth interference:** Disconnect any Bluetooth connections during setup
- **Docker configuration:** When using Docker, set `network_mode: host` to enable UDP broadcast reception

### The emulator isn't visible in the Shelly app or network scanners. Is this normal?

A: Yes. The emulator only implements the minimal protocol needed for Marstek storage systems and is not a complete Shelly device emulation.

### How do I autostart the script on boot?

A: Use systemd to create a service:
1. Create a unit file (e.g., `/etc/systemd/system/b2500-meter.service`)
2. Set `ExecStart` to your startup command
3. Enable and start: `sudo systemctl enable b2500-meter && sudo systemctl start b2500-meter`

### Can I run multiple instances for different storage devices?

A: Yes. Define multiple sections in `config.ini` (e.g., `[SHELLY_1]`, `[SHELLY_2]`) and use the `NETMASK` setting to assign each to specific client IPs.

## Configuration & Integration

### What's the correct power value convention?

A: Power from grid to house (import): **positive**  
Power from house to grid (export): **negative**

### How do I convert kW values to the required W?

A: Create a template sensor in Home Assistant:
```jinja
{{ states('sensor.power_in_kilowatts') | float * 1000 }}
```

### How do I set up three-phase measurement in the Home Assistant Addon?

A: Use comma-separated entity IDs:
```
sensor.phase1,sensor.phase2,sensor.phase3
```

### What's the difference between the power entity settings?

A: 
- `CURRENT_POWER_ENTITY`: For a single bidirectional sensor (positive/negative values)
  - `POWER_INPUT_ALIAS`/`POWER_OUTPUT_ALIAS`: Entity IDs for separate import/export sensors (with `POWER_CALCULATE = True`)

## Device and Firmware Specific

### What firmware do I need for my Marstek device?

A:
- **Venus:** Firmware 120+ for Shelly support, 152+ for improved regulation
- **B2500:** Firmware 108+ (HMJ devices) or 224+ (all others)

### How do I handle the different ports for Shelly Pro 3EM?

A: Use one of these device types:
- `shellypro3em_old`: Port 1010 (B2500 firmware ≤224 or Jupiter & Venus)
- `shellypro3em_new`: Port 2220 (B2500 firmware ≥226)
- `shellypro3em`: Both ports (most compatible)

### Can I use this with non-Marstek storage systems (e.g., Zendure, Hoymiles)?

A: No, this project is Marstek-specific. For other brands, see [uni-meter](https://github.com/sdeigm/uni-meter).

## Troubleshooting

### I get permission errors when binding to port 1010/2220.

A: Ports below 1024 require root privileges on Linux. Solutions:
- Use Docker or Home Assistant Add-on (recommended)
- Use `setcap` to grant permissions
- Run as root (not recommended)

### I get parsing errors on startup or the add-on crashes.

A: Common causes:
- Incorrect entity IDs or API access
- Memory limitations (especially on RPi 2 or similar devices)
- Check logs for specific error messages

### How can I test without a storage device?

A: You can only verify the initial configuration. Full testing requires a Marstek device in "self-adaptation" mode to request data.

## Advanced

### How do I handle negative values for CT001?

A: The CT001 protocol can't handle negative values on some firmware versions. By default, the emulator sends absolute values or clamps negatives to zero, adjustable via `DISABLE_ABSOLUTE_VALUES`.

## License

This project is licensed under the General Public License v3.0 - see the [LICENSE](LICENSE) file for details.
