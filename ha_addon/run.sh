#!/usr/bin/with-contenv bashio
set -e

# Function to check if Home Assistant is ready
wait_for_homeassistant() {
    local max_attempts=60  # 5 minutes with 5-second intervals
    local attempt=1
    local ha_url="http://supervisor:80/core/api/"
    
    bashio::log.info "Waiting for Home Assistant to be ready..."
    
    while [ $attempt -le $max_attempts ]; do
        bashio::log.debug "Checking Home Assistant readiness (attempt $attempt/$max_attempts)..."
        
        # Check if the API responds with a valid status
        if curl -s -f -H "Authorization: Bearer $SUPERVISOR_TOKEN" \
           -H "Content-Type: application/json" \
           --connect-timeout 5 --max-time 10 \
           "$ha_url" > /dev/null 2>&1; then
            bashio::log.info "Home Assistant is ready! Proceeding with B2500 Meter startup..."
            return 0
        fi
        
        bashio::log.debug "Home Assistant not ready yet, waiting 5 seconds..."
        sleep 5
        attempt=$((attempt + 1))
    done
    
    bashio::log.warning "Home Assistant may not be fully ready after $((max_attempts * 5)) seconds, but continuing anyway..."
    return 1
}

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
        echo "THROTTLE_INTERVAL=$(bashio::config 'throttle_interval')"
        echo "ENABLE_HEALTH_CHECK=true"
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

# Wait for Home Assistant to be ready before starting
wait_for_homeassistant

. /app/venv/bin/activate
cd /app

# Get log level from configuration (defaults to info)
LOG_LEVEL=$(bashio::config 'log_level')
bashio::log.info "Starting B2500 Meter with log level: $LOG_LEVEL"
python3 main.py --loglevel "$LOG_LEVEL"