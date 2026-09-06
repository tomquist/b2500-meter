import math

import pytest
from aioesphomeapi import SensorInfo, SensorState

from .esphome_native import ESPHomeNative

# ---------------------------------------------------------------------------
# ESPHomeNative async unit tests (no device needed)
#
# The class is push-based: ReconnectLogic drives connect/disconnect and the API
# client pushes SensorState updates into ``change_callback``. We drive those
# callbacks directly instead of standing up a real ESPHome device.
# ---------------------------------------------------------------------------

OBJECT_ID = "grid_power"
ENTITY_KEY = 42


def _make_pm(object_id: str = OBJECT_ID) -> ESPHomeNative:
    return ESPHomeNative(
        address="device.local",
        port="6053",
        api_key="",
        object_id=object_id,
        client_info="AstraMeter-Test",
    )


def _subscribed_pm(
    object_id: str = OBJECT_ID, unit: str | None = None
) -> ESPHomeNative:
    """A meter that has already 'discovered' its entity, as connect_callback would."""
    pm = _make_pm(object_id)
    pm.is_connected = True
    info = SensorInfo(  # type: ignore[call-arg]
        key=ENTITY_KEY, object_id=object_id, unit_of_measurement=unit or ""
    )
    pm.entity_info = info
    pm._read_unit(info)
    return pm


def _state(value: float, missing_state: bool = False) -> SensorState:
    return SensorState(  # type: ignore[call-arg]
        key=ENTITY_KEY, state=value, missing_state=missing_state
    )


async def test_no_value_before_message() -> None:
    pm = _subscribed_pm()
    assert await pm.get_powermeter_watts() == []


async def test_get_powermeter_watts_returns_latest() -> None:
    pm = _subscribed_pm()
    pm.change_callback(_state(123.0))
    assert await pm.get_powermeter_watts() == [123.0]
    pm.change_callback(_state(456.0))
    assert await pm.get_powermeter_watts() == [456.0]


async def test_change_callback_ignores_other_entities() -> None:
    pm = _subscribed_pm()
    pm.change_callback(SensorState(key=ENTITY_KEY + 1, state=999.0))  # type: ignore[call-arg]
    assert await pm.get_powermeter_watts() == []


async def test_change_callback_ignores_before_subscribe() -> None:
    pm = _make_pm()  # entity_info is None until connect_callback runs
    pm.change_callback(_state(123.0))
    assert await pm.get_powermeter_watts() == []


async def test_change_callback_drops_missing_state() -> None:
    pm = _subscribed_pm()
    pm.change_callback(_state(100.0))
    pm.change_callback(_state(math.nan, missing_state=True))
    # The unavailable update is dropped; the last good value is kept.
    assert await pm.get_powermeter_watts() == [100.0]


async def test_change_callback_drops_nan_without_missing_flag() -> None:
    pm = _subscribed_pm()
    pm.change_callback(_state(100.0))
    pm.change_callback(_state(math.nan))
    assert await pm.get_powermeter_watts() == [100.0]


async def test_wait_for_message_returns_after_message() -> None:
    pm = _subscribed_pm()
    pm.change_callback(_state(10.0))
    await pm.wait_for_message(timeout=0.1)


async def test_wait_for_message_times_out_without_message() -> None:
    pm = _subscribed_pm()
    with pytest.raises(TimeoutError):
        await pm.wait_for_message(timeout=0.05)


async def test_wait_for_next_message_blocks_until_new() -> None:
    pm = _subscribed_pm()
    pm.change_callback(_state(10.0))
    # wait_for_next_message must wait for the *next* update, not return on the
    # already-received one.
    with pytest.raises(TimeoutError):
        await pm.wait_for_next_message(timeout=0.05)


async def test_disconnect_clears_value() -> None:
    pm = _subscribed_pm()
    pm.change_callback(_state(50.0))
    assert await pm.get_powermeter_watts() == [50.0]

    await pm.disconnect_callback(expected_disconnect=True)

    # After a disconnect the meter reports no value and is offline.
    assert await pm.get_powermeter_watts() == []
    assert pm.stream_online() is False
    assert pm.entity_info is None


async def test_stream_online_reflects_connection() -> None:
    pm = _make_pm()
    assert pm.stream_online() is False
    pm.is_connected = True
    assert pm.stream_online() is True


async def test_connect_error_resets_state() -> None:
    pm = _subscribed_pm()
    pm.change_callback(_state(50.0))
    await pm.connect_error_callback(RuntimeError("boom"))
    assert pm.stream_online() is False
    assert await pm.get_powermeter_watts() == []


# ---------------------------------------------------------------------------
# Declared units (issues #39 / #572)
#
# The native API carries the sensor's ``unit_of_measurement``, so a kW sensor
# must be converted rather than read as watts — the failure that leaves typical
# household readings rounding to ~0 W and the batteries idle with no error.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("unit", "expected"),
    [
        (None, 1234.0),  # undeclared: assumed watts, as installs relied on
        ("W", 1234.0),
        ("kW", 1_234_000.0),
        ("MW", 1_234_000_000.0),
        ("mW", 1.234),
    ],
)
async def test_declared_power_unit_is_converted_to_watts(
    unit: str | None, expected: float
) -> None:
    pm = _subscribed_pm(unit=unit)
    pm.change_callback(_state(1234.0))
    assert await pm.get_powermeter_watts() == pytest.approx([expected])


async def test_non_power_unit_is_rejected_rather_than_read_as_watts() -> None:
    """A sensor that isn't power fails loudly instead of steering the batteries.

    An empty reading would read as "meter unavailable" downstream, which hides
    a permanent misconfiguration behind a transient-looking outage.
    """
    pm = _subscribed_pm(unit="kWh")
    pm.change_callback(_state(1234.0))
    with pytest.raises(ValueError, match="not a power unit"):
        await pm.get_powermeter_watts()


async def test_unit_is_re_read_on_reconnect() -> None:
    pm = _subscribed_pm(unit="kW")
    pm.change_callback(_state(1.0))
    assert await pm.get_powermeter_watts() == pytest.approx([1000.0])

    await pm.disconnect_callback(expected_disconnect=False)
    assert pm._unit is None

    # The device comes back declaring watts; the old scale must not survive.
    info = SensorInfo(  # type: ignore[call-arg]
        key=ENTITY_KEY, object_id=OBJECT_ID, unit_of_measurement="W"
    )
    pm.entity_info = info
    pm._read_unit(info)
    pm.change_callback(_state(1.0))
    assert await pm.get_powermeter_watts() == pytest.approx([1.0])
