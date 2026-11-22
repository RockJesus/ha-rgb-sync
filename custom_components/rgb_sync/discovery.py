"""Automatic device discovery for RGB Sync.

Three sources are probed:

* Bluetooth LE advertisements (Triones / ELK-BLEDOM class controllers).
* The entity registry, to pick up Matter bulbs that are already commissioned.
* mDNS (``_wled._tcp.local.``), to pick up WLED controllers on the LAN.

MQTT needs an explicit topic per device, so it is never guessed by the scanner.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_ADDRESS,
    CONF_AUTO_ADD,
    CONF_DEVICE_ID,
    CONF_DEVICES,
    CONF_ENABLED,
    CONF_ENTITY_ID,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_TOPIC,
    DEFAULT_BLE_SERVICE_UUID,
    DOMAIN,
    PROTOCOL_BLE,
    PROTOCOL_MATTER,
    PROTOCOL_MQTT,
    PROTOCOL_WLED,
)

_LOGGER = logging.getLogger(__name__)

WLED_ZEROCONF_TYPE: str = "_wled._tcp.local."
DEFAULT_SCAN_SECONDS: float = 3.0

# Advertised names that almost always belong to a generic BLE RGB controller.
BLE_NAME_HINTS: tuple[str, ...] = (
    "triones",
    "elk-bledom",
    "ledble",
    "lednet",
    "happy",
    "qhm",
    "duo",
)


# ---------------------------------------------------------------------------
# Identity helpers
# ---------------------------------------------------------------------------
def device_identity(device: dict[str, Any]) -> str:
    """Return a stable identity string used for de-duplication."""
    protocol = str(device.get(CONF_PROTOCOL))
    if protocol == PROTOCOL_BLE:
        return f"ble:{str(device.get(CONF_ADDRESS, '')).strip().upper()}"
    if protocol == PROTOCOL_MATTER:
        return f"matter:{str(device.get(CONF_ENTITY_ID, '')).strip().lower()}"
    if protocol == PROTOCOL_MQTT:
        return f"mqtt:{str(device.get(CONF_TOPIC, '')).strip()}"
    host = str(device.get(CONF_HOST, '')).strip().lower()
    port = int(device.get(CONF_PORT, 80))
    return f"{protocol}:{host}:{port}"


def configured_identities(devices: list[dict[str, Any]]) -> set[str]:
    """Identities of the devices that are already part of the hub."""
    return {device_identity(device) for device in devices}


def filter_new_candidates(
    candidates: list[dict[str, Any]], devices: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Drop candidates that are already configured or duplicated."""
    known = configured_identities(devices)
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for candidate in candidates:
        identity = device_identity(candidate)
        if identity in known or identity in seen or identity.endswith(":"):
            continue
        seen.add(identity)
        result.append(candidate)
    return result


# ---------------------------------------------------------------------------
# Bluetooth LE
# ---------------------------------------------------------------------------
def _is_ble_light(info: Any) -> bool:
    """True when a BLE advertisement looks like an RGB controller."""
    service_uuids = [str(uuid).lower() for uuid in (getattr(info, "service_uuids", None) or [])]
    if DEFAULT_BLE_SERVICE_UUID in service_uuids:
        return True
    name = str(getattr(info, "name", None) or "").lower()
    return any(hint in name for hint in BLE_NAME_HINTS)


def candidate_from_ble_info(info: Any) -> dict[str, Any] | None:
    """Turn a BLE advertisement into a device definition."""
    address = str(getattr(info, "address", "") or "").strip().upper()
    if not address or not _is_ble_light(info):
        return None
    name = str(getattr(info, "name", None) or "").strip()
    return {
        CONF_PROTOCOL: PROTOCOL_BLE,
        CONF_NAME: name or f"蓝牙灯带 {address[-5:]}",
        CONF_ADDRESS: address,
    }


async def async_bluetooth_candidates(hass: HomeAssistant) -> list[dict[str, Any]]:
    """List BLE RGB controllers seen by the bluetooth integration."""
    if "bluetooth" not in hass.config.components:
        return []
    try:
        from homeassistant.components import bluetooth
    except ImportError:  # pragma: no cover - bluetooth is a built-in
        return []
    try:
        infos = bluetooth.async_discovered_service_info(hass, connectable=True)
    except (AttributeError, KeyError):  # pragma: no cover - bluetooth not set up
        return []
    candidates = []
    for info in infos:
        candidate = candidate_from_ble_info(info)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


# ---------------------------------------------------------------------------
# Matter
# ---------------------------------------------------------------------------
def async_matter_candidates(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Return commissioned Matter lights that are not part of the hub yet."""
    registry = er.async_get(hass)
    candidates: list[dict[str, Any]] = []
    for entity in registry.entities.values():
        if entity.domain != "light" or entity.platform != "matter":
            continue
        if entity.disabled_by is not None or entity.hidden_by is not None:
            continue
        label = entity.name or entity.original_name or entity.entity_id
        candidates.append(
            {
                CONF_PROTOCOL: PROTOCOL_MATTER,
                CONF_NAME: str(label),
                CONF_ENTITY_ID: entity.entity_id,
            }
        )
    return candidates


# ---------------------------------------------------------------------------
# mDNS / WLED
# ---------------------------------------------------------------------------
def wled_candidate(service_name: str, addresses: list[str], port: int) -> dict[str, Any] | None:
    """Build a WLED device definition from mDNS data."""
    host = next((address for address in addresses if address), "")
    if not host:
        return None
    label = service_name.split(".")[0].strip() or host
    return {
        CONF_PROTOCOL: PROTOCOL_WLED,
        CONF_NAME: label,
        CONF_HOST: host,
        CONF_PORT: int(port or 80),
        CONF_ENABLED: True,
    }


async def async_zeroconf_candidates(
    hass: HomeAssistant, timeout: float = DEFAULT_SCAN_SECONDS
) -> list[dict[str, Any]]:
    """Browse ``_wled._tcp.local.`` for WLED controllers."""
    try:
        from homeassistant.components.zeroconf import async_get_async_instance
        from zeroconf import ServiceStateChange
        from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo
    except ImportError:  # pragma: no cover - both are core dependencies
        return []

    try:
        aiozc = await async_get_async_instance(hass)
    except (AttributeError, RuntimeError, KeyError):  # pragma: no cover
        return []

    found: dict[str, None] = {}

    def _handler(zeroconf, service_type, name, state_change) -> None:
        if state_change is ServiceStateChange.Added:
            found[name] = None

    browser = None
    try:
        browser = AsyncServiceBrowser(aiozc.zeroconf, WLED_ZEROCONF_TYPE, handlers=[_handler])
        await asyncio.sleep(timeout)
    except (AttributeError, RuntimeError, TypeError):  # pragma: no cover - no zeroconf
        return []
    finally:
        if browser is not None:
            try:
                await browser.async_cancel()
            except (RuntimeError, TypeError):  # pragma: no cover
                pass

    candidates: list[dict[str, Any]] = []
    for name in found:
        info = AsyncServiceInfo(WLED_ZEROCONF_TYPE, name)
        try:
            if not await info.async_request(aiozc.zeroconf, 1500):
                continue
        except (AttributeError, RuntimeError, TypeError):  # pragma: no cover
            continue
        candidate = wled_candidate(name, info.parsed_addresses(), info.port)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------
async def async_scan_devices(
    hass: HomeAssistant,
    devices: list[dict[str, Any]] | None = None,
    timeout: float = DEFAULT_SCAN_SECONDS,
) -> list[dict[str, Any]]:
    """Collect every addable device, minus the ones already configured."""
    candidates: list[dict[str, Any]] = list(async_matter_candidates(hass))
    candidates.extend(await async_bluetooth_candidates(hass))
    candidates.extend(await async_zeroconf_candidates(hass, timeout))
    return filter_new_candidates(candidates, devices or [])


# ---------------------------------------------------------------------------
# Writing discoveries back to the hub entry
# ---------------------------------------------------------------------------
def build_device(candidate: dict[str, Any]) -> dict[str, Any]:
    """Normalise a discovery candidate into a stored device definition."""
    protocol = str(candidate[CONF_PROTOCOL])
    device: dict[str, Any] = {
        CONF_DEVICE_ID: uuid.uuid4().hex[:10],
        CONF_NAME: str(candidate.get(CONF_NAME) or "RGB").strip(),
        CONF_PROTOCOL: protocol,
        CONF_ENABLED: bool(candidate.get(CONF_ENABLED, True)),
        "pixels": 1,
    }
    if protocol == PROTOCOL_BLE:
        device[CONF_ADDRESS] = str(candidate.get(CONF_ADDRESS, "")).strip().upper()
    elif protocol == PROTOCOL_MATTER:
        device[CONF_ENTITY_ID] = str(candidate.get(CONF_ENTITY_ID, "")).strip().lower()
    elif protocol == PROTOCOL_WLED:
        device[CONF_HOST] = str(candidate.get(CONF_HOST, "")).strip()
        device[CONF_PORT] = int(candidate.get(CONF_PORT, 80))
    elif protocol == PROTOCOL_MQTT:
        device[CONF_TOPIC] = str(candidate.get(CONF_TOPIC, "")).strip()
    else:  # pragma: no cover - network controllers are never auto discovered
        return device
    return device


async def async_add_to_entry(
    hass: HomeAssistant, entry: Any, candidates: list[dict[str, Any]], reload: bool = False
) -> list[dict[str, Any]]:
    """Append newly discovered devices to the hub options.

    The entry update listener reloads the hub, so an explicit reload is only
    needed when the caller does not rely on it.
    """
    devices = [dict(device) for device in (entry.options.get(CONF_DEVICES) or entry.data.get(CONF_DEVICES) or [])]
    fresh = filter_new_candidates(candidates, devices)
    if not fresh:
        return []
    new_devices = [build_device(candidate) for candidate in fresh]
    devices.extend(new_devices)
    options = dict(entry.options or entry.data)
    options[CONF_DEVICES] = devices
    hass.config_entries.async_update_entry(entry, options=options)
    _LOGGER.info("Auto discovered %s", ", ".join(device[CONF_NAME] for device in new_devices))
    if reload:
        await hass.config_entries.async_reload(entry.entry_id)
    return new_devices


@callback
def async_register_bluetooth_listener(hass: HomeAssistant, entry: Any) -> Any:
    """Auto-add BLE controllers that show up after the hub is running."""
    if not entry.options.get(CONF_AUTO_ADD, entry.data.get(CONF_AUTO_ADD, True)):
        return None
    if "bluetooth" not in hass.config.components:
        return None
    try:
        from homeassistant.components import bluetooth
        from homeassistant.components.bluetooth import BluetoothScanningMode
        from homeassistant.components.bluetooth.match import BluetoothCallbackMatcher
    except ImportError:  # pragma: no cover - bluetooth is a built-in
        return None

    matcher = BluetoothCallbackMatcher(
        {"connectable": True, "service_uuid": DEFAULT_BLE_SERVICE_UUID}
    )
    pending: set[str] = hass.data.setdefault(DOMAIN, {}).setdefault("discovery_pending", set())

    @callback
    def _handle(service_info: Any, change: Any) -> None:
        candidate = candidate_from_ble_info(service_info)
        if candidate is None:
            return
        address = str(candidate[CONF_ADDRESS])
        if address in pending:
            return
        pending.add(address)
        hass.async_create_task(_async_auto_add(entry, candidate, pending))

    async def _async_auto_add(entry_ref: Any, candidate: dict[str, Any], seen: set[str]) -> None:
        try:
            await async_add_to_entry(hass, entry_ref, [candidate])
        finally:
            seen.discard(str(candidate.get(CONF_ADDRESS, "")))

    try:
        return bluetooth.async_register_callback(
            hass, matcher, _handle, BluetoothScanningMode.ACTIVE
        )
    except (AttributeError, TypeError, ValueError):  # pragma: no cover - older core
        return None


__all__ = [
    "async_add_to_entry",
    "async_bluetooth_candidates",
    "async_matter_candidates",
    "async_register_bluetooth_listener",
    "async_scan_devices",
    "async_zeroconf_candidates",
    "build_device",
    "candidate_from_ble_info",
    "configured_identities",
    "device_identity",
    "filter_new_candidates",
    "wled_candidate",
]
