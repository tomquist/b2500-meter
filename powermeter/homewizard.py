import json
import os
import ssl
import threading
import time

import websocket

from .base import Powermeter
from config.logger import logger

# Certificate: https://api-documentation.homewizard.com/assets/files/homewizard-ca-cert-56d062ef8e71d1038f464ea905d42fc6.pem
# Docs: https://api-documentation.homewizard.com/docs/v2/authorization#https
CA_CERT_PATH = os.path.join(os.path.dirname(__file__), "homewizard_ca.pem")


class HomeWizardPowermeter(Powermeter):
    def __init__(self, ip, token, serial):
        self.ip = ip
        self.token = token
        self.serial = serial
        self.values = None
        self._lock = threading.Lock()

        url = f"wss://{self.ip}/api/ws"
        self.ws = websocket.WebSocketApp(
            url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )

        sslopt = self._build_sslopt()
        thread = threading.Thread(
            target=self.ws.run_forever,
            kwargs={"reconnect": 5, "sslopt": sslopt},
            daemon=True,
        )
        thread.start()

    def _build_sslopt(self):
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_context.load_verify_locations(CA_CERT_PATH)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_REQUIRED
        return {
            "context": ssl_context,
            "server_hostname": f"appliance/p1dongle/{self.serial}",
        }

    def _on_open(self, ws):
        logger.info(f"HomeWizard WebSocket connected to {self.ip}")

    def _on_message(self, ws, message):
        try:
            msg = json.loads(message)
        except json.JSONDecodeError:
            logger.error(f"HomeWizard: failed to decode message: {message}")
            return

        msg_type = msg.get("type")
        if msg_type == "authorization_requested":
            ws.send(json.dumps({"type": "authorization", "data": self.token}))
        elif msg_type == "authorized":
            logger.info("HomeWizard: authorized, subscribing to measurements")
            ws.send(json.dumps({"type": "subscribe", "data": "measurement"}))
        elif msg_type == "measurement":
            data = msg.get("data", {})
            self._handle_measurement(data)
        elif msg_type == "error":
            error_data = msg.get("data", {})
            logger.error(f"HomeWizard error: {error_data.get('message', msg)}")
        else:
            logger.debug(f"HomeWizard: unknown message type: {msg_type}")

    def _handle_measurement(self, data):
        if "power_l1_w" in data:
            values = [
                data["power_l1_w"],
                data.get("power_l2_w", 0),
                data.get("power_l3_w", 0),
            ]
        elif "power_w" in data:
            values = [data["power_w"]]
        else:
            return

        with self._lock:
            self.values = values

    def _on_error(self, ws, error):
        logger.error(f"HomeWizard WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        logger.info(f"HomeWizard WebSocket closed:" f" {close_status_code} {close_msg}")

    def get_powermeter_watts(self):
        with self._lock:
            if self.values is not None:
                return list(self.values)
        raise ValueError("No value received from HomeWizard")

    def wait_for_message(self, timeout=5):
        start_time = time.time()
        while True:
            with self._lock:
                if self.values is not None:
                    return
            if time.time() - start_time > timeout:
                raise TimeoutError("Timeout waiting for HomeWizard measurement")
            time.sleep(1)
