# Changelog

## Next
- Added SML powermeter support for power readings over a local serial port (Smart Message Language / IR head), configurable with `[SML]` and `SERIAL`; auto-detects per-phase power when L1–L3 OBIS are present and supports optional OBIS hex overrides ([#229](https://github.com/tomquist/b2500-meter/pull/229))
- Clarified README: emulated device types (CT001/Shelly) are listed separately from powermeter data sources such as SMA Energy Meter / Sunny Home Manager
- Added HomeWizard P1 powermeter support via the device WebSocket API with token and serial configuration ([#231](https://github.com/tomquist/b2500-meter/pull/231)), including optional `VERIFY_SSL` to disable TLS certificate verification on trusted networks when needed ([#254](https://github.com/tomquist/b2500-meter/pull/254))
- Added SMA Energy Meter / Sunny Home Manager support via Speedwire multicast protocol with auto-detection and per-phase power readings ([#231](https://github.com/tomquist/b2500-meter/pull/252))
- Switched the Home Assistant powermeter integration from REST polling to the WebSocket API and improved missing/non-numeric sensor state handling ([#232](https://github.com/tomquist/b2500-meter/pull/232), [#193](https://github.com/tomquist/b2500-meter/pull/193))
- Added optional Marstek cloud auto-registration for managed fake `ct002` and `ct003` devices at startup ([#237](https://github.com/tomquist/b2500-meter/pull/237))
- Added battery activity info logs for Shelly emulation to report detection, inactivity, and reconnection events ([#241](https://github.com/tomquist/b2500-meter/pull/241))
- Added `POWER_OFFSET` and `POWER_MULTIPLIER` transforms for any powermeter, including per-phase calibration, sign flipping, and phase nulling support ([#250](https://github.com/tomquist/b2500-meter/pull/250))
- Improved power transform validation and logging, including support for `POWER_MULTIPLIER = 0`, one-time phase-mismatch warnings, and preserved exception chaining for invalid float lists ([#250](https://github.com/tomquist/b2500-meter/pull/250))
- Added `LOG_LEVEL` environment variable support for Docker and CLI runs ([#174](https://github.com/tomquist/b2500-meter/pull/174))
- Reduced throttling output noise by replacing unconditional `print` calls in `ThrottledPowermeter` with structured logging (`logger.debug` for routine wait/fetch/cache messages; failures remain at error level) ([#251](https://github.com/tomquist/b2500-meter/pull/251))
- Improved Shelly UDP server robustness by adding socket timeouts to avoid hangs during shutdown and testing ([#233](https://github.com/tomquist/b2500-meter/pull/233))
- Fixed Modbus `UNIT_ID` handling and clarified Home Assistant entity ID configuration in the docs ([#191](https://github.com/tomquist/b2500-meter/pull/191), [#195](https://github.com/tomquist/b2500-meter/pull/195))

### Breaking
- The Home Assistant add-on no longer publishes images for 32-bit ARM (`armhf` / `armv7`). Installations must use a 64-bit Home Assistant OS or supervisor environment (`amd64` or `aarch64`), consistent with Home Assistant dropping 32-bit support.

## 1.0.8
- Added support for Modbus holding registers through new `REGISTER_TYPE` configuration option ([#173](https://github.com/tomquist/b2500-meter/pull/173))
- Improved Shelly emulator with threaded UDP handling for better performance under concurrent requests when throttle interval is used ([#168](https://github.com/tomquist/b2500-meter/pull/168))
- Enhanced TQ Energy Manager with signed power calculation using separate import/export OBIS codes ([#153](https://github.com/tomquist/b2500-meter/pull/153))
- Fixed powermeter test results to log at info level instead of debug level ([#165](https://github.com/tomquist/b2500-meter/pull/165))

## 1.0.7
- Added support for TQ Energy Manager devices through new TQ EM powermeter integration
- Added generic JSON HTTP powermeter integration with JSONPath support for flexible data extraction
- Fixed health check service port from 8124 to 52500

## 1.0.6
- Modbus: Support powermeters spanning multiple registers
- Modbus: Allow changing endianess
- Add dedicated health service module with endpoints on port 52500
- Implement multi-layer auto-restart: supervisor watchdog, startup retries, health checks

## 1.0.5
- Added throttling of powermeter readings for slow data sources to prevent oscillation.

## 1.0.4

### Added
- Added support for Shelly Pro 3EM on port 2220 (B2500 firmware version >=226)
- Added backward compatibility for Shelly Pro 3EM devices through shellypro3em_old (port 1010) and shellypro3em_new (port 2220) device types

## 1.0.3

### Added
- Support for three-phase power monitoring in Home Assistant integration
- Support for multiple powermeters (not through the HomeAssistant addon at this point)
- Allow providing custom config file in HA Addon

## 1.0.0 - Initial Release

- Initial release of B2500 Meter
- Support for emulating a CT001, Shelly Pro 3EM, Shelly EM gen3 and Shelly Pro EM50 for Marstek/Hame storages
- Support for various power meter integrations:
  - Shelly devices (1PM, Plus1PM, EM, 3EM, 3EMPro)
  - Tasmota devices
  - Home Assistant
  - MQTT
  - Modbus
  - ESPHome
  - VZLogger
  - AMIS Reader
  - IoBroker
  - Emlog
  - Shrdzm
  - Script execution
