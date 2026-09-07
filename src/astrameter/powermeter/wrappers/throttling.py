import asyncio
import logging
import time
from collections.abc import Callable

from astrameter.powermeter.base import Powermeter

from .base import PowermeterWrapper

# Stdlib logger: avoid importing astrameter.config (config_loader imports powermeter).
logger = logging.getLogger("astrameter")

#: How many refresh cycles the last good reading may cover for once a read
#: starts failing.  One missed refresh is a hiccup worth riding out; a source
#: that keeps failing is an outage, and the consumer has to hear about it
#: rather than keep steering on a value that only gets older.
STALE_CACHE_CYCLES = 2

#: Floor under that window, so a sub-second throttle doesn't turn a single
#: slow read into an outage.
MIN_STALE_CACHE_SECONDS = 5.0

#: While reads keep failing, log at most one line per this many seconds.  A
#: CT002 battery polls about once a second, so an unthrottled line per failure
#: would bury the log during an outage.
FAILURE_LOG_INTERVAL_SECONDS = 30.0


class ThrottledPowermeter(PowermeterWrapper):
    """
    A wrapper around powermeter that throttles the rate of value fetching.

    This helps prevent control instability when using slow data sources by
    enforcing a minimum interval between power meter readings. When called
    too frequently, it waits for the remaining time before fetching fresh
    values, ensuring the storage always receives relatively fresh data at
    a controlled rate.

    A failed read is covered by the last good reading for a bounded grace
    window (see :data:`STALE_CACHE_CYCLES`) and then propagates. Serving the
    cache indefinitely would hide a meter outage from the layers built to
    handle one — CT002's ``before_send`` sends a zero adjustment so batteries
    hold their output instead of re-driving control from a stale reading, and
    it can only do that if the read actually fails.
    """

    def __init__(
        self,
        wrapped_powermeter: Powermeter,
        throttle_interval: float = 0.0,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        super().__init__(wrapped_powermeter)
        self.throttle_interval = throttle_interval
        self._clock = clock or time.monotonic
        self._stale_cache_window = max(
            STALE_CACHE_CYCLES * throttle_interval, MIN_STALE_CACHE_SECONDS
        )

        # Coalescing fetch pattern: when a fetch is in flight (including the
        # throttle sleep), concurrent callers await the same future so every
        # consumer gets fresh data without hammering the source.
        self._last_update_time: float | None = None
        self._last_values: list[float] | None = None
        self._pending_fetch: asyncio.Future[list[float]] | None = None
        # Age of the cached values is measured from the read that produced
        # them, not from _last_update_time — that one also moves on failure,
        # to keep the throttle from hammering a failing source.
        self._last_success_time: float | None = None
        self._failure_count = 0
        self._last_failure_log: float | None = None
        self._logged_serving_cache = False

    async def get_powermeter_watts_raw(self) -> list[float]:
        # Raw reads skip throttle coalescing so the Marstek app can show sensor-level
        # watts without being tied to the CT002 control cadence.
        return await self.wrapped_powermeter.get_powermeter_watts_raw()

    async def get_powermeter_watts(self) -> list[float]:
        if self.throttle_interval <= 0:
            return await self.wrapped_powermeter.get_powermeter_watts()

        # If a fetch (including its throttle sleep) is already in progress,
        # coalesce: wait for the same result so every consumer gets fresh
        # data from the same read.
        if self._pending_fetch is not None:
            return list(await asyncio.shield(self._pending_fetch))

        # We are the leader — other callers that arrive while we sleep or
        # fetch will coalesce behind our future.
        self._pending_fetch = asyncio.get_running_loop().create_future()
        try:
            if self._last_update_time is not None:
                now = self._clock()
                remaining = self.throttle_interval - (now - self._last_update_time)
            else:
                remaining = 0.0
            if remaining > 0:
                logger.debug(
                    "Throttling: Waiting %.1fs before fetching fresh values...",
                    remaining,
                )
                await asyncio.sleep(remaining)

            values = await self.wrapped_powermeter.get_powermeter_watts()
            self._last_values = values
            self._last_update_time = self._clock()
            self._last_success_time = self._last_update_time
            self._note_recovery()
            logger.debug("Throttling: Fetched fresh values: %s", values)
            self._pending_fetch.set_result(values)
            return list(values)
        except (asyncio.CancelledError, KeyboardInterrupt, SystemExit):
            if not self._pending_fetch.done():
                self._pending_fetch.cancel()
            raise
        except Exception as e:
            # Update timestamp even on failure so we respect the throttle
            # interval before retrying — avoids hammering a failing source.
            now = self._clock()
            self._last_update_time = now
            if self._cache_still_covers(now):
                self._note_failure(now, e, serving_cache=True)
                assert self._last_values is not None
                logger.debug(
                    "Throttling: Using cached values due to error: %s",
                    self._last_values,
                )
                cached = list(self._last_values)
                if not self._pending_fetch.done():
                    self._pending_fetch.set_result(cached)
                return cached
            self._note_failure(now, e, serving_cache=False)
            # Past the grace window the cache is no longer an answer: drop it
            # so a later failure can't resurrect a reading from before the
            # outage, and let the error through to the consumer.
            self._last_values = None
            self._last_success_time = None
            if not self._pending_fetch.done():
                self._pending_fetch.set_exception(e)
            raise
        finally:
            self._pending_fetch = None

    def _cache_still_covers(self, now: float) -> bool:
        """Whether the cached reading is young enough to stand in for a failed read."""
        if self._last_values is None or self._last_success_time is None:
            return False
        return (now - self._last_success_time) <= self._stale_cache_window

    def _note_failure(self, now: float, exc: Exception, *, serving_cache: bool) -> None:
        """Log a failed read, at most once per :data:`FAILURE_LOG_INTERVAL_SECONDS`.

        The moment the grace window runs out is always logged, however recently
        the previous line went out: that is when the consumer stops getting a
        reading, which is the part the user has to see.
        """
        self._failure_count += 1
        due = (
            self._last_failure_log is None
            or serving_cache != self._logged_serving_cache
            or now - self._last_failure_log >= FAILURE_LOG_INTERVAL_SECONDS
        )
        if not due:
            return
        self._last_failure_log = now
        self._logged_serving_cache = serving_cache
        if serving_cache:
            logger.warning(
                "Throttling: Error getting fresh values (%d in a row): %s. "
                "Serving the last reading for up to %.0fs.",
                self._failure_count,
                exc,
                self._stale_cache_window,
                exc_info=logger.isEnabledFor(logging.DEBUG),
            )
        else:
            logger.warning(
                "Throttling: Error getting fresh values (%d in a row): %s. "
                "The last reading is older than %.0fs, so it is no longer "
                "served — the powermeter now reads as unavailable.",
                self._failure_count,
                exc,
                self._stale_cache_window,
                exc_info=logger.isEnabledFor(logging.DEBUG),
            )

    def _note_recovery(self) -> None:
        if self._failure_count == 0:
            return
        logger.info(
            "Throttling: Powermeter recovered after %d consecutive failures",
            self._failure_count,
        )
        self._failure_count = 0
        self._last_failure_log = None
        self._logged_serving_cache = False
