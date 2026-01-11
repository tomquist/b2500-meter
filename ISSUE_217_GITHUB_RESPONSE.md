Hi @habemusgitus,

Thanks for reporting this issue. To help diagnose the problem, could you provide some additional information?

## What I'd like to see:

1. **Your full ESPHome YAML configuration** (with sensitive info like passwords/MAC addresses redacted)
2. **Complete logs from startup** showing:
   - Ethernet connection status
   - BLE tracker initialization
   - Any errors or warnings
   - Whether BLE scanning starts
3. **What specifically isn't working:**
   - Does BLE scanning start at all?
   - Does it find the B2500 device but not connect?
   - Does it connect but sensors don't update?
   - Are there any error messages?

## What I've investigated so far:

I looked into the ESPHome source code to understand the WiFi/Ethernet/BLE relationship:

**Finding 1: `software_coexistence` behavior**
- This parameter uses `OnlyWith('wifi', default=True)` in the config schema
- When WiFi component is NOT present, this setting becomes `undefined` (not set at all)
- The code only enables coexistence features if explicitly set to True: `if config.get(CONF_SOFTWARE_COEXISTENCE):`
- **Conclusion:** BLE tracker should work fine without WiFi present - no special configuration needed

**Finding 2: BLE initialization**
- The `esp32_ble_tracker` component has no hardcoded WiFi dependency in the C++ code
- BLE scanning is managed by the ESP-IDF BLE stack, not network components
- The B2500 component itself only depends on: `["ble_client", "time", "select"]`

**Finding 3: Template consideration**
- The generated template from the web UI includes WiFi `on_connect`/`on_disconnect` handlers that log "Starting/Stopping BLE scan"
- However, these are just log messages - they don't actually call `ble_tracker.start_scan()`
- The BLE tracker should auto-start based on the configuration

## Questions to narrow down the issue:

1. Did you generate your config from the web UI or manually create it?
2. Did you completely remove the `wifi:` section or just replace it with `ethernet:`?
3. What ESP32 board are you using? (e.g., WT32-ETH01, Olimex ESP32-POE, etc.)
4. Can you share your Ethernet pin configuration?

## Potential areas to check:

- Make sure `esp32_ble_tracker:` section is present in your config
- Verify your B2500 MAC address is correct in the `ble_client:` section
- Check if `auto_connect` is enabled (it defaults to true)
- Ensure the B2500 device is in range and powered on

Once I see the logs and configuration, I can help identify the actual root cause. Right now I'm working on assumptions without seeing what's actually failing.

Thanks!
