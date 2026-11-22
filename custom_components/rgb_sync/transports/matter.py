"""Matter transport: forwards state to an existing light entity."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from ..const import EFFECT_SOLID
from .base import BaseTransport, TransportError

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from ..models import DeviceState

RGB = tuple[int, int, int]


def _brightness_pct(brightness: int) -> int:
    return max(1, min(100, round(brightness / 255 * 100)))


class MatterTransport(BaseTransport):
    """Drive a Matter light through Home Assistant's light service.

    The Matter stack lives in Home Assistant itself; a Matter bulb is exposed
    as a regular ``light`` entity, so the transport mirrors our state onto it.
    """

    min_interval = 0.25

    def __init__(self, hass: "HomeAssistant", device: dict[str, Any]) -> None:
        super().__init__(hass, device)
        self.entity_id = str(device.get("entity_id", "")).strip().lower()

    async def async_setup(self) -> None:
        if not self.entity_id:
            raise TransportError("Matter entity is empty")
        state = self.hass.states.get(self.entity_id)
        if state is None:
            raise TransportError(f"Entity {self.entity_id} not found")
        if state.domain != "light":
            raise TransportError(f"{self.entity_id} is not a light entity")

    async def async_probe(self) -> bool:
        state = self.hass.states.get(self.entity_id)
        if state is None or state.state == "unavailable":
            self.online = False
            return False
        self._mark_ok()
        return True

    async def _async_turn_off(self) -> None:
        await self.hass.services.async_call(
            "light",
            "turn_off",
            {},
            target={"entity_id": self.entity_id},
            blocking=False,
        )

    async def _async_turn_on(self, rgb: RGB, brightness: int) -> None:
        data: dict[str, Any] = {"rgb_color": list(rgb)}
        if brightness > 0:
            data["brightness_pct"] = _brightness_pct(brightness)
        await self.hass.services.async_call(
            "light",
            "turn_on",
            data,
            target={"entity_id": self.entity_id},
            blocking=False,
        )

    async def async_apply(self, state: "DeviceState") -> None:
        started = time.monotonic()
        try:
            if not state.on:
                await self._async_turn_off()
            elif state.effect == EFFECT_SOLID:
                await self._async_turn_on(state.rgb, state.brightness)
            else:
                # Effects stream frames; applying once here keeps the base colour.
                await self._async_turn_on(state.rgb, state.brightness)
        except Exception as err:  # noqa: BLE001 - HA service errors
            self._mark_error(err)
            raise TransportError(str(err)) from err
        self._mark_ok(time.monotonic() - started)

    async def async_frame(self, frame: list[RGB], state: "DeviceState") -> None:
        if not state.on or not frame:
            return
        if self._throttled():
            return
        try:
            await self._async_turn_on(frame[0], state.brightness)
        except Exception as err:  # noqa: BLE001
            self._mark_error(err)
