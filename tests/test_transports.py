"""Tests for transport payload builders."""

from types import SimpleNamespace

import pytest

from custom_components.rgb_sync.models import DeviceState
from custom_components.rgb_sync.transports.base import parse_hex, render_payload
from custom_components.rgb_sync.transports.ble import colour_bytes, normalise_uuid
from custom_components.rgb_sync.transports.wled import WledTransport


def test_render_payload():
    state = DeviceState(on=True, brightness=128, rgb=(255, 0, 77), effect="彩虹", speed=70)
    payload = render_payload(
        '{"on": {on}, "bri": {brightness}, "pct": {brightness_pct}, "r": {r}, "g": {g}, "b": {b}, "hex": "{hex}"}',
        state,
    )
    assert '"on": 1' in payload
    assert '"bri": 128' in payload
    assert '"pct": 50' in payload
    assert '"r": 255' in payload
    assert '"hex": "#ff004d"' in payload


def test_render_payload_off_state():
    state = DeviceState(on=False)
    assert render_payload("{state}", state) == "OFF"


def test_parse_hex_variants():
    assert parse_hex("cc 23 33") == b"\xcc\x23\x33"
    assert parse_hex("0xcc,0x23,0x33") == b"\xcc\x23\x33"
    assert parse_hex("cc2333") == b"\xcc\x23\x33"


def test_ble_colour_bytes():
    assert colour_bytes("56{r:02x}{g:02x}{b:02x}00f0aa", (255, 0, 77)) == bytes.fromhex("56ff004d00f0aa")


def test_normalise_uuid():
    assert normalise_uuid("FFF3") == "0000fff3-0000-1000-8000-00805f9b34fb"
    assert normalise_uuid("0000fff0-0000-1000-8000-00805f9b34fb").startswith("0000fff0")


def test_wled_state_payload():
    transport = WledTransport(SimpleNamespace(), {"id": "a", "host": "10.0.0.2", "pixels": 30})
    on = transport._state_payload(DeviceState(on=True, brightness=200, rgb=(10, 20, 30)))
    assert on["on"] is True
    assert on["bri"] == 200
    assert on["seg"][0]["col"] == [[10, 20, 30]]
    off = transport._state_payload(DeviceState(on=False))
    assert off == {"on": False, "transition": 0}


def test_wled_frame_expansion():
    transport = WledTransport(SimpleNamespace(), {"id": "a", "host": "10.0.0.2", "pixels": 3})
    transport.pixel_count = 5
    expanded = transport._expand([(1, 2, 3), (4, 5, 6)])
    assert expanded == [(1, 2, 3), (4, 5, 6), (1, 2, 3), (4, 5, 6), (1, 2, 3)]


async def test_matter_transport_forwards_to_light_entity(hass):
    from custom_components.rgb_sync.transports.base import TransportError
    from custom_components.rgb_sync.transports.matter import MatterTransport

    turn_on = []
    turn_off = []

    async def _on(call):
        turn_on.append(call)

    async def _off(call):
        turn_off.append(call)

    hass.services.async_register("light", "turn_on", _on)
    hass.services.async_register("light", "turn_off", _off)
    hass.states.async_set("light.matter_strip", "on", {"brightness": 100})

    transport = MatterTransport(hass, {"id": "m1", "protocol": "matter", "entity_id": "light.matter_strip"})
    await transport.async_setup()
    assert await transport.async_probe() is True

    await transport.async_apply(DeviceState(on=True, brightness=200, rgb=(0, 40, 255)))
    assert turn_on[-1].data["rgb_color"] == [0, 40, 255]
    assert turn_on[-1].data["brightness_pct"] == 78
    assert turn_on[-1].data["entity_id"] == "light.matter_strip"

    await transport.async_apply(DeviceState(on=False))
    assert turn_off[-1].data["entity_id"] == "light.matter_strip"

    missing = MatterTransport(hass, {"id": "m2", "protocol": "matter", "entity_id": "light.nope"})
    with pytest.raises(TransportError):
        await missing.async_setup()


async def test_mqtt_transport_publishes_rendered_payload(hass, monkeypatch):
    from homeassistant.components import mqtt

    from custom_components.rgb_sync.transports import mqtt as mqtt_transport
    from custom_components.rgb_sync.transports.base import TransportError

    published = []

    async def _publish(hass_, topic, payload, qos, retain):
        published.append((topic, payload, qos, retain))

    monkeypatch.setattr(mqtt, "async_publish", _publish)
    monkeypatch.setattr(mqtt_transport, "mqtt_client_ready", lambda hass_: True)

    transport = mqtt_transport.MqttTransport(
        hass,
        {"id": "q1", "protocol": "mqtt", "topic": "rgb_sync/desk", "qos": 1, "retain": True},
    )
    await transport.async_setup()
    await transport.async_apply(DeviceState(on=True, brightness=128, rgb=(255, 0, 77), effect="固定"))
    topic, payload, qos, retain = published[-1]
    assert topic == "rgb_sync/desk"
    assert '"state": "ON"' in payload
    assert '"r": 255' in payload
    assert qos == 1 and retain is True

    bad = mqtt_transport.MqttTransport(hass, {"id": "q2", "protocol": "mqtt", "topic": "rgb_sync/#"})
    with pytest.raises(TransportError):
        await bad.async_setup()
