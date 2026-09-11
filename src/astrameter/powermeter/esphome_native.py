import asyncio
import logging
import math

import aioesphomeapi
from aioesphomeapi import EntityInfo, EntityState, SensorState
from aioesphomeapi.reconnect_logic import ReconnectLogic

from astrameter.power_units import POWER_UNIT_SCALE, POWER_UNITS

from .base import PushPowermeter

# Stdlib logger: avoid importing astrameter.config (config_loader imports powermeter).
logger = logging.getLogger("astrameter")


class ESPHomeNative(PushPowermeter):
    _TIMEOUT_MESSAGE = "Timeout waiting for ESPHome message"

    def __init__(
        self, address: str, port: str, api_key: str, object_id: str, client_info: str
    ) -> None:
        super().__init__()
        self.object_id = object_id
        self.address = address
        self.port = int(port)
        # address/port/password are positional in aioesphomeapi's APIClient
        # (older releases, e.g. the one pinned on Python 3.10, reject them as
        # keywords). Noise-encrypted devices don't use the password, so pass "".
        self.api = aioesphomeapi.APIClient(
            address,
            self.port,
            "",
            noise_psk=api_key,
            client_info=client_info,
            keepalive=5.0,  # Ping interval used to detect a dropped connection.
        )
        self.reconnect_logic = ReconnectLogic(
            client=self.api,
            on_connect=self.connect_callback,
            on_disconnect=self.disconnect_callback,
            on_connect_error=self.connect_error_callback,
        )
        self.last_value: float = 0
        self.entity_info: EntityInfo | None = None
        #: Declared unit of the subscribed sensor, read once per connection.
        #: ``None`` means the device declares none, which is assumed to be
        #: watts — what installs relied on before units were read.
        self._unit: str | None = None
        self.is_connected: bool = False
        # Set while the latest sensor state is valid; cleared on unavailability
        # and disconnect so a connected API cannot make stale data look healthy.
        self._any_message_event = asyncio.Event()
        logger.debug(
            "ESPHome native: %s:%s as %s, object id %s",
            address,
            port,
            client_info,
            self.object_id,
        )

    def reset_connection_state(self) -> None:
        self.is_connected = False
        self._any_message_event.clear()
        self._message_event.clear()
        self.entity_info = None
        # Re-read from the entity list on the next connect: the device may have
        # been reconfigured while we were away.
        self._unit = None

    async def start(self) -> None:
        await self.reconnect_logic.start()

    async def stop(self) -> None:
        await self.reconnect_logic.stop()
        await self.api.disconnect()
        self.reset_connection_state()

    async def connect_callback(self) -> None:
        self.is_connected = True
        logger.debug(
            "ESPHome native: connected to %s:%s, API version %s",
            self.address,
            self.port,
            self.api.api_version,
        )

        device_info = await self.api.device_info()
        logger.info(
            "ESPHome native: device %s runs ESPHome %s",
            device_info.name,
            device_info.esphome_version,
        )

        entity_infos, _ = await self.api.list_entities_services()

        for entity_info in entity_infos:
            if entity_info.object_id == self.object_id:
                self.entity_info = entity_info

        if self.entity_info is None:
            # Raising here would bubble up through ReconnectLogic's on_connect and
            # trigger an immediate reconnect + relist loop that never resolves the
            # misconfiguration. Stay connected instead and just log it clearly.
            logger.error(
                "ESPHome native: the device provides no object id %r; it offers %s",
                self.object_id,
                [e.object_id for e in entity_infos],
            )
            return

        logger.info(
            "ESPHome native: subscribing to %s (name %s, key %s)",
            self.entity_info.object_id,
            self.entity_info.name,
            self.entity_info.key,
        )
        self._read_unit(self.entity_info)
        self.api.subscribe_states(self.change_callback)

    def _read_unit(self, entity_info: EntityInfo) -> None:
        """Record the sensor's declared unit and say what it means for us.

        The native API carries ``unit_of_measurement`` on the entity, so a kW
        sensor is convertible rather than a silent factor of 1000 (issues #39 /
        #572) and a sensor that is not power at all can be named as the problem
        instead of steering the batteries with °C. Mirrors what the Home
        Assistant source does with the same attribute.
        """
        unit = getattr(entity_info, "unit_of_measurement", None)
        self._unit = unit if isinstance(unit, str) and unit else None
        if self._unit is None or self._unit == "W":
            return
        if self._unit in POWER_UNIT_SCALE:
            logger.info(
                "ESPHome native: sensor %s reports %s; converting to W automatically",
                entity_info.object_id,
                self._unit,
            )
        else:
            logger.error(
                "ESPHome native: sensor %s reports unit %r, which is not a "
                "power unit — expected one of %s. Its values will be rejected.",
                entity_info.object_id,
                self._unit,
                ", ".join(POWER_UNITS),
            )

    async def connect_error_callback(self, err: Exception) -> None:
        self.reset_connection_state()
        logger.error("ESPHome native: connection failed: %s", err)

    async def disconnect_callback(self, expected_disconnect: bool) -> None:
        self.reset_connection_state()

        if expected_disconnect:
            logger.info("Expected disconnect occurred")
        else:
            logger.warning("Unexpected disconnect. Trying to reconnect")

    def change_callback(self, state: EntityState) -> None:
        if self.entity_info is None:
            return

        if state.key != self.entity_info.key:
            return

        if not isinstance(state, SensorState):
            logger.error("ESPHome native: subscribed entity %s is not a sensor", state)
            return

        # An explicit unavailable state invalidates the old measurement even
        # while the API connection stays alive. Wake pending readers too: they
        # must see the outage instead of waiting and reusing the old value.
        if state.missing_state or not math.isfinite(state.state):
            self._any_message_event.clear()
            self._message_event.set()
            logger.debug("ESPHome native sensor is unavailable")
            return

        self.last_value = state.state
        self._message_event.set()
        self._any_message_event.set()
        logger.debug("ESPHome native: new sensor state %s", state.state)

    async def get_powermeter_watts(self) -> list[float]:
        if not self._any_message_event.is_set():
            return []
        return [self.last_value * self._unit_scale()]

    def _unit_scale(self) -> float:
        """Multiplier from the sensor's declared unit to watts.

        Raises when the sensor declares a unit that is not power: an empty
        reading would read as "meter unavailable" and hide the misconfiguration
        behind a transient-looking outage.
        """
        if self._unit is None:
            return 1.0
        scale = POWER_UNIT_SCALE.get(self._unit)
        if scale is None:
            raise ValueError(
                f"ESPHome native sensor {self.object_id} reports unit "
                f"{self._unit!r}, which is not a power unit — expected one of "
                f"{', '.join(POWER_UNITS)}"
            )
        return scale

    def stream_online(self) -> bool | None:
        return (
            self.is_connected
            and self._any_message_event.is_set()
            and (self._unit is None or self._unit in POWER_UNIT_SCALE)
        )

    async def wait_for_message(self, timeout: float = 5) -> None:
        await self._wait(self._any_message_event, timeout)
