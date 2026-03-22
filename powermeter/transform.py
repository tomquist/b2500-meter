from typing import List
from .base import Powermeter


class TransformedPowermeter(Powermeter):
    """
    A wrapper around a powermeter that applies a linear transformation
    (multiplier and offset) to each returned power value.

    Formula per value: value * multiplier + offset

    Supports per-phase configuration: if a single multiplier/offset is given,
    it applies to all phases. If multiple values are given, each applies to
    the corresponding phase.
    """

    def __init__(self, wrapped_powermeter, offsets, multipliers):
        # type: (Powermeter, List[float], List[float]) -> None
        self.wrapped_powermeter = wrapped_powermeter
        self.offsets = offsets
        self.multipliers = multipliers

    def wait_for_message(self, timeout=5):
        return self.wrapped_powermeter.wait_for_message(timeout)

    def get_powermeter_watts(self):
        # type: () -> List[float]
        values = self.wrapped_powermeter.get_powermeter_watts()
        result = []
        for i, value in enumerate(values):
            multiplier = self.multipliers[i % len(self.multipliers)]
            offset = self.offsets[i % len(self.offsets)]
            result.append(value * multiplier + offset)

        if len(self.offsets) > 1 and len(self.offsets) != len(values):
            print(
                f"Warning: POWER_OFFSET has {len(self.offsets)} values but "
                f"powermeter returned {len(values)} phases"
            )
        if len(self.multipliers) > 1 and len(self.multipliers) != len(values):
            print(
                f"Warning: POWER_MULTIPLIER has {len(self.multipliers)} values but "
                f"powermeter returned {len(values)} phases"
            )

        return result
