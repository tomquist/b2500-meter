"""Shelly Gen2 HTTP RPC server for HA Shelly integration compatibility.

Serves the same endpoints as a real Shelly Pro 3EM device so the
Home Assistant Shelly integration can poll power data over HTTP.
"""

import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from config.logger import logger

SHELLY_MODEL = "SPEM-003CEBEU"
SHELLY_GEN = 2
SHELLY_APP = "Pro3EM"
SHELLY_FW_VER = "1.6.1-g8dbd358"
SHELLY_FW_ID = "20250508-110717/1.6.1-g8dbd358"
DEFAULT_VOLTAGE = 230.0
DEFAULT_FREQ = 50.0


def _phase_key(index):
    """Return phase letter for index: 0->a, 1->b, 2->c."""
    return chr(ord("a") + index)


def build_device_info(device_id, mac):
    """Build /shelly and Shelly.GetDeviceInfo response."""
    return {
        "name": "Shelly Pro 3EM Emulator",
        "id": device_id,
        "mac": mac,
        "slot": 0,
        "model": SHELLY_MODEL,
        "gen": SHELLY_GEN,
        "fw_id": SHELLY_FW_ID,
        "ver": SHELLY_FW_VER,
        "app": SHELLY_APP,
        "profile": "triphase",
        "auth_en": False,
        "auth_domain": None,
    }


def build_em_status(powers):
    """Build EM.GetStatus response from a list of phase power values."""
    while len(powers) < 3:
        powers = list(powers) + [0.0]

    result = {"id": 0}
    total_power = 0.0
    total_current = 0.0

    for i in range(3):
        key = _phase_key(i)
        power = round(float(powers[i]), 1)
        current = round(abs(power) / DEFAULT_VOLTAGE, 3) if power != 0 else 0.0
        pf = 1.0 if power != 0 else 0.0
        total_power += power
        total_current += current

        result[f"{key}_current"] = current
        result[f"{key}_voltage"] = DEFAULT_VOLTAGE
        result[f"{key}_act_power"] = power
        result[f"{key}_aprt_power"] = round(abs(power), 1)
        result[f"{key}_pf"] = pf
        result[f"{key}_freq"] = DEFAULT_FREQ

    result["n_current"] = 0.0
    result["total_current"] = round(total_current, 3)
    result["total_act_power"] = round(total_power, 1)
    result["total_aprt_power"] = round(abs(total_power), 1)
    result["user_calibrated_phase"] = []

    return result


def build_emdata_status():
    """Build EMData.GetStatus response (stub with zeros)."""
    result = {"id": 0}
    for i in range(3):
        key = _phase_key(i)
        result[f"{key}_total_act_energy"] = 0.0
        result[f"{key}_total_act_ret_energy"] = 0.0
    result["total_act"] = 0.0
    result["total_act_ret"] = 0.0
    return result


def build_shelly_status(powers, mac):
    """Build Shelly.GetStatus response."""
    return {
        "sys": {
            "mac": mac,
            "restart_required": False,
            "available_updates": {},
        },
        "em:0": build_em_status(powers),
        "emdata:0": build_emdata_status(),
    }


class ShellyHttpHandler(BaseHTTPRequestHandler):
    """HTTP handler for Shelly Gen2 RPC endpoints."""

    def do_GET(self):
        """Handle GET requests for Shelly RPC endpoints."""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        shelly = self.server.shelly_ref
        device_info = build_device_info(shelly.device_id, shelly.mac)

        if path in ("/shelly", "/rpc/Shelly.GetDeviceInfo"):
            self._json_response(device_info)
        elif path == "/rpc/EM.GetStatus":
            powers = shelly.get_powers()
            self._json_response(build_em_status(powers))
        elif path == "/rpc/EMData.GetStatus":
            self._json_response(build_emdata_status())
        elif path == "/rpc/Shelly.GetStatus":
            powers = shelly.get_powers()
            self._json_response(build_shelly_status(powers, shelly.mac))
        else:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error": "Not Found"}')

    def _json_response(self, data):
        """Send a JSON response with status 200."""
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        """Route HTTP logs through our logger at debug level."""
        logger.debug("Shelly HTTP: %s", format % args)


class ShellyHttpServer:
    """Threaded HTTP server for Shelly RPC endpoints."""

    def __init__(self, shelly_ref, port=80):
        self._port = port
        self._server = None
        self._thread = None
        self._shelly_ref = shelly_ref

    def start(self):
        """Start the HTTP server in a daemon thread."""
        self._server = HTTPServer(("", self._port), ShellyHttpHandler)
        self._server.shelly_ref = self._shelly_ref
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="ShellyHTTP",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "Shelly HTTP RPC server listening on port %d", self._port
        )

    def stop(self):
        """Stop the HTTP server."""
        if self._server:
            self._server.shutdown()
            self._server.server_close()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
