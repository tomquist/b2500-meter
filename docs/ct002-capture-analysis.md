# CT002/CT003 Capture Analysis (Issue #111)

This note documents findings from two packet captures shared for issue #111:

- `charge 1 batteryes.pcap` (single-active-battery scenario)
- `charge 3 batteryes.pcap` (multi-active-battery scenario)

The goal is to describe observed wire behavior as clearly as possible.

## 1) Network roles and transport

Observed UDP traffic:

- **Storage endpoint:** `<storage_host>:12345`
- **Battery/consumer endpoints:**
  - `<battery_A_host>:22222` (battery A)
  - `<battery_B_host>:22222` (battery B)
  - `<battery_C_host>:22222` (battery C)

Request direction:
- battery -> storage (`22222 -> 12345`)

Response direction:
- storage -> battery (`12345 -> 22222`)

## 2) Request payload structure (confirmed)

Observed request payload pattern:

`LEN|HMG-50|<battery_mac>|HME-3|<ct_mac>|<phase>|<power>`

Example from capture (anonymized):

`53|HMG-50|<battery_mac>|HME-3|<ct_mac>|B|-217`

Field mapping (from observed packets):

1. `LEN`
2. storage type (`HMG-50`)
3. battery/storage MAC (`battery_mac`)
4. CT type (`HME-3` in these captures)
5. CT MAC (`<ct_mac>`)
6. **phase** (`A`/`B` seen)
7. **phase power** (signed integer)

### Important implication

The last two request fields are **phase + signed power**, not `charge_power/discharge_power`.

## 3) Response payload structure (partially confirmed)

Observed response payload pattern:

`LEN|HME-3|<ct_mac>|HMG-50|<battery_mac>|v1|v2|v3|v4|...`

Example (anonymized):

`135|HME-3|<ct_mac>|HMG-50|<battery_mac>|121|202|-294|29|1|2|0|0|-36|0|0|-353|-270|...`

Confirmed:

- Identity fields are consistent and mirrored:
  - CT type/mac first
  - storage type/mac second
- Numeric section starts immediately after those identity fields.

Likely (high confidence):

- `v1..v3` are per-phase-like values
- `v4` behaves like a total/aggregate value (often close to sum with small +/- drift)

Unclear (needs targeted experiments):

- exact semantics of later fields after `v4` (status/counters/energy accumulators/etc.)

## 4) Scenario comparison: single-active vs multi-active

### `charge 1 batteryes.pcap`

Requests: 401, Responses: 290

Observed request senders:
- battery A, phase `A`, power range `-275..-208` (active)
- battery B, phase `B`, power range `0..0` (inactive)
- battery C, phase `B`, power range `0..0` (inactive)

Interpretation:
- Three batteries still communicate, but only one contributes non-zero power.

### `charge 3 batteryes.pcap`

Requests: 604, Responses: 428

Observed request senders:
- battery A, phase `A`, power range `-368..-141`
- battery B, phase `B`, power range `-217..-70`
- battery C, phase `B`, power range `-121..0`

Interpretation:
- All three batteries actively report non-zero power.

## 5) Additional observations

- Two devices (battery B and battery C) both report phase `B` in these captures.
  - So phase label is not guaranteed to be globally unique per device.
- Response destination identity aligns with requesting battery identity (no obvious cross-target mismatches).

## 6) Practical modeling guidance

For emulator/protocol implementation:

- Parse request tail strictly as:
  - `phase = fields[4]`
  - `power = int(fields[5])`
- Keep legacy fallback only for synthetic/older tests.
- Treat later response fields as implementation-defined unless verified with controlled experiments.

## 7) Suggested follow-up experiments

To resolve remaining unknown response fields:

1. Run controlled tests with exactly one battery changing power stepwise (e.g. -100, -200, -300).
2. Repeat with two batteries toggling one at a time.
3. Correlate each response field against known injected values.
4. Label fields only when correlation is stable across runs.
