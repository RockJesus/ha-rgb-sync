"""Runtime models for RGB Sync."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .const import (
    DEFAULT_PIXELS,
    DEFAULT_SPEED,
    EFFECT_SOLID,
    PROTOCOL_NETWORK,
    PROTOCOL_WLED,
    CONF_PIXELS,
    CONF_ENABLED,
    CONF_NAME,
)


@dataclass
class DeviceState:
    """Desired state of one lighting device."""

    on: bool = False
    brightness: int = 255
    rgb: tuple[int, int, int] = (255, 255, 255)
    effect: str = EFFECT_SOLID
    speed: int = DEFAULT_SPEED
    palette: list[str] = field(default_factory=list)

    def as_light_kwargs(self) -> dict[str, Any]:
        return {
            "on": self.on,
            "brightness": self.brightness,
            "rgb": self.rgb,
            "effect": self.effect,
        }


def device_pixels(device: dict[str, Any]) -> int:
    """Return the configured pixel count for a device."""
    if device.get("protocol") in (PROTOCOL_WLED, PROTOCOL_NETWORK):
        try:
            return max(1, int(device.get(CONF_PIXELS, DEFAULT_PIXELS)))
        except (TypeError, ValueError):
            return DEFAULT_PIXELS
    return 1


def device_name(device: dict[str, Any]) -> str:
    """Return a human readable device name."""
    return str(device.get(CONF_NAME) or device.get("id") or "RGB")


def device_enabled(device: dict[str, Any]) -> bool:
    """Return whether a device takes part in synchronisation."""
    return bool(device.get(CONF_ENABLED, True))
