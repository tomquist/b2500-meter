"""Shelly Gen2 HTTP RPC server for HA Shelly integration compatibility.

Serves the same endpoints as a real Shelly Pro 3EM device so the
Home Assistant Shelly integration can poll power data over HTTP.
Also provides a WebSocket JSON-RPC endpoint at /rpc with NotifyStatus
push notifications for real-time updates.

Uses FastAPI + uvicorn for native async WebSocket support.
"""

import asyncio
import json
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import uvicorn

from config.logger import logger

SHELLY_MODEL = "SPEM-003CEBEU"
SHELLY_GEN = 2
SHELLY_APP = "Pro3EM"
SHELLY_FW_VER = "1.6.1-g8dbd358"
SHELLY_FW_ID = "20250508-110717/1.6.1-g8dbd358"
DEFAULT_VOLTAGE = 230.0
DEFAULT_FREQ = 50.0
WS_NOTIFY_INTERVAL = 5  # seconds between NotifyStatus pushes


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


def build_shelly_config(mac):
    """Build Shelly.GetConfig response."""
    return {
        "em:0": {
            "id": 0,
            "name": None,
            "blink_mode_selector": "active_energy",
            "ct_type": "120A",
            "monitor_phase_sequence": False,
            "phase_selector": "all",
            "reverse": {},
        },
        "emdata:0": {},
        "sys": {
            "device": {
                "mac": mac,
                "name": "Shelly Pro 3EM Emulator",
                "fw_id": SHELLY_FW_ID,
                "profile": "triphase",
                "discoverable": True,
                "eco_mode": False,
                "addon_type": None,
            },
        },
    }


# ── FastAPI app builder ──────────────────────────────────────────────


def _build_app(shelly_ref):
    """Create the FastAPI app with all Shelly RPC routes."""

    @asynccontextmanager
    async def lifespan(app):
        yield

    app = FastAPI(lifespan=lifespan)
    app.state.shelly_ref = shelly_ref

    device_id = shelly_ref.device_id
    mac = shelly_ref.mac

    def _get_powers():
        """Get cached powers without blocking the event loop."""
        return shelly_ref.get_cached_powers()

    @app.get("/shelly")
    async def shelly_info():
        return build_device_info(device_id, mac)

    @app.get("/rpc/Shelly.GetDeviceInfo")
    async def get_device_info():
        return build_device_info(device_id, mac)

    @app.get("/rpc/Shelly.GetConfig")
    async def get_config():
        return build_shelly_config(mac)

    @app.get("/rpc/Shelly.GetStatus")
    async def get_status():
        powers = _get_powers()
        return build_shelly_status(powers, mac)

    @app.get("/rpc/EM.GetStatus")
    async def em_status():
        powers = _get_powers()
        return build_em_status(powers)

    @app.get("/rpc/EMData.GetStatus")
    async def emdata_status():
        return build_emdata_status()

    @app.get("/rpc/Shelly.GetComponents")
    async def get_components():
        return {"components": [], "cfg_rev": 0, "offset": 0, "total": 0}

    def _dispatch_method(method):
        """Dispatch an RPC method and return the result or None."""
        if method == "Shelly.GetDeviceInfo":
            return build_device_info(device_id, mac)
        if method == "Shelly.GetStatus":
            powers = _get_powers()
            return build_shelly_status(powers, mac)
        if method == "EM.GetStatus":
            powers = _get_powers()
            return build_em_status(powers)
        if method == "EMData.GetStatus":
            return build_emdata_status()
        if method == "Shelly.GetConfig":
            return build_shelly_config(mac)
        if method == "Shelly.GetComponents":
            return {"components": [], "cfg_rev": 0, "offset": 0, "total": 0}
        return None

    @app.websocket("/rpc")
    async def websocket_rpc(ws: WebSocket):
        """Shelly Gen2 JSON-RPC 2.0 over WebSocket with push notifications."""
        await ws.accept()
        logger.info("WebSocket /rpc: client connected")
        peer_src = ""

        async def _notify_loop():
            """Push NotifyStatus at regular intervals."""
            while True:
                await asyncio.sleep(WS_NOTIFY_INTERVAL)
                powers = _get_powers()
                em = build_em_status(powers)
                notification = {
                    "src": device_id,
                    "dst": peer_src,
                    "method": "NotifyStatus",
                    "params": {
                        "em:0": em,
                        "emdata:0": build_emdata_status(),
                    },
                }
                logger.debug(
                    "WebSocket push: NotifyStatus total_act_power=%.1f",
                    em.get("total_act_power", 0.0),
                )
                await ws.send_json(notification)

        notify_task = None
        try:
            while True:
                msg = await ws.receive_json()
                method = msg.get("method", "")
                msg_id = msg.get("id")
                src = msg.get("src", "")
                if src:
                    peer_src = src

                rpc_result = _dispatch_method(method)
                if rpc_result is not None:
                    logger.info("WebSocket RPC: %s id=%s -> ok", method, msg_id)
                    response = {
                        "id": msg_id,
                        "src": device_id,
                        "dst": src,
                        "result": rpc_result,
                    }
                else:
                    logger.info(
                        "WebSocket RPC: %s id=%s -> error(-114)", method, msg_id
                    )
                    response = {
                        "id": msg_id,
                        "src": device_id,
                        "dst": src,
                        "error": {
                            "code": -114,
                            "message": f"Method {method} failed: Method not found!",
                        },
                    }
                await ws.send_json(response)

                # Start push notifications after first successful exchange
                if notify_task is None:
                    notify_task = asyncio.create_task(_notify_loop())
        except WebSocketDisconnect:
            logger.info("WebSocket /rpc: client disconnected")
        except Exception as e:
            logger.info("WebSocket /rpc error: %s", e)
        finally:
            if notify_task is not None:
                notify_task.cancel()

    return app


class ShellyHttpServer:
    """Threaded HTTP server for Shelly RPC endpoints using uvicorn."""

    def __init__(self, shelly_ref, port=80):
        self._port = port
        self._shelly_ref = shelly_ref
        self._server = None
        self._thread = None

    def start(self):
        """Start the uvicorn server in a daemon thread."""
        app = _build_app(self._shelly_ref)
        config = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=self._port,
            log_level="warning",
        )
        self._server = uvicorn.Server(config)

        self._thread = threading.Thread(
            target=self._server.run,
            name="ShellyHTTP",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "Shelly HTTP RPC server listening on port %d", self._port
        )

    def stop(self):
        """Stop the uvicorn server."""
        if self._server:
            self._server.should_exit = True
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
