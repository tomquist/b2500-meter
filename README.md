# B2500 Meter

This project emulates Smart Meter devices for Marstek storages such as the B2500, Marstek Jupiter and Marstek Venus energy storage system while allowing integration with almost any smart meters.

## Getting Started

### Prerequisites

1. **Python Installation:** Make sure you have Python 3.7 or higher installed. You can download it from the [official Python website](https://www.python.org/downloads/).

2. **Configuration:** Create a `config.ini` file in the root directory of the project and add the appropriate configuration as described in the [Configuration](#configuration) section.

### Windows

1. **Open Command Prompt**
   - Press `Win + R`, type `cmd`, and hit Enter.

2. **Navigate to the Project Directory**
   ```cmd
   cd path\to\b2500-meter
   ```

3. **Install Dependencies**
   ```cmd
   pipenv install
   ```

4. **Run the Script**
   ```cmd
   pipenv run python main.py
   ```

### macOS

1. **Open Terminal**
   - Press `Cmd + Space`, type `Terminal`, and hit Enter.

2. **Navigate to the Project Directory**
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

### Linux

1. **Install Dependencies**
   ```bash
   pipenv install
   ```

2. **Run the Script**
   ```bash
   pipenv run python main.py
   ```

### Docker

See the `docker_compose.yaml` example.

### Additional Notes

When the script is running, switch your B2500 to "Self-Adaptation" mode to enable the powermeter functionality.

## Configuration

Configuration is managed via `config.ini`. Each powermeter type has specific settings.

### General Configuration

```ini
[GENERAL]
# Comma-separated list of device types to emulate (ct001, shellypro3em, shellyemg3, shellyproem50)
DEVICE_TYPE = ct001
# Skip initial powermeter test on startup
SKIP_POWERMETER_TEST = False
# Sum power values of all phases and report on phase 1 (ct001 only and default is False)
DISABLE_SUM_PHASES = False
# Send absolute values (necessary for storage system) (ct001 only and default is False)
DISABLE_ABSOLUTE_VALUES = False
# Interval for sending power values in seconds (ct001 only and default is 1)
POLL_INTERVAL = 1
```

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
# The alias of the sensor that provides both current power input & output
CURRENT_POWER_ENTITY = ""|sensor.current_power
# If False or Empty the power is not calculated - if empty False is Fallback
POWER_CALCULATE = ""|True|False 
# The alias of the sensor that provides the current power input.
POWER_INPUT_ALIAS = ""|sensor.power_input
# The alias of the sensor that provides the current power output.
POWER_OUTPUT_ALIAS = ""|sensor.power_output
# Is a Path Prefix needed?
API_PATH_PREFIX = ""|/core
```
Example: Variant 1 with a combined input & output sensor
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
```

The `JSON_PATH` option is used to extract the power value from a JSON payload. The path must be a [valid JSONPath expression](https://goessner.net/articles/JsonPath/). 
If the payload is a simple integer value, you can omit this option.

### Modbus

```ini
[MODBUS]
IP =
PORT =
UNIT_ID =
REGISTER =
```

### Script

You can also use a custom script to get the power values. The script should output at most 3 integer values, separated by a line break.
```ini
[SCRIPT]
COMMAND = /path/to/your/script.sh
```

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

## Home Assistant Add-on Installation

You can install the B2500 Meter add-on either through the Home Assistant repository or manually.

### Option 1: Installation via Repository (Recommended)

1. **Add the Repository to Home Assistant**
   - Open your Home Assistant instance
   - Go to Settings → Add-ons
   - Click the three dots menu in the top right corner
   - Select "Repositories"
   - Add the following URL: `https://github.com/tomquist/b2500-meter`
   - Click "Add"

2. **Install the Add-on**
   - Click on "Add-on Store" in the bottom right corner
   - The B2500 Meter add-on should appear in the add-on store
   - Click on it and then click "Install"

3. **Configure the Add-on**
   - After installation, go to the add-on's Configuration tab
   - Set the `Power Input Alias` and optionally the `Power Output Alias` to the entity IDs of your power sensors in Home Assistant
   - Set `Device Types` (comma-separated list) to the device types you want to emulate (ct001, shellypro3em, shellyemg3, shellyproem50)
   - Click "Save" to apply the configuration

4. **Start the Add-on**
   - Go to the add-on's Info tab
   - Click "Start" to run the add-on

### Option 2: Manual Installation

If you prefer to install the add-on manually, you can do so using either the Samba or SSH add-ons:

#### Using Samba:
1. Enable and start the Samba add-on in Home Assistant
2. Your Home Assistant instance will appear in your local network, sharing a folder called "addons"
3. This "addons" folder is where you should store your custom add-ons

   **Tip for macOS users:** If the folder doesn't show up automatically, go to Finder, press CMD+K, and enter `smb://homeassistant.local`

#### Using SSH:
1. Install the SSH add-on in Home Assistant
2. Before starting it, you need to have a private/public key pair and store your public key in the add-on config (refer to the SSH add-on documentation for more details)
3. Once started, you can SSH into Home Assistant
4. Store your custom add-ons in the `/addons` directory

#### Installation Steps:
1. **Copy the add-on files**
   - Copy the `ha_addon` folder from this repository into the `addons` directory you accessed via Samba or SSH
   - The resulting path should look like: `/addons/ha_addon/`
   - Rename the folder to `b2500_meter`

2. **Install and run the add-on**
   - Follow steps 2-4 from the repository installation method above

## Node-RED Implementation

This project also provides a Node-RED implementation, allowing integration with various smart meters. The Node-RED flow is available in the `nodered.json` file.

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

## License

This project is licensed under the General Public License v3.0 - see the [LICENSE](LICENSE) file for details.
