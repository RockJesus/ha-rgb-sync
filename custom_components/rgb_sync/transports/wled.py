"""WLED transport: HTTP JSON for persistent state, UDP DRGB for live frames."""

from __future__ import annotations

import asyncio
import json
import socket
import time
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ..const import WLED_REQUEST_TIMEOUT, WLED_UDP_PORT, WLED_UDP_TIMEOUT
from .base import BaseTransport, TransportError

if TYPE_CHECKING:
    from ..models import DeviceState

RGB = tuple[int, int, int]


class WledTransport(BaseTransport):
    """Controls a WLED instance over its local JSON API."""

    min_interval = 0.04

    def __init__(self, hass: Any, device: dict[str, Any]) -> None:
        super().__init__(hass, device)
        self.host = str(device.get("host", "")).strip()
        self.port = int(device.get("port") or 80)
        self.udp_port = int(device.get("udp_port") or WLED_UDP_PORT)
        self.pixel_count = max(1, int(device.get("pixels") or 1))
        self.version = ""
        self._sock: socket.socket | None = None
        self._udp_ok = True
        self._http_fps = 5.0
        self._last_http_frame = 0.0

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    async def async_setup(self) -> None:
        if not self.host:
            raise TransportError("WLED host is empty")
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setblocking(False)
        except OSError:  # pragma: no cover - platform dependent
            self._sock = None
            self._udp_ok = False

    async def async_probe(self) -> bool:
        started = time.monotonic()
        try:
            session = async_get_clientsession(self.hass)
            async with session.get(
                f"{self.base_url}/json/info",
                timeout=WLED_REQUEST_TIMEOUT,
            ) as response:
                if response.status != 200:
                    raise TransportError(f"HTTP {response.status}")
                info = await response.json(content_type=None)
        except Exception as err:  # noqa: BLE001 - transport keeps running
            self._mark_error(err)
            return False

        leds = info.get("leds") or {}
        try:
            count = int(leds.get("count") or 0)
        except (TypeError, ValueError):
            count = 0
        if count > 0:
            self.pixel_count = count
        self.version = str(info.get("ver") or info.get("version") or "")
        self._mark_ok(time.monotonic() - started)
        return True

    def _state_payload(self, state: "DeviceState", *, brightness: int | None = None) -> dict[str, Any]:
        if not state.on:
            return {"on": False, "transition": 0}
        return {
            "on": True,
            "bri": state.brightness if brightness is None else brightness,
            "transition": 0,
            "seg": [
                {
                    "id": 0,
                    "on": True,
                    "fx": 0,
                    "col": [[state.rgb[0], state.rgb[1], state.rgb[2]]],
                }
            ],
        }

    async def _async_post_state(self, payload: dict[str, Any]) -> None:
        session = async_get_clientsession(self.hass)
        async with session.post(
            f"{self.base_url}/json/state",
            data=json.dumps(payload),
            timeout=WLED_REQUEST_TIMEOUT,
        ) as response:
            await response.read()
            if response.status >= 400:
                raise TransportError(f"HTTP {response.status}")

    async def async_apply(self, state: "DeviceState") -> None:
        try:
            await self._async_post_state(self._state_payload(state))
        except Exception as err:  # noqa: BLE001
            self._mark_error(err)
            raise TransportError(str(err)) from err
        self._mark_ok()

    async def async_frame(self, frame: list[RGB], state: "DeviceState") -> None:
        if not state.on or not frame:
            return
        if self._throttled():
            return
        pixels = self._expand(frame)
        if self._udp_ok and self._sock is not None:
            packet = bytes([1, WLED_UDP_TIMEOUT])
            packet += b"".join(bytes((red, green, blue)) for red, green, blue in pixels)
            try:
                await self.hass.loop.sock_sendto(self._sock, packet, (self.host, self.udp_port))
                self._mark_ok()
                return
            except Exception as err:  # noqa: BLE001 - fall back to HTTP frames
                self._udp_ok = False
                self.last_error = f"UDP fallback: {err}"
        await self._async_http_frame(frame, state)

    def _expand(self, frame: list[RGB]) -> list[RGB]:
        if len(frame) >= self.pixel_count:
            return frame[: self.pixel_count]
        return [frame[index % len(frame)] for index in range(self.pixel_count)]

    async def _async_http_frame(self, frame: list[RGB], state: "DeviceState") -> None:
        now = time.monotonic()
        if now - self._last_http_frame < 1 / self._http_fps:
            return
        self._last_http_frame = now
        red, green, blue = frame[len(frame) // 2]
        try:
            await self._async_post_state(
                {
                    "on": True,
                    "bri": 255,
                    "transition": 0,
                    "seg": [{"id": 0, "on": True, "fx": 0, "col": [[red, green, blue]]}],
                }
            )
        except Exception as err:  # noqa: BLE001
            self._mark_error(err)

    async def async_close(self) -> None:
        if self._sock is not None:
            self._sock.close()
            self._sock = None
        await asyncio.sleep(0)
