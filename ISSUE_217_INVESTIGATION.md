# Investigation Report: Issue #217 - Ethernet Support for esphome-b2500

**Repository:** tomquist/esphome-b2500
**Issue:** https://github.com/tomquist/esphome-b2500/issues/217
**Reporter:** habemusgitus
**Date:** January 11, 2026
**Investigation Date:** January 11, 2026

## Issue Summary

The user successfully configured their ESPHome B2500 device to use Ethernet instead of WiFi. The webserver works properly over Ethernet, but the B2500-specific BLE functionality fails to activate. The user suspects the BLE component is dependent on WiFi connectivity.

## Root Cause

The issue is caused by the `software_coexistence` parameter in the `esp32_ble_tracker` component. This parameter:

- **Defaults to `true`** when WiFi is configured
- **Requires the WiFi component** to function properly
- **Causes BLE initialization to fail** when WiFi is not present

When the user replaced WiFi with Ethernet configuration, they removed the WiFi component but the `esp32_ble_tracker` still expects `software_coexistence` to work, which requires WiFi radio management features.

## Technical Details

### What is Software Coexistence?

The `software_coexistence` feature manages radio interference between WiFi and Bluetooth on ESP32 chips (they share the same 2.4GHz radio). When enabled:
- Coordinates WiFi and BLE radio access
- Prevents conflicts between WiFi and Bluetooth operations
- Requires the WiFi component to be configured

### Why It Fails with Ethernet

When using Ethernet:
- No WiFi component is present
- `software_coexistence` cannot initialize
- BLE tracker fails to start or operates incorrectly
- B2500 component cannot connect via BLE

### Component Dependencies

The B2500 component itself has no WiFi dependency:
- **Declared dependencies:** `["ble_client", "time", "select"]`
- **Communication:** Entirely via Bluetooth Low Energy
- **No network checks:** Component doesn't verify WiFi status

The issue is purely at the `esp32_ble_tracker` configuration level.

## Solution

### For Users: Manual Configuration Fix

When using Ethernet instead of WiFi, explicitly disable `software_coexistence`:

```yaml
ethernet:
  type: LAN8720  # Adjust for your ethernet module
  mdc_pin: GPIO23
  mdio_pin: GPIO18
  clk_mode: GPIO17_OUT
  phy_addr: 0
  power_pin: GPIO12

esp32_ble:
  id: ble
  max_connections: 1  # Adjust for number of B2500 devices

esp32_ble_tracker:
  software_coexistence: false  # CRITICAL: Must be false without WiFi

ble_client:
  - mac_address: "XX:XX:XX:XX:XX:XX"  # Your B2500 MAC address
    id: b2500_ble_client_1
    # ... rest of configuration
```

### For the Project: Template Update

The template generator (`src/template_v2.jinja2`) needs to support Ethernet configuration and automatically set `software_coexistence: false` when Ethernet is selected.

## Implementation Plan

### Option 1: Simple Fix (Recommended for Quick Resolution)

Add a note to the template output or documentation:

**If using Ethernet instead of WiFi:**
1. Replace the `wifi:` section with your `ethernet:` configuration
2. Add `software_coexistence: false` to the `esp32_ble_tracker:` section

### Option 2: Full Template Support (Proper Long-term Solution)

Modify the template to support Ethernet as a first-class option:

**Changes to `src/template_v2.jinja2`:**

```jinja2
{% if network_type == 'ethernet' %}
# Ethernet configuration
ethernet:
  type: {{ ethernet_type }}
  mdc_pin: {{ ethernet_mdc_pin }}
  mdio_pin: {{ ethernet_mdio_pin }}
  clk_mode: {{ ethernet_clk_mode }}
  phy_addr: {{ ethernet_phy_addr }}
  {% if ethernet_power_pin %}
  power_pin: {{ ethernet_power_pin }}
  {% endif %}
  {% if enable_manual_ip %}
  manual_ip:
    static_ip: {{ manual_ip }}
    gateway: {{ gateway }}
    subnet: {{ subnet }}
  {% endif %}
{% else %}
# WiFi configuration
wifi:
  ssid: "{{ yaml_string(wifi_ssid) }}"
  password: "{{ yaml_string(wifi_password) }}"
  reboot_timeout: 0s
  fast_connect: True
  {% if enable_manual_ip %}
  manual_ip:
    static_ip: {{ manual_ip }}
    gateway: {{ gateway }}
    subnet: {{ subnet }}
  {% endif %}
{% endif %}

esp32_ble_tracker:
  {% if network_type == 'ethernet' %}
  software_coexistence: false
  {% endif %}
```

**Changes to Web UI:**

Add network configuration section:
- Radio buttons: WiFi / Ethernet
- Ethernet-specific fields (shown only when Ethernet selected):
  - Ethernet module type (dropdown: LAN8720, TLK110, IP101, W5500)
  - MDC Pin
  - MDIO Pin
  - Clock Mode
  - PHY Address
  - Power Pin (optional)

## Benefits of Ethernet for B2500

Using Ethernet instead of WiFi provides several advantages:

1. **Better BLE Performance:** No radio interference between WiFi and Bluetooth
2. **More Stable Connection:** No wireless network issues
3. **Potential for More BLE Connections:** Ethernet proxies can handle 4+ connection slots vs 3 for WiFi
4. **Eliminates Known Issues:** B2500 devices have documented BLE/WiFi coexistence problems (improved but not eliminated in firmware v224)

## Hardware Compatibility

### Supported Ethernet Modules

**PHY-based (RMII interface):**
- LAN8720 (most common)
- TLK110 (Texas Instruments)
- IP101 (budget option)

**SPI-based:**
- W5500 (requires different pin configuration)

### Boards with Built-in Ethernet

- **WT32-ETH01** - ESP32 + LAN8720
- **Olimex ESP32-POE** - ESP32 + LAN8720 + PoE
- **Olimex ESP32-POE-ISO** - ESP32 + LAN8720 + PoE + Isolation
- **LILYGO T-Internet-POE** - ESP32-S3 + W5500

## Testing Checklist

To verify the fix:

- [ ] Ethernet connectivity established
- [ ] Web server accessible
- [ ] BLE scanning active (check logs)
- [ ] BLE client connects to B2500
- [ ] B2500 component sensors update
- [ ] MQTT connectivity works
- [ ] Time synchronization functions
- [ ] Commands to B2500 execute successfully

## Files to Modify

### Quick Documentation Fix
- **README.md** - Add Ethernet troubleshooting section

### Full Template Support
- **src/template_v2.jinja2** - Add Ethernet configuration support
- **src/App.tsx** (or similar) - Add network type selection UI
- **src/types.ts** (or similar) - Add Ethernet configuration types
- **examples/** - Add Ethernet example configuration

## Example User Configuration

Here's a complete working example for WT32-ETH01:

```yaml
esphome:
  name: b2500-controller
  platform: ESP32
  board: esp32dev

ethernet:
  type: LAN8720
  mdc_pin: GPIO23
  mdio_pin: GPIO18
  clk_mode: GPIO0_IN
  phy_addr: 1
  power_pin: GPIO16

logger:
  level: DEBUG

api:
  encryption:
    key: "your-encryption-key"

ota:
  password: "your-ota-password"

esp32_ble:
  id: ble
  max_connections: 1

esp32_ble_tracker:
  software_coexistence: false  # REQUIRED for Ethernet-only setup

ble_client:
  - mac_address: "AA:BB:CC:DD:EE:FF"
    id: b2500_ble_client_1
    on_connect:
      - logger.log: "B2500 BLE connected"
      - binary_sensor.template.publish:
          id: b2500_ble_status
          state: ON
      - delay: 1s
      - b2500.set_datetime:
          b2500_id: b2500_1
          datetime: !lambda "return id(sntp_time).now();"
    on_disconnect:
      - logger.log: "B2500 BLE disconnected"
      - binary_sensor.template.publish:
          id: b2500_ble_status
          state: OFF

time:
  - platform: sntp
    id: sntp_time
    servers:
      - pool.ntp.org

b2500:
  - id: b2500_1
    ble_client_id: b2500_ble_client_1
    update_interval: 10s
    # ... rest of B2500 configuration

binary_sensor:
  - platform: template
    id: b2500_ble_status
    name: "B2500 BLE Status"
    device_class: connectivity
```

## Common Ethernet Pin Configurations

### WT32-ETH01
```yaml
ethernet:
  type: LAN8720
  mdc_pin: GPIO23
  mdio_pin: GPIO18
  clk_mode: GPIO0_IN
  phy_addr: 1
  power_pin: GPIO16
```

### Olimex ESP32-POE / ESP32-POE-ISO
```yaml
ethernet:
  type: LAN8720
  mdc_pin: GPIO23
  mdio_pin: GPIO18
  clk_mode: GPIO17_OUT
  phy_addr: 0
  power_pin: GPIO12
```

### LILYGO T-Internet-POE (W5500 SPI)
```yaml
spi:
  clk_pin: GPIO14
  mosi_pin: GPIO13
  miso_pin: GPIO12

ethernet:
  type: W5500
  cs_pin: GPIO15
  interrupt_pin: GPIO4
  reset_pin: GPIO5
```

## Validation Steps

After implementing the fix, verify:

1. **Compile succeeds** without WiFi component errors
2. **BLE tracker initializes** (check startup logs)
3. **BLE scanning active** (watch for device discovery logs)
4. **BLE client connects** to B2500 MAC address
5. **B2500 sensors populate** with data
6. **No WiFi-related errors** in logs

## References

- [ESPHome ESP32 BLE Tracker Documentation](https://esphome.io/components/esp32_ble_tracker/)
- [ESPHome BLE Client Documentation](https://esphome.io/components/ble_client/)
- [ESPHome Ethernet Component Documentation](https://esphome.io/components/ethernet/)
- [GitHub Issue #217](https://github.com/tomquist/esphome-b2500/issues/217)
- [ESPHome Feature Request: WiFi Fallback for Ethernet](https://github.com/esphome/feature-requests/issues/1357)
- [ESPHome Bluetooth Proxy Documentation](https://esphome.io/components/bluetooth_proxy/)

## Conclusion

Issue #217 is caused by the `software_coexistence` parameter defaulting to `true` in `esp32_ble_tracker`, which requires WiFi to be configured. When users switch from WiFi to Ethernet, this parameter must be explicitly set to `false`.

**Immediate Solution:** Document the need to set `software_coexistence: false` when using Ethernet

**Long-term Solution:** Update the template generator to support Ethernet as a configuration option and automatically handle the `software_coexistence` setting

**Priority:** High - This is a simple configuration issue with a clear fix that prevents legitimate hardware configurations from working

**Estimated Effort for Template Fix:**
- Template changes: 1-2 hours
- Web UI updates: 3-4 hours
- Documentation: 1-2 hours
- Testing: 2-3 hours
- **Total: 7-11 hours**
