import json
import threading
import time
from typing import Union, List

import websocket

from .base import Powermeter
from config.logger import logger


class HomeAssistant(Powermeter):
    def __init__(
        self,
        ip: str,
        port: str,
        use_https: bool,
        access_token: str,
        current_power_entity: Union[str, List[str]],
        power_calculate: bool,
        power_input_alias: Union[str, List[str]],
        power_output_alias: Union[str, List[str]],
        path_prefix: str,
    ):
        self.ip = ip
        self.port = port
        self.use_https = use_https
        self.access_token = access_token
        self.current_power_entity = (
            [current_power_entity]
            if isinstance(current_power_entity, str)
            else current_power_entity
        )
        self.power_calculate = power_calculate
        self.power_input_alias = (
            [power_input_alias]
            if isinstance(power_input_alias, str)
            else power_input_alias
        )
        self.power_output_alias = (
            [power_output_alias]
            if isinstance(power_output_alias, str)
            else power_output_alias
        )
        self.path_prefix = path_prefix

        self._lock = threading.Lock()
        self._entity_values = {}
        self._tracked_entities = self._collect_entities()
        self._msg_id = 0
        self._get_states_id = None

        url = self._build_ws_url()
        self.ws = websocket.WebSocketApp(
            url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )

        thread = threading.Thread(
            target=self.ws.run_forever,
            kwargs={"reconnect": 5},
            daemon=True,
        )
        thread.start()

    def _collect_entities(self) -> set:
        if self.power_calculate:
            entities = list(self.power_input_alias) + list(self.power_output_alias)
        else:
            entities = list(self.current_power_entity)
        return {e for e in entities if e}

    def _build_ws_url(self) -> str:
        scheme = "wss" if self.use_https else "ws"
        prefix = self.path_prefix or ""
        return f"{scheme}://{self.ip}:{self.port}{prefix}/api/websocket"

    def _next_id(self) -> int:
        self._msg_id += 1
        return self._msg_id

    def _on_open(self, ws):
        logger.info(f"Home Assistant WebSocket connected to {self.ip}")

    def _on_message(self, ws, message):
        try:
            msg = json.loads(message)
        except json.JSONDecodeError:
            logger.error(f"Home Assistant: failed to decode message: {message}")
            return

        msg_type = msg.get("type")

        if msg_type == "auth_required":
            ws.send(json.dumps({"type": "auth", "access_token": self.access_token}))
        elif msg_type == "auth_ok":
            logger.info("Home Assistant: authenticated")
            self._get_states_id = self._next_id()
            ws.send(json.dumps({"id": self._get_states_id, "type": "get_states"}))
            subscribe_id = self._next_id()
            ws.send(
                json.dumps(
                    {
                        "id": subscribe_id,
                        "type": "subscribe_trigger",
                        "trigger": {
                            "platform": "state",
                            "entity_id": sorted(self._tracked_entities),
                        },
                    }
                )
            )
        elif msg_type == "auth_invalid":
            logger.error(f"Home Assistant auth failed: {msg.get('message', '')}")
        elif msg_type == "result":
            if msg.get("id") == self._get_states_id:
                if msg.get("success"):
                    self._handle_states(msg.get("result", []))
                else:
                    logger.error(
                        f"Home Assistant get_states failed: {msg.get('error')}"
                    )
        elif msg_type == "event":
            event = msg.get("event", {})
            trigger = event.get("variables", {}).get("trigger", {})
            to_state = trigger.get("to_state")
            if to_state:
                entity_id = to_state.get("entity_id")
                if entity_id in self._tracked_entities:
                    self._update_entity_value(entity_id, to_state.get("state"))

    def _handle_states(self, states):
        for state in states:
            entity_id = state.get("entity_id")
            if entity_id in self._tracked_entities:
                self._update_entity_value(entity_id, state.get("state"))

    def _update_entity_value(self, entity_id, state_val):
        if state_val is None:
            with self._lock:
                self._entity_values[entity_id] = None
            return
        try:
            value = float(state_val)
            with self._lock:
                self._entity_values[entity_id] = value
        except (ValueError, TypeError):
            logger.warning(
                f"Home Assistant sensor {entity_id} state"
                f" '{state_val}' is not numeric"
            )
            with self._lock:
                self._entity_values[entity_id] = None

    def _get_entity_value(self, entity_id) -> float:
        """Return cached value for entity. Caller must hold self._lock."""
        val = self._entity_values.get(entity_id)
        if val is None:
            raise ValueError(f"Home Assistant sensor {entity_id} has no state")
        return val

    def _on_error(self, ws, error):
        logger.error(f"Home Assistant WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        logger.info(
            f"Home Assistant WebSocket closed:" f" {close_status_code} {close_msg}"
        )

    def get_powermeter_watts(self):
        with self._lock:
            if not self.power_calculate:
                return [
                    self._get_entity_value(entity)
                    for entity in self.current_power_entity
                ]
            else:
                if len(self.power_input_alias) != len(self.power_output_alias):
                    raise ValueError(
                        "Home Assistant power_input_alias and"
                        " power_output_alias lengths differ"
                    )
                results = []
                for in_entity, out_entity in zip(
                    self.power_input_alias, self.power_output_alias
                ):
                    power_in = self._get_entity_value(in_entity)
                    power_out = self._get_entity_value(out_entity)
                    results.append(power_in - power_out)
                return results

    def wait_for_message(self, timeout=5):
        start_time = time.time()
        while True:
            with self._lock:
                if all(
                    self._entity_values.get(e) is not None
                    for e in self._tracked_entities
                ):
                    return
            if time.time() - start_time > timeout:
                raise TimeoutError("Timeout waiting for Home Assistant state")
            time.sleep(0.1)
