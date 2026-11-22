"""Bluetooth Low Energy transport for BLE RGB controllers."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from ..const import (
    DEFAULT_BLE_CHAR_UUID,
    DEFAULT_BLE_SERVICE_UUID,
    DEFAULT_COLOR_TEMPLATE,
    DEFAULT_POWER_OFF_HEX,
    DEFAULT_POWER_ON_HEX,
    BLE_PROFILE_GENERIC,
)
from .base import BaseTransport, TransportError, parse_hex

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from ..models import DeviceState

RGB = tuple[int, int, int]


def normalise_uuid(value: str) -> str:
    """Expand a short 16-bit UUID to the full Bluetooth base UUID."""
    text = str(value).strip().lower()
    if len(text) == 4:
        return f"0000{text}-0000-1000-8000-00805f9b34fb"
    return text


def colour_bytes(template: str, rgb: RGB) -> bytes:
    """Render a BLE colour command template."""
    return parse_hex(template.format(r=rgb[0], g=rgb[1], b=rgb[2], hex="#{:02x}{:02x}{:02x}".format(*rgb)))


class BleTransport(BaseTransport):
    """Writes colour commands to a connectable BLE peripheral."""

    min_interval = 0.25

    def __init__(self, hass: "HomeAssistant", device: dict[str, Any]) -> None:
        super().__init__(hass, device)
        self.address = str(device.get("address", "")).strip().upper()
        self.profile = str(device.get("ble_profile") or "triones")
        self.service_uuid = normalise_uuid(device.get("service_uuid") or DEFAULT_BLE_SERVICE_UUID)
        self.char_uuid = normalise_uuid(device.get("char_uuid") or DEFAULT_BLE_CHAR_UUID)
        self.power_on = str(device.get("power_on_hex") or DEFAULT_POWER_ON_HEX)
        self.power_off = str(device.get("power_off_hex") or DEFAULT_POWER_OFF_HEX)
        self.color_template = str(device.get("color_template") or DEFAULT_COLOR_TEMPLATE)
        self._client: Any | None = None
        self._lock = asyncio.Lock()
        self._last_rgb: RGB | None = None
        self._powered: bool | None = None

    async def async_setup(self) -> None:
        if not self.address:
            raise TransportError("Bluetooth address is empty")
        if self.profile == BLE_PROFILE_GENERIC and not self.char_uuid:
            raise TransportError("generic profile requires a characteristic UUID")

    def _ble_device(self) -> Any | None:
        try:
            from homeassistant.components import bluetooth
        except ImportError:  # pragma: no cover - bluetooth always present in HA
            return None
        if "bluetooth" not in self.hass.config.components:
            return None
        return bluetooth.async_ble_device_from_address(self.hass, self.address, connectable=True)

    async def async_probe(self) -> bool:
        device = self._ble_device()
        if device is None:
            self._mark_error("BLE device not in range")
            return False
        self._mark_ok()
        return True

    async def _async_client(self) -> Any:
        from bleak import BleakClient

        if self._client is not None and getattr(self._client, "is_connected", False):
            return self._client
        device = self._ble_device()
        if device is None:
            raise TransportError("BLE device not in range")
        client = BleakClient(device, timeout=10, disconnected_callback=self._on_disconnect)
        await client.connect()
        services = getattr(client, "services", None)
        if services is not None:
            available = {str(service.uuid).lower() for service in services}
            if self.service_uuid not in available:
                await client.disconnect()
                raise TransportError(f"service {self.service_uuid} not found")
        self._client = client
        self._powered = None
        return client

    def _on_disconnect(self, _client: Any) -> None:
        self._client = None
        self._powered = None
        self.online = False

    async def _write(self, payload: bytes) -> None:
        async with self._lock:
            client = await self._async_client()
            await client.write_gatt_char(self.char_uuid, payload, response=False)

    async def async_apply(self, state: "DeviceState") -> None:
        rgb = self._scaled(state)
        try:
            if not state.on:
                await self._write(parse_hex(self.power_off))
                self._powered = False
                self._last_rgb = rgb
            else:
                if not self._powered:
                    await self._write(parse_hex(self.power_on))
                    self._powered = True
                await self._write(colour_bytes(self.color_template, rgb))
                self._last_rgb = rgb
        except Exception as err:  # noqa: BLE001
            self._mark_error(err)
            raise TransportError(str(err)) from err
        self._mark_ok()

    async def async_frame(self, frame: list[RGB], state: "DeviceState") -> None:
        if not state.on or not frame or self._throttled():
            return
        rgb = frame[len(frame) // 2]
        if rgb == self._last_rgb:
            return
        try:
            await self._write(colour_bytes(self.color_template, rgb))
        except Exception as err:  # noqa: BLE001
            self._mark_error(err)
            return
        self._last_rgb = rgb
        self._mark_ok()

    @staticmethod
    def _scaled(state: "DeviceState") -> RGB:
        factor = max(0.0, min(1.0, state.brightness / 255.0))
        return (
            int(state.rgb[0] * factor),
            int(state.rgb[1] * factor),
            int(state.rgb[2] * factor),
        )

    async def async_close(self) -> None:
        client = self._client
        self._client = None
        if client is not None:
            try:
                await client.disconnect()
            except Exception:  # noqa: BLE001 - best effort
                pass
        await asyncio.sleep(0)
        self._last_rgb = None
        self._powered = None
        self.online = False


__all__ = ["BleTransport", "colour_bytes", "normalise_uuid"]
