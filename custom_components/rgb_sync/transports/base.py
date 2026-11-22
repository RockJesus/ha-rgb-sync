"""Transport abstraction for RGB Sync."""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from ..models import DeviceState

RGB = tuple[int, int, int]

_TOKEN = re.compile(r"{(on|state|brightness|brightness_pct|r|g|b|hex|effect|speed)}")


class TransportError(Exception):
    """Raised when a device cannot be reached."""


def render_payload(template: str, state: "DeviceState") -> str:
    """Render a payload template with the current device state.

    Only known ``{token}`` placeholders are replaced, so JSON bodies keep their
    literal braces.
    """
    values = {
        "on": 1 if state.on else 0,
        "state": "ON" if state.on else "OFF",
        "brightness": int(state.brightness),
        "brightness_pct": round(state.brightness / 255 * 100),
        "r": state.rgb[0],
        "g": state.rgb[1],
        "b": state.rgb[2],
        "hex": "#{:02x}{:02x}{:02x}".format(*state.rgb),
        "effect": state.effect,
        "speed": state.speed,
    }
    return _TOKEN.sub(lambda match: str(values[match.group(1)]), template)


def parse_hex(text: str) -> bytes:
    """Parse ``56 r g b 00 f0 aa`` style hex strings into bytes."""
    cleaned = (
        str(text)
        .replace("0x", " ")
        .replace("0X", " ")
        .replace(",", " ")
        .replace(":", " ")
        .replace("-", " ")
        .replace("\n", " ")
    )
    return bytes.fromhex(cleaned)


class BaseTransport:
    """Base class for all device transports."""

    min_interval: float = 0.2

    def __init__(self, hass: "HomeAssistant", device: dict[str, Any]) -> None:
        self.hass = hass
        self.device = device
        self.online = False
        self.last_error: str | None = None
        self.last_latency: float | None = None
        self._last_frame = 0.0

    @property
    def device_id(self) -> str:
        return str(self.device.get("id", ""))

    async def async_setup(self) -> None:
        """Prepare the transport (no network traffic required)."""

    async def async_probe(self) -> bool:
        """Check reachability and refresh capability data."""
        return False

    async def async_apply(self, state: "DeviceState") -> None:
        """Apply a static state (power / colour / effect selection)."""
        raise NotImplementedError

    async def async_frame(self, frame: list[RGB], state: "DeviceState") -> None:
        """Push one animation frame."""
        raise NotImplementedError

    async def async_close(self) -> None:
        """Release resources."""

    def _throttled(self) -> bool:
        now = time.monotonic()
        if now - self._last_frame < self.min_interval:
            return True
        self._last_frame = now
        return False

    def _mark_ok(self, latency: float | None = None) -> None:
        self.online = True
        self.last_error = None
        if latency is not None:
            self.last_latency = latency

    def _mark_error(self, error: Exception | str) -> None:
        self.online = False
        self.last_error = str(error)[:160]
