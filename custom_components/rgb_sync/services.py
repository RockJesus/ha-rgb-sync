"""Service handlers shared by every config entry."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv, device_registry as dr, entity_registry as er, selector

from .const import (
    ATTR_BANDS,
    ATTR_BRIGHTNESS,
    ATTR_DEVICE,
    ATTR_EFFECT,
    ATTR_HEX,
    ATTR_LEVEL,
    ATTR_ON,
    ATTR_PALETTE,
    ATTR_RGB,
    ATTR_SCENE,
    ATTR_SPEED,
    DOMAIN,
    EFFECTS,
    SCENES,
    SERVICE_APPLY,
    SERVICE_AUDIO_LEVEL,
    SERVICE_CUE,
    SERVICE_EFFECT,
    SERVICE_IDENTIFY,
    SERVICE_PING,
    SERVICE_SCENE,
)
from .effects import hex_to_rgb
from .engine import SyncEngine

_LOGGER = logging.getLogger(__name__)

DEVICE_SELECTOR = selector.DeviceSelector(selector.DeviceSelectorConfig(integration=DOMAIN))

APPLY_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_DEVICE): DEVICE_SELECTOR,
        vol.Optional(ATTR_ON): cv.boolean,
        vol.Optional(ATTR_BRIGHTNESS): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
        vol.Optional(ATTR_RGB): vol.All([cv.byte], vol.Length(min=3, max=3)),
        vol.Optional(ATTR_HEX): cv.string,
        vol.Optional(ATTR_EFFECT): vol.In(EFFECTS),
        vol.Optional(ATTR_SPEED): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
        vol.Optional(ATTR_PALETTE): [cv.string],
    }
)

EFFECT_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_DEVICE): DEVICE_SELECTOR,
        vol.Required(ATTR_EFFECT): vol.In(EFFECTS),
        vol.Optional(ATTR_SPEED): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
        vol.Optional(ATTR_PALETTE): [cv.string],
    }
)

SCENE_SCHEMA = vol.Schema({vol.Required(ATTR_SCENE): vol.In(SCENES)})

AUDIO_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_LEVEL): vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
        vol.Optional(ATTR_BANDS): vol.All([vol.Coerce(float)], vol.Length(max=48)),
    }
)

IDENTIFY_SCHEMA = vol.Schema({vol.Optional(ATTR_DEVICE): DEVICE_SELECTOR})


def _engines(hass: HomeAssistant) -> list[SyncEngine]:
    store = hass.data.get(DOMAIN, {})
    return [value for value in store.values() if isinstance(value, SyncEngine)]


def _resolve(engine: SyncEngine, hass: HomeAssistant, service_call: ServiceCall) -> list[str]:
    """Map Home Assistant device / entity targets to RGB Sync device ids."""
    device_refs = service_call.data.get(ATTR_DEVICE)
    if isinstance(device_refs, str):
        device_refs = [device_refs]
    entity_refs = service_call.data.get("entity_id")
    if isinstance(entity_refs, str):
        entity_refs = [entity_refs]

    ha_ids: set[str] = set(device_refs or [])
    if entity_refs:
        registry = er.async_get(hass)
        for entity_id in entity_refs:
            record = registry.async_get(entity_id)
            if record is not None and record.device_id:
                ha_ids.add(record.device_id)

    if not ha_ids:
        # Plain YAML callers may pass the integration device id or its name.
        raw = service_call.data.get(ATTR_DEVICE)
        if raw:
            for device in engine.devices:
                if raw in (str(device.get("id")), str(device.get("name"))):
                    return [str(device["id"])]
        return [str(device["id"]) for device in engine.devices]

    resolved: list[str] = []
    device_registry = dr.async_get(hass)
    for ha_id in ha_ids:
        entry = device_registry.async_get(ha_id)
        if entry is None:
            continue
        for domain, identifier in entry.identifiers:
            if domain != DOMAIN:
                continue
            if identifier == engine.entry.entry_id:
                resolved.extend(str(device["id"]) for device in engine.devices)
                continue
            for device in engine.devices:
                if f"{engine.entry.entry_id}_{device['id']}" == identifier:
                    resolved.append(str(device["id"]))
    return resolved


async def _async_apply(hass: HomeAssistant, service_call: ServiceCall) -> None:
    for engine in _engines(hass):
        rgb = service_call.data.get(ATTR_RGB)
        hex_color = service_call.data.get(ATTR_HEX)
        if hex_color:
            rgb = hex_to_rgb(hex_color)
        kwargs: dict[str, Any] = {}
        for key in (ATTR_ON, ATTR_BRIGHTNESS, ATTR_EFFECT, ATTR_SPEED, ATTR_PALETTE):
            if key in service_call.data:
                kwargs[key] = service_call.data[key]
        if rgb:
            kwargs["rgb"] = tuple(int(channel) for channel in rgb)
            kwargs.setdefault("palette", ["#{:02x}{:02x}{:02x}".format(*kwargs["rgb"])])
        targets = _resolve(engine, hass, service_call)
        for dev_id in targets:
            await engine.async_set(dev_id, source="user", **kwargs)


async def _async_effect(hass: HomeAssistant, service_call: ServiceCall) -> None:
    for engine in _engines(hass):
        palette = service_call.data.get(ATTR_PALETTE) or []
        for dev_id in _resolve(engine, hass, service_call):
            await engine.async_set(
                dev_id,
                on=True,
                effect=service_call.data[ATTR_EFFECT],
                speed=service_call.data.get(ATTR_SPEED),
                palette=palette or None,
                source="user",
            )


async def _async_scene(hass: HomeAssistant, service_call: ServiceCall) -> None:
    for engine in _engines(hass):
        await engine.async_apply_scene(service_call.data[ATTR_SCENE])


async def _async_audio(hass: HomeAssistant, service_call: ServiceCall) -> None:
    for engine in _engines(hass):
        await engine.async_audio_level(
            service_call.data[ATTR_LEVEL], service_call.data.get(ATTR_BANDS)
        )


async def _async_cue(hass: HomeAssistant, service_call: ServiceCall) -> None:
    for engine in _engines(hass):
        await engine.async_cue(force=True)


async def _async_identify(hass: HomeAssistant, service_call: ServiceCall) -> None:
    for engine in _engines(hass):
        targets = _resolve(engine, hass, service_call)
        if service_call.data.get(ATTR_DEVICE) and targets:
            await engine.async_identify(targets[0])
        else:
            await engine.async_identify()


async def _async_ping(hass: HomeAssistant, service_call: ServiceCall) -> None:
    for engine in _engines(hass):
        await engine.async_ping()


async def async_register_services(hass: HomeAssistant) -> None:
    """Register the RGB Sync service actions once per Home Assistant run."""
    if hass.data.setdefault(DOMAIN, {}).get("services_registered"):
        return
    hass.data[DOMAIN]["services_registered"] = True
    hass.services.async_register(DOMAIN, SERVICE_APPLY, _async_apply, schema=APPLY_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_EFFECT, _async_effect, schema=EFFECT_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_SCENE, _async_scene, schema=SCENE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_AUDIO_LEVEL, _async_audio, schema=AUDIO_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_CUE, _async_cue)
    hass.services.async_register(DOMAIN, SERVICE_IDENTIFY, _async_identify, schema=IDENTIFY_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_PING, _async_ping)


__all__ = ["async_register_services"]
