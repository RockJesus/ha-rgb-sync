"""Engine behaviour tests with an in-memory transport."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.rgb_sync.const import (
    CONF_DEVICES,
    CONF_LINK,
    EFFECT_RAINBOW,
    EFFECT_SOLID,
)
from custom_components.rgb_sync.engine import SyncEngine
from custom_components.rgb_sync.models import DeviceState


class FakeTransport:
    """Records static applies instead of talking to hardware."""

    online = True
    last_error = None

    def __init__(self, device_id: str) -> None:
        self.device_id = device_id
        self.applied: list[DeviceState] = []
        self.frames = 0

    async def async_probe(self) -> bool:
        return True

    async def async_apply(self, state: DeviceState) -> None:
        self.applied.append(state)

    async def async_frame(self, frame, state) -> None:
        self.frames += 1

    async def async_close(self) -> None:
        return None


@pytest.fixture
def engine(hass) -> SyncEngine:
    devices = [
        {"id": "a", "name": "Living room", "protocol": "wled", "pixels": 30},
        {"id": "b", "name": "Bedroom", "protocol": "network", "pixels": 1},
    ]
    entry = SimpleNamespace(
        entry_id="entry_test",
        title="Home RGB",
        data={CONF_DEVICES: devices},
        options={CONF_LINK: False},
    )
    eng = SyncEngine(hass, entry)
    for device in devices:
        eng.states[str(device["id"])] = DeviceState()
    eng.transports = {"a": FakeTransport("a"), "b": FakeTransport("b")}
    return eng


async def test_individual_change_without_link(engine, hass):
    await engine.async_set("a", on=True, rgb=(255, 0, 0), source="user")
    await hass.async_block_till_done()
    assert engine.state("a").on is True
    assert engine.state("a").rgb == (255, 0, 0)
    assert engine.state("b").rgb == (255, 255, 255)
    assert engine.transports["a"].applied
    assert engine.transports["b"].applied == []


async def test_link_mirrors_colour_and_effect(engine, hass):
    engine.link = True
    await engine.async_set("a", rgb=(0, 255, 0), effect=EFFECT_RAINBOW, brightness=90, source="user")
    await hass.async_block_till_done()
    assert engine.state("b").rgb == (0, 255, 0)
    assert engine.state("b").effect == EFFECT_RAINBOW
    assert engine.state("b").brightness == 90
    # Power is intentionally per-device.
    assert engine.state("b").on is False


async def test_set_all_controls_every_device(engine, hass):
    await engine.async_set_all(on=True, brightness=40, rgb=(0, 0, 255), source="group")
    await hass.async_block_till_done()
    for dev_id in ("a", "b"):
        assert engine.state(dev_id).on is True
        assert engine.state(dev_id).brightness == 40
        assert engine.state(dev_id).rgb == (0, 0, 255)


async def test_scene_applies_palette_and_effect(engine, hass):
    await engine.async_apply_scene("派对")
    await hass.async_block_till_done()
    assert engine.scene == "派对"
    for dev_id in ("a", "b"):
        assert engine.state(dev_id).on is True
        assert engine.state(dev_id).effect == EFFECT_RAINBOW
        assert engine.state(dev_id).palette


async def test_scene_off_turns_everything_off(engine, hass):
    await engine.async_set_all(on=True)
    await engine.async_apply_scene("关闭")
    assert engine.state("a").on is False
    assert engine.state("b").on is False


async def test_audio_level_is_clamped(engine):
    await engine.async_audio_level(4.2)
    assert engine._raw_level == 1.0
    await engine.async_audio_level(-1)
    assert engine._raw_level == 0.0


async def test_unknown_device_is_ignored(engine):
    before = engine.state("a").rgb
    await engine.async_set("missing", rgb=(1, 2, 3))
    assert engine.state("a").rgb == before


async def test_solid_effect_by_default(engine):
    assert engine.state("a").effect == EFFECT_SOLID
