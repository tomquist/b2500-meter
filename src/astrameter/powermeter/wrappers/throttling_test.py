import asyncio
import logging
from unittest.mock import AsyncMock, Mock

import pytest

from .throttling import ThrottledPowermeter


async def test_no_throttling_always_fetches_fresh_values() -> None:
    """Test that when throttling is disabled, fresh values are always fetched."""
    mock_pm = Mock()
    mock_pm.get_powermeter_watts = AsyncMock(return_value=[100.0, 200.0, 300.0])
    mock_pm.get_powermeter_watts_raw = mock_pm.get_powermeter_watts
    throttled = ThrottledPowermeter(mock_pm, throttle_interval=0)

    result1 = await throttled.get_powermeter_watts()
    result2 = await throttled.get_powermeter_watts()

    assert result1 == [100.0, 200.0, 300.0]
    assert result2 == [100.0, 200.0, 300.0]
    assert mock_pm.get_powermeter_watts.call_count == 2


async def test_throttling_waits_for_interval() -> None:
    """Test that throttling waits for remaining time before fetching new values."""
    mock_pm = Mock()
    mock_pm.get_powermeter_watts = AsyncMock(return_value=[100.0, 200.0, 300.0])
    mock_pm.get_powermeter_watts_raw = mock_pm.get_powermeter_watts
    throttled = ThrottledPowermeter(mock_pm, throttle_interval=0.2)

    result1 = await throttled.get_powermeter_watts()
    assert result1 == [100.0, 200.0, 300.0]
    assert mock_pm.get_powermeter_watts.call_count == 1

    mock_pm.get_powermeter_watts.return_value = [400.0, 500.0, 600.0]

    loop = asyncio.get_running_loop()
    start_time = loop.time()
    result2 = await throttled.get_powermeter_watts()
    elapsed = loop.time() - start_time

    assert result2 == [400.0, 500.0, 600.0]
    assert mock_pm.get_powermeter_watts.call_count == 2
    assert elapsed >= 0.2


async def test_throttling_fetches_fresh_after_interval() -> None:
    """Test that fresh values are fetched after throttling interval passes."""
    mock_pm = Mock()
    mock_pm.get_powermeter_watts = AsyncMock(return_value=[100.0, 200.0, 300.0])
    mock_pm.get_powermeter_watts_raw = mock_pm.get_powermeter_watts
    throttled = ThrottledPowermeter(mock_pm, throttle_interval=0.1)

    result1 = await throttled.get_powermeter_watts()
    assert result1 == [100.0, 200.0, 300.0]
    assert mock_pm.get_powermeter_watts.call_count == 1

    mock_pm.get_powermeter_watts.return_value = [400.0, 500.0, 600.0]

    await asyncio.sleep(0.2)

    result2 = await throttled.get_powermeter_watts()
    assert result2 == [400.0, 500.0, 600.0]
    assert mock_pm.get_powermeter_watts.call_count == 2


async def test_wait_for_message_passthrough() -> None:
    """Test that wait_for_message is passed through to wrapped powermeter."""
    mock_pm = Mock()
    mock_pm.wait_for_message = AsyncMock()
    throttled = ThrottledPowermeter(mock_pm, throttle_interval=1.0)

    await throttled.wait_for_message(timeout=30)
    mock_pm.wait_for_message.assert_called_once_with(30)


async def test_wait_for_next_message_passthrough() -> None:
    mock_pm = Mock()
    mock_pm.wait_for_next_message = AsyncMock()
    throttled = ThrottledPowermeter(mock_pm, throttle_interval=1.0)

    await throttled.wait_for_next_message(timeout=15)
    mock_pm.wait_for_next_message.assert_called_once_with(15)


async def test_exception_handling_with_cache() -> None:
    """Test that cached values are returned on error after a successful fetch."""
    mock_pm = Mock()
    mock_pm.start = AsyncMock()
    mock_pm.stop = AsyncMock()
    mock_pm.get_powermeter_watts = AsyncMock(return_value=[100.0, 200.0])
    mock_pm.get_powermeter_watts_raw = mock_pm.get_powermeter_watts

    throttled = ThrottledPowermeter(mock_pm, throttle_interval=0.1)

    result1 = await throttled.get_powermeter_watts()
    assert result1 == [100.0, 200.0]

    mock_pm.get_powermeter_watts.side_effect = Exception("Network error")

    result2 = await throttled.get_powermeter_watts()
    assert result2 == [100.0, 200.0]


async def test_exception_raises_without_cache() -> None:
    """Test that exceptions propagate if no cached values exist."""
    mock_pm = Mock()
    mock_pm.start = AsyncMock()
    mock_pm.stop = AsyncMock()
    mock_pm.get_powermeter_watts = AsyncMock(side_effect=Exception("Network error"))
    mock_pm.get_powermeter_watts_raw = mock_pm.get_powermeter_watts

    throttled = ThrottledPowermeter(mock_pm, throttle_interval=0.1)

    with pytest.raises(Exception, match="Network error"):
        await throttled.get_powermeter_watts()


async def test_throttled_raw_bypasses_get_and_throttle_coalescing() -> None:
    mock_pm = Mock()
    get_m = AsyncMock(return_value=[1.0])
    raw_m = AsyncMock(return_value=[2.0, 3.0, 4.0])
    mock_pm.get_powermeter_watts = get_m
    mock_pm.get_powermeter_watts_raw = raw_m
    throttled = ThrottledPowermeter(mock_pm, throttle_interval=3600.0)

    assert await throttled.get_powermeter_watts_raw() == [2.0, 3.0, 4.0]
    raw_m.assert_awaited_once()
    get_m.assert_not_called()


class _FakeClock:
    """Monotonic clock a test drives by hand, so the grace window is exact."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _failing_after_one_read(values: list[float]) -> Mock:
    mock_pm = Mock()
    mock_pm.get_powermeter_watts = AsyncMock(return_value=values)
    mock_pm.get_powermeter_watts_raw = mock_pm.get_powermeter_watts
    return mock_pm


async def test_stale_cache_expires_and_the_error_reaches_the_caller() -> None:
    """A read that keeps failing must stop being answered from the cache.

    CT002 turns the failure into a zero adjustment so batteries hold their
    output; an endlessly served cached value would keep them steering against
    a reading from before the outage instead (issue #403's failure mode).
    """
    clock = _FakeClock()
    mock_pm = _failing_after_one_read([100.0, 200.0])
    throttled = ThrottledPowermeter(mock_pm, throttle_interval=3.0, clock=clock)

    assert await throttled.get_powermeter_watts() == [100.0, 200.0]
    mock_pm.get_powermeter_watts.side_effect = ValueError("sensor has no state")

    # Grace window is 2 x 3 s: within it the last reading still stands in.
    clock.now += 3.0
    assert await throttled.get_powermeter_watts() == [100.0, 200.0]
    clock.now += 3.0
    assert await throttled.get_powermeter_watts() == [100.0, 200.0]

    clock.now += 3.0
    with pytest.raises(ValueError, match="sensor has no state"):
        await throttled.get_powermeter_watts()


async def test_expired_cache_is_not_resurrected_by_a_later_failure() -> None:
    clock = _FakeClock()
    mock_pm = _failing_after_one_read([100.0])
    throttled = ThrottledPowermeter(mock_pm, throttle_interval=3.0, clock=clock)

    await throttled.get_powermeter_watts()
    mock_pm.get_powermeter_watts.side_effect = ValueError("down")
    clock.now += 100.0
    with pytest.raises(ValueError):
        await throttled.get_powermeter_watts()

    # Still failing a moment later: the pre-outage reading must stay gone.
    clock.now += 1.0
    with pytest.raises(ValueError):
        await throttled.get_powermeter_watts()


async def test_short_throttle_keeps_a_five_second_grace_floor() -> None:
    clock = _FakeClock()
    mock_pm = _failing_after_one_read([50.0])
    throttled = ThrottledPowermeter(mock_pm, throttle_interval=0.2, clock=clock)

    await throttled.get_powermeter_watts()
    mock_pm.get_powermeter_watts.side_effect = ValueError("down")

    clock.now += 4.0
    assert await throttled.get_powermeter_watts() == [50.0]
    clock.now += 2.0
    with pytest.raises(ValueError):
        await throttled.get_powermeter_watts()


async def test_recovery_restarts_the_grace_window() -> None:
    clock = _FakeClock()
    mock_pm = _failing_after_one_read([10.0])
    throttled = ThrottledPowermeter(mock_pm, throttle_interval=3.0, clock=clock)

    await throttled.get_powermeter_watts()
    mock_pm.get_powermeter_watts.side_effect = ValueError("down")
    clock.now += 3.0
    assert await throttled.get_powermeter_watts() == [10.0]

    mock_pm.get_powermeter_watts.side_effect = None
    mock_pm.get_powermeter_watts.return_value = [20.0]
    clock.now += 3.0
    assert await throttled.get_powermeter_watts() == [20.0]

    mock_pm.get_powermeter_watts.side_effect = ValueError("down again")
    clock.now += 6.0
    assert await throttled.get_powermeter_watts() == [20.0]


async def test_failed_reads_are_logged_once_per_spell_not_once_per_poll(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A battery polls about once a second; one line per failed read buries the log."""
    clock = _FakeClock()
    mock_pm = _failing_after_one_read([100.0])
    throttled = ThrottledPowermeter(mock_pm, throttle_interval=3.0, clock=clock)

    await throttled.get_powermeter_watts()
    mock_pm.get_powermeter_watts.side_effect = ValueError("sensor has no state")

    caplog.set_level(logging.WARNING, logger="astrameter")
    for _ in range(4):
        clock.now += 1.0
        await throttled.get_powermeter_watts()

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "sensor has no state" in warnings[0].getMessage()
    # No traceback unless the user asked for one with LOG_LEVEL = DEBUG.
    # ``exc_info=False`` also opts the record out of the auto-exc-info filter
    # in ``config/logger.py``, which would otherwise attach one anyway.
    assert warnings[0].exc_info is False


async def test_the_end_of_the_grace_window_is_always_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    clock = _FakeClock()
    mock_pm = _failing_after_one_read([100.0])
    throttled = ThrottledPowermeter(mock_pm, throttle_interval=3.0, clock=clock)

    await throttled.get_powermeter_watts()
    mock_pm.get_powermeter_watts.side_effect = ValueError("sensor has no state")

    caplog.set_level(logging.INFO, logger="astrameter")
    clock.now += 1.0
    await throttled.get_powermeter_watts()
    # Well inside the 30 s log interval, but this is the transition the user
    # has to see: the meter stops answering here.
    clock.now += 6.0
    with pytest.raises(ValueError):
        await throttled.get_powermeter_watts()

    messages = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(messages) == 2
    assert "no longer" in messages[1]

    caplog.clear()
    mock_pm.get_powermeter_watts.side_effect = None
    clock.now += 3.0
    await throttled.get_powermeter_watts()
    assert any("recovered after" in r.getMessage() for r in caplog.records)
