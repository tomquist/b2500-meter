# B2500 Meter

This project replicates a Smart Meter device for a B2500 energy storage system while allowing integration with various smart meters.

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
   pipenv run python smartmeter.py
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
   pipenv run python smartmeter.py
   ```

### Linux

1. **Install Dependencies**
   ```bash
   pipenv install
   ```

2. **Run the Script**
   ```bash
   pipenv run python smartmeter.py
   ```

### Additional Notes

When the script is running, switch your B2500 to "Self-Adaptation" mode to enable the powermeter functionality.

## Configuration

The configuration is managed using an `ini` file called `config.ini`. Below, you'll find the configuration settings required for each supported powermeter type.

### General Configuration

Add a general section with the option to enable or disable summation of phase values.

```ini
[GENERAL]
# By default, the script will sum the power values of all phases and report them as a single value on phase 1. To disable this behavior, add the following configuration to the `config.ini` file
DISABLE_SUM_PHASES = False
# It looks like the B2500 storage currently does not support negative power values so they get clamped to 0 by default. To disable this behavior, you can set the following configuration to `True`
ALLOW_NEGATIVE_VALUES = False
SKIP_POWERMETER_TEST = False
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
HTTPS = True
ACCESSTOKEN = YOUR_ACCESS_TOKEN
CURRENT_POWER_ENTITY = sensor.current_power
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

## License

This project is licensed under the General Public License v3.0 - see the [LICENSE](LICENSE) file for details.
