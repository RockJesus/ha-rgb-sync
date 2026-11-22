"""MQTT transport: publish device state to a topic."""

from __future__ import annotations

import dataclasses
import time
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntryState

from ..const import DEFAULT_MQTT_BODY
from .base import BaseTransport, TransportError, render_payload

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from ..models import DeviceState

RGB = tuple[int, int, int]


def mqtt_client_ready(hass: "HomeAssistant") -> bool:
    """Return True when the MQTT integration is configured and loaded."""
    return any(
        entry.state is ConfigEntryState.LOADED for entry in hass.config_entries.async_entries("mqtt")
    )


class MqttTransport(BaseTransport):
    """Publish JSON payloads on MQTT for bridges and DIY controllers."""

    min_interval = 0.15

    def __init__(self, hass: "HomeAssistant", device: dict[str, Any]) -> None:
        super().__init__(hass, device)
        self.topic = str(device.get("topic", "")).strip()
        self.qos = int(device.get("qos") or 0)
        self.retain = bool(device.get("retain", False))
        self.body = str(device.get("body") or DEFAULT_MQTT_BODY)

    async def async_setup(self) -> None:
        if not self.topic:
            raise TransportError("MQTT topic is empty")
        if any(char in self.topic for char in ("+", "#")):
            raise TransportError("MQTT topic must not contain wildcards")
        if not self.qos in (0, 1, 2):
            raise TransportError("MQTT QoS must be 0, 1 or 2")
        if not mqtt_client_ready(self.hass):
            raise TransportError("MQTT is not configured in Home Assistant")

    async def async_probe(self) -> bool:
        ready = mqtt_client_ready(self.hass)
        self.online = ready
        return ready

    async def _async_publish(self, state: "DeviceState", rgb: RGB | None = None) -> None:
        from homeassistant.components import mqtt

        payload_state = state if rgb is None else dataclasses.replace(state, rgb=rgb)
        payload = render_payload(self.body, payload_state)
        await mqtt.async_publish(self.hass, self.topic, payload, self.qos, self.retain)

    async def async_apply(self, state: "DeviceState") -> None:
        started = time.monotonic()
        try:
            await self._async_publish(state)
        except Exception as err:  # noqa: BLE001 - broker may be offline
            self._mark_error(err)
            raise TransportError(str(err)) from err
        self._mark_ok(time.monotonic() - started)

    async def async_frame(self, frame: list[RGB], state: "DeviceState") -> None:
        if not state.on or not frame:
            return
        if self._throttled():
            return
        try:
            await self._async_publish(state, rgb=frame[0])
        except Exception as err:  # noqa: BLE001
            self._mark_error(err)


__all__ = ["MqttTransport"]
