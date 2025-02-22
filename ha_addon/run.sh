#!/usr/bin/with-contenv bashio
set -e

CONFIG="/app/config.ini"

# Check if custom config is provided
if bashio::config.has_value 'custom_config' && [ -f "/config/$(bashio::config 'custom_config')" ]; then
    bashio::log.info "Using custom config file: $(bashio::config 'custom_config')"
    cp "/config/$(bashio::config 'custom_config')" "$CONFIG"
else
    # Generate default config
    {
        echo "[GENERAL]"
        echo "DEVICE_TYPE=$(bashio::config 'device_types')"
        echo "POLL_INTERVAL=$(bashio::config 'poll_interval')"
        echo "DISABLE_ABSOLUTE_VALUES=$(bashio::config 'disable_absolute_values')"
        echo ""
        echo "[HOMEASSISTANT]"
        echo "IP=supervisor"
        echo "PORT=80"
        echo "API_PATH_PREFIX=/core"
        echo "ACCESSTOKEN=$SUPERVISOR_TOKEN"
        if bashio::config.has_value 'power_output_alias'; then
            echo "POWER_CALCULATE=True"
            echo "POWER_INPUT_ALIAS=$(bashio::config 'power_input_alias')"
            echo "POWER_OUTPUT_ALIAS=$(bashio::config 'power_output_alias')"
        else
            echo "POWER_CALCULATE=False"
            echo "CURRENT_POWER_ENTITY=$(bashio::config 'power_input_alias')"
        fi
    } > "$CONFIG"
fi

cat "$CONFIG"
. /app/venv/bin/activate
cd /app
python3 main.py