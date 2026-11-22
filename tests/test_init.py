"""Setup / teardown tests against a real config entry."""

from __future__ import annotations

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rgb_sync.const import CONF_DEVICES, DOMAIN


async def test_setup_and_unload(hass, socket_enabled):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home RGB",
        data={
            CONF_DEVICES: [
                {
                    "id": "udp1",
                    "name": "Kitchen",
                    "protocol": "network",
                    "net_protocol": "udp",
                    "host": "127.0.0.1",
                    "port": 5577,
                    "path": "/color",
                    "method": "POST",
                    "body": "{r},{g},{b}",
                    "pixels": 1,
                    "enabled": True,
                }
            ]
        },
        entry_id="setup_test",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    lights = hass.states.async_entity_ids("light")
    switches = hass.states.async_entity_ids("switch")
    sensors = hass.states.async_entity_ids("sensor")
    assert len(lights) == 2  # group + one device
    assert len(switches) == 3
    assert len(sensors) == 3
    assert hass.services.has_service(DOMAIN, "apply")

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.entry_id not in hass.data.get(DOMAIN, {})


async def test_group_light_and_sync_switch(hass, socket_enabled):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home RGB",
        data={
            CONF_DEVICES: [
                {
                    "id": "udp1",
                    "name": "Kitchen",
                    "protocol": "network",
                    "net_protocol": "udp",
                    "host": "127.0.0.1",
                    "port": 5577,
                    "path": "/color",
                    "method": "POST",
                    "body": "{r},{g},{b}",
                    "pixels": 1,
                    "enabled": True,
                }
            ]
        },
        entry_id="light_test",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    group = hass.states.get("light.home_rgb_all_lights")
    assert group is not None
    assert group.state == "off"

    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": "light.home_rgb_all_lights",
            "rgb_color": [255, 0, 77],
            "brightness": 128,
            "effect": "呼吸",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    device = hass.states.get("light.kitchen")
    assert device is not None
    assert device.state == "on"
    assert device.attributes["rgb_color"] == (255, 0, 77)
    assert device.attributes["effect"] == "呼吸"
    assert device.attributes["brightness"] == 128

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.home_rgb_whole_house_sync"}, blocking=True
    )
    await hass.async_block_till_done()
    assert hass.states.get("switch.home_rgb_whole_house_sync").state == "on"

    await hass.config_entries.async_unload(entry.entry_id)
