"""Tests for device auto discovery."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rgb_sync import discovery
from custom_components.rgb_sync.const import (
    CONF_AUTO_ADD,
    CONF_CANDIDATES,
    CONF_DEVICES,
    CONF_PROTOCOL,
    DOMAIN,
    DEFAULT_BLE_SERVICE_UUID,
    PROTOCOL_BLE,
    PROTOCOL_MATTER,
    PROTOCOL_WLED,
)

SCAN = "custom_components.rgb_sync.config_flow.async_scan_devices"
VALIDATE = "custom_components.rgb_sync.config_flow.async_validate_device"


def _hub_entry(**options) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="全屋 RGB",
        unique_id=DOMAIN,
        data={CONF_DEVICES: []},
        options={CONF_DEVICES: [], CONF_AUTO_ADD: True, **options},
    )


def test_device_identity_per_protocol():
    assert discovery.device_identity({CONF_PROTOCOL: PROTOCOL_BLE, "address": "aa:bb:cc:dd:ee:ff"}) == (
        "ble:AA:BB:CC:DD:EE:FF"
    )
    assert discovery.device_identity(
        {CONF_PROTOCOL: PROTOCOL_MATTER, "entity_id": "Light.Bulb"}
    ) == "matter:light.bulb"
    assert discovery.device_identity({CONF_PROTOCOL: PROTOCOL_WLED, "host": "10.0.0.5"}) == (
        "wled:10.0.0.5:80"
    )


def test_filter_new_candidates_skips_configured_and_duplicates():
    existing = [{CONF_PROTOCOL: PROTOCOL_BLE, "address": "AA:BB:CC:DD:EE:01"}]
    candidates = [
        {CONF_PROTOCOL: PROTOCOL_BLE, "address": "aa:bb:cc:dd:ee:01", "name": "old"},
        {CONF_PROTOCOL: PROTOCOL_BLE, "address": "AA:BB:CC:DD:EE:02", "name": "new"},
        {CONF_PROTOCOL: PROTOCOL_BLE, "address": "AA:BB:CC:DD:EE:02", "name": "dupe"},
        {CONF_PROTOCOL: PROTOCOL_WLED, "host": "10.0.0.9", "port": 80},
        {CONF_PROTOCOL: PROTOCOL_BLE, "address": "", "name": "broken"},
    ]
    fresh = discovery.filter_new_candidates(candidates, existing)
    assert [item.get("name") or item.get("host") for item in fresh] == ["new", "10.0.0.9"]


def test_candidate_from_ble_info():
    info = SimpleNamespace(
        address="aa:bb:cc:dd:ee:ff",
        name="Triones-ABCDEF",
        service_uuids=[DEFAULT_BLE_SERVICE_UUID],
        rssi=-60,
    )
    candidate = discovery.candidate_from_ble_info(info)
    assert candidate is not None
    assert candidate[CONF_PROTOCOL] == PROTOCOL_BLE
    assert candidate["address"] == "AA:BB:CC:DD:EE:FF"
    assert candidate["name"] == "Triones-ABCDEF"

    named = SimpleNamespace(address="11:22:33:44:55:66", name="ELK-BLEDOM", service_uuids=[])
    assert discovery.candidate_from_ble_info(named)["name"] == "ELK-BLEDOM"

    speaker = SimpleNamespace(address="aa:bb:cc:dd:ee:99", name="JBL Flip", service_uuids=[])
    assert discovery.candidate_from_ble_info(speaker) is None
    assert discovery.candidate_from_ble_info(SimpleNamespace(name="x")) is None


def test_wled_candidate():
    candidate = discovery.wled_candidate("wled-abc123._wled._tcp.local.", ["10.0.0.12"], 80)
    assert candidate is not None
    assert candidate[CONF_PROTOCOL] == PROTOCOL_WLED
    assert candidate["host"] == "10.0.0.12"
    assert candidate["port"] == 80
    assert candidate["name"] == "wled-abc123"
    assert discovery.wled_candidate("empty", [], 80) is None


async def test_scan_devices_merges_sources(hass):
    matter = [
        {
            CONF_PROTOCOL: PROTOCOL_MATTER,
            "entity_id": "light.matter_bulb",
            "name": "Matter bulb",
        }
    ]
    ble = [{CONF_PROTOCOL: PROTOCOL_BLE, "address": "AA:BB:CC:DD:EE:01", "name": "strip"}]
    zeroconf = [{CONF_PROTOCOL: PROTOCOL_WLED, "host": "10.0.0.12", "port": 80, "name": "wled"}]

    async def _fake_ble(_hass):
        return ble

    async def _fake_zeroconf(_hass, _timeout=3.0):
        return zeroconf

    with (
        patch.object(discovery, "async_matter_candidates", return_value=matter),
        patch.object(discovery, "async_bluetooth_candidates", _fake_ble),
        patch.object(discovery, "async_zeroconf_candidates", _fake_zeroconf),
    ):
        found = await discovery.async_scan_devices(
            hass, [{CONF_PROTOCOL: PROTOCOL_BLE, "address": "AA:BB:CC:DD:EE:01"}]
        )

    assert [item[CONF_PROTOCOL] for item in found] == [PROTOCOL_MATTER, PROTOCOL_WLED]


async def test_matter_candidates_from_registry(hass):
    registry = er.async_get(hass)
    active = registry.async_get_or_create(
        "light", "matter", "matter-uid-1", suggested_object_id="matter_bulb"
    )
    registry.async_get_or_create(
        "light", "hue", "hue-uid-1", suggested_object_id="hue_bulb"
    )
    candidates = discovery.async_matter_candidates(hass)
    assert [item["entity_id"] for item in candidates] == [active.entity_id]

    registry.async_update_entity(active.entity_id, disabled_by=er.RegistryEntryDisabler.USER)
    assert discovery.async_matter_candidates(hass) == []


async def test_async_add_to_entry_appends_devices(hass):
    entry = _hub_entry()
    entry.add_to_hass(hass)
    candidate = {CONF_PROTOCOL: PROTOCOL_WLED, "host": "10.0.0.12", "port": 80, "name": "wled"}
    added = await discovery.async_add_to_entry(hass, entry, [candidate])
    assert len(added) == 1
    stored = hass.config_entries.async_get_entry(entry.entry_id)
    assert stored.options[CONF_DEVICES][0]["host"] == "10.0.0.12"
    assert stored.options[CONF_DEVICES][0]["id"]

    again = await discovery.async_add_to_entry(hass, stored, [candidate])
    assert again == []
    assert len(stored.options[CONF_DEVICES]) == 1


async def test_bluetooth_listener_defers_without_bluetooth(hass):
    from homeassistant.const import EVENT_COMPONENT_LOADED

    entry = _hub_entry()
    entry.add_to_hass(hass)
    unsub = discovery.async_register_bluetooth_listener(hass, entry)
    assert callable(unsub)
    # No bluetooth component: the listener waits instead of failing.
    hass.bus.async_fire(EVENT_COMPONENT_LOADED, {"component": "bluetooth"})
    await hass.async_block_till_done()
    unsub()


async def test_bluetooth_listener_respects_auto_add_off(hass):
    entry = _hub_entry(**{CONF_AUTO_ADD: False})
    entry.add_to_hass(hass)
    assert discovery.async_register_bluetooth_listener(hass, entry) is None


async def test_options_flow_discover_adds_selected(hass):
    entry = _hub_entry()
    entry.add_to_hass(hass)

    candidates = [
        {CONF_PROTOCOL: PROTOCOL_BLE, "address": "AA:BB:CC:DD:EE:01", "name": "蓝牙灯带"},
        {CONF_PROTOCOL: PROTOCOL_MATTER, "entity_id": "light.matter_bulb", "name": "Matter 灯"},
    ]
    with patch(SCAN, return_value=candidates), patch(VALIDATE, return_value=None):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["step_id"] == "init"
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "discover"}
        )
        assert result["step_id"] == "discover"
        assert result["description_placeholders"]["count"] == "2"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_CANDIDATES: ["0", "1"]}
        )
    assert result["step_id"] == "init"
    assert result["type"] == "menu"

    with patch(VALIDATE, return_value=None):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "save"}
        )
    assert result["type"] == "create_entry"
    devices = result["data"][CONF_DEVICES]
    assert {device[CONF_PROTOCOL] for device in devices} == {PROTOCOL_BLE, PROTOCOL_MATTER}


async def test_options_flow_discover_empty(hass):
    entry = _hub_entry()
    entry.add_to_hass(hass)
    with patch(SCAN, return_value=[]):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "discover"}
        )
    assert result["step_id"] == "discover_none"
    assert result["type"] == "menu"


async def test_config_flow_zeroconf_adds_to_existing_hub(hass):
    entry = _hub_entry()
    entry.add_to_hass(hass)

    discovery_info = SimpleNamespace(
        host="10.0.0.12",
        name="wled-abc123._wled._tcp.local.",
        port=80,
        properties={"mac": "abcd"},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "zeroconf"}, data=discovery_info
    )
    assert result["step_id"] == "discovered"
    assert result["description_placeholders"]["name"] == "wled-abc123"

    with patch(VALIDATE, return_value=None):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"name": "wled-abc123", "host": "10.0.0.12", "port": 80, "pixels": 60, "enabled": True},
        )
    assert result["type"] == "abort"
    assert result["reason"] == "device_added"
    assert hass.config_entries.async_get_entry(entry.entry_id).options[CONF_DEVICES][0]["host"] == (
        "10.0.0.12"
    )


async def test_config_flow_bluetooth_requires_address(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "bluetooth"}, data=SimpleNamespace(name="Triones-ABCDEF")
    )
    assert result["type"] == "abort"
    assert result["reason"] == "invalid_discovery_info"


async def test_config_flow_bluetooth_first_setup(hass):
    discovery_info = SimpleNamespace(
        address="aa:bb:cc:dd:ee:ff", name="Triones-ABCDEF", service_uuids=[DEFAULT_BLE_SERVICE_UUID]
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "bluetooth"}, data=discovery_info
    )
    assert result["step_id"] == "add_menu"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "finish"}
    )
    assert result["type"] == "create_entry"
    device = result["data"][CONF_DEVICES][0]
    assert device[CONF_PROTOCOL] == PROTOCOL_BLE
    assert device["address"] == "AA:BB:CC:DD:EE:FF"


@pytest.mark.parametrize("protocol", [PROTOCOL_WLED, PROTOCOL_BLE, PROTOCOL_MATTER])
async def test_build_device_normalises(protocol):
    candidate = {CONF_PROTOCOL: protocol, "name": " Dev "}
    if protocol == PROTOCOL_WLED:
        candidate.update({"host": "10.0.0.2", "port": 80})
    elif protocol == PROTOCOL_BLE:
        candidate.update({"address": "aa:bb:cc:dd:ee:ff"})
    else:
        candidate.update({"entity_id": "Light.Bulb"})
    device = discovery.build_device(candidate)
    assert device[CONF_PROTOCOL] == protocol
    assert device["name"] == "Dev"
    assert len(device["id"]) == 10
