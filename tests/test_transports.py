"""Tests for transport payload builders."""

from types import SimpleNamespace

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
