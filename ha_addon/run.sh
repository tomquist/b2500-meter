#!/usr/bin/with-contenv bashio
set -e

CONFIG="/app/config.ini"

{
  echo "[GENERAL]"
  echo "POLL_INTERVAL=$(bashio::config 'poll_interval')"
  echo "DISABLE_ABSOLUTE_VALUES=$(bashio::config 'disable_absolute_values')"
  echo "DISABLE_SUM_PHASES=$(bashio::config 'disable_sum_phases')"
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

. /app/venv/bin/activate
cd /app
python3 main.py