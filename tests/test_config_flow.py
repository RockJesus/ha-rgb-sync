"""Config and options flow tests."""

from __future__ import annotations

from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rgb_sync.const import (
    CONF_DEVICES,
    CONF_PROTOCOL,
    CONF_ENABLED,
    DOMAIN,
    PROTOCOL_BLE,
    PROTOCOL_NETWORK,
    PROTOCOL_WLED,
)

VALIDATE = "custom_components.rgb_sync.config_flow.async_validate_device"


async def test_full_config_flow(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": "Home RGB"})
    assert result["step_id"] == "add_menu"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "wled"})
    assert result["step_id"] == "wled"

    with patch(VALIDATE, return_value=None):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"name": "Living room", "host": "192.168.1.50", "port": 80, "pixels": 60, "enabled": True},
        )
    assert result["step_id"] == "add_menu"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "finish"})
    assert result["type"] == "create_entry"
    assert result["title"] == "Home RGB"
    devices = result["data"][CONF_DEVICES]
    assert len(devices) == 1
    assert devices[0][CONF_PROTOCOL] == PROTOCOL_WLED
    assert devices[0]["host"] == "192.168.1.50"
    assert devices[0][CONF_ENABLED] is True


async def test_config_flow_reports_connection_error(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": "Home RGB"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "network"})
    assert result["step_id"] == "network"

    with patch(VALIDATE, return_value="cannot_connect"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "Desk",
                "net_protocol": "http",
                "host": "192.168.1.99",
                "port": 80,
                "path": "/color",
                "method": "POST",
                "body": "{}",
                "pixels": 1,
                "enabled": True,
            },
        )
    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_ble_device_normalisation(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": "Home RGB"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "ble"})
    with patch(VALIDATE, return_value=None):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"name": "Desk strip", "address": "aa:bb:cc:dd:ee:ff", "ble_profile": "triones", "enabled": True},
        )
    assert result["step_id"] == "add_menu"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "finish"})
    device = result["data"][CONF_DEVICES][0]
    assert device[CONF_PROTOCOL] == PROTOCOL_BLE
    assert device["address"] == "AA:BB:CC:DD:EE:FF"
    assert device["pixels"] == 1


async def test_options_flow_add_and_remove(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home RGB",
        data={
            CONF_DEVICES: [
                {
                    "id": "dev1",
                    "name": "Living room",
                    "protocol": PROTOCOL_WLED,
                    "host": "192.168.1.50",
                    "port": 80,
                    "pixels": 30,
                    "enabled": True,
                }
            ]
        },
        options={},
        entry_id="test_entry",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "menu"
    assert "add_network" in result["menu_options"]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "add_network"}
    )
    assert result["step_id"] == "add_network"

    with patch(VALIDATE, return_value=None):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                "name": "Bedroom",
                "net_protocol": "udp",
                "host": "192.168.1.60",
                "port": 5577,
                "path": "/color",
                "method": "POST",
                "body": "{r},{g},{b}",
                "pixels": 1,
                "enabled": True,
            },
        )
    assert result["type"] == "menu"
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "save"})
    assert result["type"] == "create_entry"
    stored = result["data"][CONF_DEVICES]
    assert len(stored) == 2
    assert stored[1][CONF_PROTOCOL] == PROTOCOL_NETWORK
    assert stored[1]["host"] == "192.168.1.60"


async def test_matter_and_mqtt_devices(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": "Home RGB"})
    assert set(result["menu_options"]) >= {"matter", "mqtt"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "matter"})
    assert result["step_id"] == "matter"
    with patch(VALIDATE, return_value=None):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"name": "Matter 吊灯", "entity_id": "Light.Matter_Pendant", "enabled": True},
        )
    assert result["step_id"] == "add_menu"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "mqtt"})
    assert result["step_id"] == "mqtt"
    with patch(VALIDATE, return_value=None):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "MQTT 灯带",
                "topic": "rgb_sync/strip",
                "qos": 1,
                "retain": True,
                "body": '{"state": "{state}"}',
                "enabled": True,
            },
        )
    assert result["step_id"] == "add_menu"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "finish"})
    devices = result["data"][CONF_DEVICES]
    assert [d[CONF_PROTOCOL] for d in devices] == ["matter", "mqtt"]
    assert devices[0]["entity_id"] == "light.matter_pendant"
    assert devices[0]["pixels"] == 1
    assert devices[1]["topic"] == "rgb_sync/strip"
    assert devices[1]["qos"] == 1
    assert devices[1]["retain"] is True
