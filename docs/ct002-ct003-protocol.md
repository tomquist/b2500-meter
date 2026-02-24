# CT002 / CT003 UDP Protocol

This document summarizes the CT002/CT003 protocol based on community reverse‑engineering and the reference scripts in:
- https://github.com/rweijnen/marstek-venus-e-firmware-notes
- https://github.com/d-shmt/hass_marstek-smart-meter

The CT002 and CT003 share the **same protocol**. The only difference is the CT type value:
- **CT002:** `HME-4`
- **CT003:** `HME-3`

## Transport

- **Protocol:** UDP
- **Port:** `12345`
- **Direction:** Storage system (consumer) sends a request to the CT. CT replies with measurements.

## Frame Format

All messages (request and response) are ASCII payloads wrapped with control bytes and a checksum.

```text
SOH (0x01)
STX (0x02)
<LENGTH ASCII digits>
|<field1>|<field2>|...|<fieldN>
ETX (0x03)
<CHECKSUM ASCII HEX>
```

### Length
`LENGTH` is the **total byte length** of the entire packet, including the length digits and checksum bytes.
Because the length field is part of the packet, you must compute it iteratively until the digit count matches.

### Checksum
The checksum is a 2‑character ASCII hex string (lowercase in observed traffic). It is the XOR of all bytes from the
**start of SOH up to and including ETX**.

Pseudo‑code:

```python
xor = 0
for b in payload_without_checksum:
    xor ^= b
checksum = f"{xor:02x}".encode("ascii")
```

## Request Fields

Request payload fields (consumer → CT):

1. **meter_dev_type** — device type of the storage system (commonly `HMG-50` for Venus/B2500)
2. **meter_mac_code** — battery MAC (12 hex chars, from Marstek app device management)
3. **hhm_dev_type** — CT type (`HME-4` or `HME-3`)
4. **hhm_mac_code** — CT MAC (12 hex chars, from Marstek app device management)
5. **phase** — phase identifier (`A`, `B`, `C`) observed in real traffic
6. **phase_power** — signed integer watts for the phase in field 5

This mapping is based on real packet captures. Older public scripts may show `0|0` placeholders,
but observed live traffic carries `phase|power` in these two fields.

### Example Request (human readable)

```text
<SOH><STX>53|HMG-50|AABBCCDDEEFF|HME-4|112233445566|B|-217<ETX>xx
```

## Response Fields

Response payload fields (CT → consumer):

1. **meter_dev_type** — echoes request field 1
2. **meter_mac_code** — echoes request field 2
3. **hhm_dev_type** — CT type (`HME-4` or `HME-3`)
4. **hhm_mac_code** — CT MAC
5. **A_phase_power** — integer watts for phase A
6. **B_phase_power** — integer watts for phase B
7. **C_phase_power** — integer watts for phase C
8. **total_power** — integer watts (sum of phases)
9. **A_chrg_nb** — 0
10. **B_chrg_nb** — 0
11. **C_chrg_nb** — 0
12. **ABC_chrg_nb** — 0
13. **wifi_rssi** — integer RSSI (e.g., `-50`)
14. **info_idx** — integer index (often `0`)
15. **x_chrg_power** — 0
16. **A_chrg_power** — 0
17. **B_chrg_power** — 0
18. **C_chrg_power** — 0
19. **ABC_chrg_power** — 0
20. **x_dchrg_power** — 0
21. **A_dchrg_power** — 0
22. **B_dchrg_power** — 0
23. **C_dchrg_power** — 0
24. **ABC_dchrg_power** — 0

Only the phase and total power fields are required for the storage system to react. The remaining fields
are less well understood and may contain status/counter values in vendor firmware.

## Multi‑consumer behavior

When multiple storage systems query the same CT emulator, each system should receive a response that
reflects the grid power **excluding its own output** so the devices do not over‑compensate.

The emulator therefore:
- Tracks per‑consumer `phase` + `phase_power` from the request fields.
- When responding to consumer **X**, it includes only *other* consumers in the per-phase report fields,
  grouped by their reported phase.

This avoids feeding a storage unit its own reported contribution and helps reduce feedback loops in
multi-consumer setups.

If a consumer stops sending updates for a while, its reported values are evicted after a configurable
TTL (`CONSUMER_TTL`).

## CT MAC behavior

The CT only responds if the request’s `hhm_mac_code` matches its configured `CT_MAC`. For convenience,
the emulator can be configured to accept any CT MAC (or `000000000000` as a wildcard) when
`ALLOW_ANY_CT_MAC=true`. When `CT_MAC` is not set, the emulator echoes the request’s CT MAC back in
responses to keep configuration simple (this fallback is not based on device RE).
