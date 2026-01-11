# Response to Issue #217: Ethernet instead of WiFi

Hi @habemusgitus,

I've identified the issue! It's not that BLE is waiting for a WiFi event, but rather a configuration parameter that needs to be adjusted when using Ethernet.

## The Problem

The `esp32_ble_tracker` component has a `software_coexistence` parameter that:
- Defaults to `true` when WiFi is present
- Manages radio interference between WiFi and Bluetooth
- **Requires WiFi to function** - it fails when WiFi component is not configured

When you replaced WiFi with Ethernet, this parameter is still trying to coordinate with WiFi, causing BLE to fail to initialize properly.

## The Solution

Add this single line to your `esp32_ble_tracker` configuration:

```yaml
esp32_ble_tracker:
  software_coexistence: false  # Required when using Ethernet without WiFi
```

## Complete Ethernet Configuration Example

Here's what your configuration should look like:

```yaml
# Replace WiFi section with Ethernet
ethernet:
  type: LAN8720  # Adjust for your hardware
  mdc_pin: GPIO23
  mdio_pin: GPIO18
  clk_mode: GPIO17_OUT
  phy_addr: 0
  # power_pin: GPIO12  # If needed for your board

esp32_ble:
  id: ble
  max_connections: 1  # Adjust based on number of B2500 devices

esp32_ble_tracker:
  software_coexistence: false  # ← THIS IS THE CRITICAL FIX

ble_client:
  - mac_address: "XX:XX:XX:XX:XX:XX"  # Your B2500 MAC
    id: b2500_ble_client_1
    # ... rest of your configuration
```

## Why This Works

Since you're using Ethernet instead of WiFi:
- No WiFi radio activity = no need for WiFi/BLE coexistence management
- Disabling `software_coexistence` allows BLE to initialize without WiFi
- Actually **improves BLE performance** since there's no WiFi radio interference

## Hardware-Specific Pin Configurations

**WT32-ETH01:**
```yaml
ethernet:
  type: LAN8720
  mdc_pin: GPIO23
  mdio_pin: GPIO18
  clk_mode: GPIO0_IN
  phy_addr: 1
  power_pin: GPIO16
```

**Olimex ESP32-POE / ESP32-POE-ISO:**
```yaml
ethernet:
  type: LAN8720
  mdc_pin: GPIO23
  mdio_pin: GPIO18
  clk_mode: GPIO17_OUT
  phy_addr: 0
  power_pin: GPIO12
```

**LILYGO T-Internet-POE (W5500):**
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

## What to Check

After adding `software_coexistence: false`, verify in the logs:
1. ✅ Ethernet connects successfully
2. ✅ BLE tracker initializes
3. ✅ BLE client finds and connects to your B2500
4. ✅ B2500 sensors start reporting data

## Additional Benefits

Using Ethernet for B2500 control actually has advantages over WiFi:
- **Better BLE stability** - no radio interference
- **More reliable** - no wireless connection issues
- **Potential for more simultaneous connections** - Ethernet proxies can handle 4+ BLE devices vs 3 for WiFi
- **Avoids known issues** - B2500 has documented BLE/WiFi coexistence problems (improved but not eliminated in FW v224)

## Code Changes Needed

For the template generator to support this properly:

**File:** `src/template_v2.jinja2`

The template should conditionally set `software_coexistence` based on network type:

```jinja2
esp32_ble_tracker:
  {% if network_type == 'ethernet' %}
  software_coexistence: false
  {% endif %}
```

Would you like me to prepare a PR to add native Ethernet support to the configuration generator?

Let me know if this resolves your issue or if you need help with the configuration!

---

**References:**
- [ESPHome ESP32 BLE Tracker Docs](https://esphome.io/components/esp32_ble_tracker/)
- [ESPHome Ethernet Docs](https://esphome.io/components/ethernet/)
- [ESPHome Bluetooth Proxy Docs](https://esphome.io/components/bluetooth_proxy/)
