"""Transport factory and configuration validation."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from ..const import PROTOCOL_BLE, PROTOCOL_NETWORK, PROTOCOL_WLED, NET_HTTP
from .base import BaseTransport, TransportError
from .ble import BleTransport
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
    raise TransportError(f"unsupported protocol {protocol}")


async def async_validate_device(hass: HomeAssistant, device: dict[str, Any]) -> str | None:
    """Validate a device definition; returns an error key or ``None``."""
    try:
        transport = create_transport(hass, device)
        await transport.async_setup()
    except TransportError:
        return "invalid_device"

    try:
        if device.get("protocol") == PROTOCOL_BLE:
            # BLE peripherals are often asleep while configuring; accept the
            # definition and let the runtime connection report reachability.
            return None
        if device.get("protocol") == PROTOCOL_NETWORK and device.get("net_protocol") != NET_HTTP:
            return None
        if await transport.async_probe():
            return None
        return "cannot_connect"
    finally:
        await transport.async_close()


__all__ = ["create_transport", "async_validate_device", "TransportError"]
