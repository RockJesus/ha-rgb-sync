"""WebSocket API for pushing audio levels from cards or browsers."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .engine import SyncEngine


@callback
def async_register_websocket(hass: HomeAssistant) -> None:
    """Register the WebSocket commands once."""
    store = hass.data.setdefault(DOMAIN, {})
    if store.get("websocket_registered"):
        return
    store["websocket_registered"] = True
    websocket_api.async_register_command(hass, ws_audio_level)
    websocket_api.async_register_command(hass, ws_info)


def _engines(hass: HomeAssistant) -> list[SyncEngine]:
    return [value for value in hass.data.get(DOMAIN, {}).values() if isinstance(value, SyncEngine)]


@websocket_api.websocket_command(
    {
        vol.Required("type"): "rgb_sync/audio_level",
        vol.Required("level"): vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
        vol.Optional("bands"): [vol.All(vol.Coerce(float), vol.Range(min=0, max=1))],
    }
)
@websocket_api.async_response
async def ws_audio_level(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Inject an audio level from a browser-based microphone analyser."""
    for engine in _engines(hass):
        await engine.async_audio_level(msg["level"], msg.get("bands"))
    connection.send_result(msg["id"])


@websocket_api.websocket_command({vol.Required("type"): "rgb_sync/info"})
@callback
def ws_info(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Return devices, states and hub flags for dashboards or cards."""
    entries = []
    for engine in _engines(hass):
        entries.append(
            {
                "title": engine.entry.title,
                "link": engine.link,
                "audio_reactive": engine.audio_reactive,
                "audio_level": round(engine.audio_level, 3),
                "fps": engine.fps,
                "scene": engine.scene,
                "devices": [
                    {
                        "id": device["id"],
                        "name": device.get("name"),
                        "protocol": device.get("protocol"),
                        "enabled": device.get("enabled", True),
                        "online": bool(
                            engine.transports.get(str(device["id"]))
                            and engine.transports[str(device["id"])].online
                        ),
                        "state": {
                            "on": engine.state(str(device["id"])).on,
                            "brightness": engine.state(str(device["id"])).brightness,
                            "rgb": list(engine.state(str(device["id"])).rgb),
                            "effect": engine.state(str(device["id"])).effect,
                        },
                    }
                    for device in engine.devices
                ],
            }
        )
    connection.send_result(msg["id"], {"entries": entries})
