from typing import List
import time
import requests

from .base import Powermeter


class TQEnergyManager(Powermeter):
    """Powermeter using the TQ Energy Manager JSON API."""

    # OBIS codes
    _TOTAL_TO_GRID = 0
    _TOTAL_FROM_GRID = 1
    _TOTAL_KEYS = (
        "1-0:1.4.0*255",  # Σ active power (from grid)
        "1-0:2.4.0*255",  # Σ active power (to grid)
    )

    _TOTAL_TO_GRID_L1 = 0
    _TOTAL_FROM_GRID_L1 = 1
    _TOTAL_TO_GRID_L2 = 2
    _TOTAL_FROM_GRID_L2 = 3
    _TOTAL_TO_GRID_L3 = 4
    _TOTAL_FROM_GRID_L3 = 5
    _PHASE_KEYS = (
        "1-0:21.4.0*255",  # L1 active power (from grid)
        "1-0:22.4.0*255",  # L1 active power (to grid)
        "1-0:41.4.0*255",  # L2 active power (from grid)
        "1-0:42.4.0*255",  # L2 active power (to grid)
        "1-0:61.4.0*255",  # L3 active power (from grid)
        "1-0:62.4.0*255",  # L3 active power (to grid)
    )

    _MAX_IDLE = 60 * 30  # 30 min

    def __init__(self, host: str, password: str = "", *, timeout: float = 5.0) -> None:
        self._host, self._pw, self._timeout = host.rstrip("/"), password, timeout
        self._sess = requests.Session()
        self._serial: str | None = None
        self._last_use = 0.0

    # ------------------------------------------------------------------ #
    # PUBLIC                                                             #
    # ------------------------------------------------------------------ #
    def get_powermeter_watts(self) -> List[float]:
        self._ensure_session()

        try:
            data = self._read_live_json()
        except _SessionExpired:
            self._login()
            data = self._read_live_json()

        if any(k in data for k in self._PHASE_KEYS):
            return [
                float(data.get(self._PHASE_KEYS[self._TOTAL_TO_GRID_L1], 0))
                - float(data.get(self._PHASE_KEYS[self._TOTAL_FROM_GRID_L1], 0)),
                float(data.get(self._PHASE_KEYS[self._TOTAL_TO_GRID_L2], 0))
                - float(data.get(self._PHASE_KEYS[self._TOTAL_FROM_GRID_L2], 0)),
                float(data.get(self._PHASE_KEYS[self._TOTAL_TO_GRID_L3], 0))
                - float(data.get(self._PHASE_KEYS[self._TOTAL_FROM_GRID_L3], 0)),
            ]

        if any(k in data for k in self._TOTAL_KEYS):
            return [
                float(data.get(self._TOTAL_KEYS[self._TOTAL_TO_GRID], 0))
                - float(data.get(self._TOTAL_KEYS[self._TOTAL_FROM_GRID], 0))
            ]

        raise RuntimeError("Required OBIS values missing in payload")

    # ------------------------------------------------------------------ #
    # INTERNALS                                                          #
    # ------------------------------------------------------------------ #
    def _ensure_session(self) -> None:
        now = time.time()
        if self._serial is None or (now - self._last_use) > self._MAX_IDLE:
            self._login()
        self._last_use = now

    def _login(self) -> None:
        """Authenticate lazily with the device."""
        r1 = self._sess.get(f"http://{self._host}/start.php", timeout=self._timeout)
        r1.raise_for_status()
        j1 = r1.json()

        self._serial = j1.get("serial") or j1.get("ieq_serial")
        if not self._serial:
            raise RuntimeError("Serial number missing in /start.php response")

        if j1.get("authentication") is True:
            return

        payload = {"login": self._serial, "save_login": 1}
        if self._pw:
            payload["password"] = self._pw

        r2 = self._sess.post(
            f"http://{self._host}/start.php", data=payload, timeout=self._timeout
        )
        r2.raise_for_status()
        if r2.json().get("authentication") is not True:
            raise RuntimeError("Authentication failed")

    def _read_live_json(self) -> dict:
        r = self._sess.get(
            f"http://{self._host}/mum-webservice/data.php", timeout=self._timeout
        )
        if r.status_code in (401, 403):
            raise _SessionExpired

        r.raise_for_status()
        data = r.json()
        if data.get("status", 0) >= 900:
            raise _SessionExpired
        return data


class _SessionExpired(RuntimeError):
    """Internal marker – triggers transparent re-login."""

    pass
