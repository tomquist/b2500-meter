import datetime
import threading
from dataclasses import dataclass, field

import serial
import smllib.errors
from smllib import SmlFrame, SmlStreamReader
from smllib.const import UNITS

from config.logger import logger

from .base import Powermeter

# from smllib:const.py
_OBIS_POWER_CURRENT = "0100100700ff"
_OBIS_POWER_IN_TOTAL = "0100010800ff"
_OBIS_POWER_OUT_TOTAL = "0100020800ff"


@dataclass
class EnergyStats:
    current_power: int = 0
    total_power_in: int = 0
    total_power_out: int = 0
    when: datetime.datetime = field(default_factory=datetime.datetime.now)

    @classmethod
    def from_sml_frame(cls, sml_frame: SmlFrame) -> "EnergyStats":
        stats = cls()
        for ov in sml_frame.get_obis():
            if ov.obis == _OBIS_POWER_CURRENT:
                stats.current_power = ov.value
                assert UNITS[ov.unit] == "W"
            elif ov.obis == _OBIS_POWER_IN_TOTAL:
                stats.total_power_in = ov.value
                assert UNITS[ov.unit] == "Wh"
            elif ov.obis == _OBIS_POWER_OUT_TOTAL:
                stats.total_power_out = ov.value
                assert UNITS[ov.unit] == "Wh"
        stats.when = datetime.datetime.now()
        return stats


class Sml(Powermeter):
    def __init__(self, serial_device: str = "/dev/ttyUSB0"):
        self._serial_device = serial_device
        self._current = EnergyStats()
        self._lock = threading.Lock()

    @property
    def current(self) -> EnergyStats:
        return self._current

    def get_powermeter_watts(self) -> list[float]:
        self.read_serial()
        return [self._current.current_power]

    def _try_read_frame(self, ser: serial.Serial, stream: SmlStreamReader) -> SmlFrame | None:
        try:
            sml_frame = stream.get_frame()
        except smllib.errors.CrcError as e:
            logger.debug("CRC error, keep reading: %s", e)
            sml_frame = None
        except Exception as e:
            logger.error("error reading frame: %s", e)
            sml_frame = None
        if sml_frame is None:
            data = ser.read(512)
            if not data:
                logger.error("serial read timed out")
                return None
            stream.add(data)
        return sml_frame

    def read_serial(self) -> None:
        if not self._lock.acquire(blocking=False):
            return
        try:
            stream = SmlStreamReader()
            with serial.Serial(self._serial_device, 9600, timeout=10) as ser:
                data = ser.read(512)
                stream.add(data)
                for i in range(10):
                    sml_frame = self._try_read_frame(ser, stream)
                    if sml_frame is not None:
                        self._current = EnergyStats.from_sml_frame(sml_frame)
                        logger.debug("got sml frame: %s after %s attemps", self._current, i)
                        return
                logger.error("failed to read SML frame after 10 attempts")
        finally:
            self._lock.release()
