"""Transport factory and configuration validation."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from ..const import (
    NET_HTTP,
    PROTOCOL_BLE,
    PROTOCOL_MATTER,
    PROTOCOL_MQTT,
    PROTOCOL_NETWORK,
    PROTOCOL_WLED,
)
from .base import BaseTransport, TransportError
from .ble import BleTransport
from .matter import MatterTransport
from .mqtt import MqttTransport
from .network import NetworkTransport
from .wled import WledTransport


def create_transport(hass: HomeAssistant, device: dict[str, Any]) -> BaseTransport:
    """Build the transport matching ``device['protocol']``."""
    protocol = device.get("protocol")
    if protocol == PROTOCOL_WLED:
        return WledTransport(hass, device)
    if protocol == PROTOCOL_NETWORK:
        return NetworkTransport(hass, device)
    if protocol == PROTOCOL_BLE:
        return BleTransport(hass, device)
    if protocol == PROTOCOL_MATTER:
        return MatterTransport(hass, device)
    if protocol == PROTOCOL_MQTT:
        return MqttTransport(hass, device)
    raise TransportError(f"unsupported protocol {protocol}")


async def async_validate_device(hass: HomeAssistant, device: dict[str, Any]) -> str | None:
    """Validate a device definition; returns an error key or ``None``."""
    try:
        transport = create_transport(hass, device)
        await transport.async_setup()
    except TransportError:
        return "invalid_device"

    try:
        if device.get("protocol") in (PROTOCOL_BLE, PROTOCOL_MATTER):
            # BLE peripherals and Matter bulbs can be asleep; the definition is
            # valid once the target exists, runtime probes report reachability.
            return None
        if device.get("protocol") == PROTOCOL_NETWORK and device.get("net_protocol") != NET_HTTP:
            return None
        if await transport.async_probe():
            return None
        return "cannot_connect"
    finally:
        await transport.async_close()


__all__ = ["create_transport", "async_validate_device", "TransportError"]
