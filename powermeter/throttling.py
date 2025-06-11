import time
import threading
from typing import List, Optional
from .base import Powermeter


class ThrottledPowermeter(Powermeter):
    """
    A wrapper around powermeter that throttles the rate of value fetching.

    This helps prevent control instability when using slow data sources by
    enforcing a minimum interval between power meter readings. When called
    too frequently, it waits for the remaining time before fetching fresh
    values, ensuring the storage always receives relatively fresh data at
    a controlled rate.
    """

    def __init__(self, wrapped_powermeter: Powermeter, throttle_interval: float = 0.0):
        """
        Initialize throttled powermeter wrapper.

        Args:
            wrapped_powermeter: The actual powermeter instance to wrap
            throttle_interval: Minimum time in seconds between value updates (0 = no throttling)
        """
        self.wrapped_powermeter = wrapped_powermeter
        self.throttle_interval = throttle_interval
        self.last_update_time = 0.0
        self.last_values: Optional[List[float]] = None
        self.lock = threading.Lock()

    def wait_for_message(self, timeout=5):
        """Pass through to wrapped powermeter."""
        return self.wrapped_powermeter.wait_for_message(timeout)

    def get_powermeter_watts(self) -> List[float]:
        with self.lock:
            current_time = time.time()

            # If throttling is disabled, always fetch fresh values
            if self.throttle_interval <= 0:
                values = self.wrapped_powermeter.get_powermeter_watts()
                self.last_values = values
                self.last_update_time = current_time
                return values

            # Check if enough time has passed since last update
            time_since_last_update = current_time - self.last_update_time

            if time_since_last_update < self.throttle_interval:
                # Not enough time has passed, wait for the remaining time
                wait_time = self.throttle_interval - time_since_last_update
                print(
                    f"Throttling: Waiting {wait_time:.1f}s before fetching fresh values..."
                )
                time.sleep(wait_time)
                current_time = time.time()  # Update current time after sleep

            # Time to get fresh values (either enough time passed or we waited)
            try:
                values = self.wrapped_powermeter.get_powermeter_watts()
                self.last_values = values
                self.last_update_time = current_time
                total_interval = current_time - (
                    self.last_update_time - time_since_last_update
                    if time_since_last_update < self.throttle_interval
                    else self.last_update_time
                )
                print(
                    f"Throttling: Fetched fresh values after {total_interval:.1f}s interval: {values}"
                )
                return values
            except Exception as e:
                print(f"Throttling: Error getting fresh values: {e}")
                # Fall back to cached values if available, otherwise re-raise
                if self.last_values is not None:
                    print(
                        f"Throttling: Using cached values due to error: {self.last_values}"
                    )
                    return self.last_values
                raise
