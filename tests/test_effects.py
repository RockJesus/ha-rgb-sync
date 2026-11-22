"""Pure tests for the effect renderer."""

from custom_components.rgb_sync.effects import (
    blend,
    dominant,
    hex_to_rgb,
    hsv,
    normalise_palette,
    palette_at,
    render,
    rgb_to_hex,
    scale,
)


def test_hex_roundtrip():
    assert hex_to_rgb("#ff004d") == (255, 0, 77)
    assert hex_to_rgb("00ff00") == (0, 255, 0)
    assert hex_to_rgb("#abc") == (170, 187, 204)
    assert rgb_to_hex((255, 0, 77)) == "#ff004d"
    assert hex_to_rgb("not-a-colour") == (255, 255, 255)


def test_scale_and_blend_clamp():
    assert scale((200, 100, 50), 1.5) == (200, 100, 50)
    assert scale((200, 100, 50), 0.5) == (100, 50, 25)
    assert blend((0, 0, 0), (255, 255, 255), 0.5) == (127, 127, 127)


def test_palette_wraps():
    colours = normalise_palette(["#ff0000", "#00ff00"])
    assert palette_at(colours, 0.0) == (255, 0, 0)
    assert palette_at(colours, 0.25) == (127, 127, 0)
    assert palette_at(colours, 0.5) == (0, 255, 0)
    assert palette_at(colours, 1.0) == (255, 0, 0)
    assert palette_at([(10, 20, 30)], 0.9) == (10, 20, 30)


def test_solid_respects_brightness():
    frame = render("固定", t=1.0, count=4, base=(200, 100, 40), brightness=128)
    assert len(frame) == 4
    assert frame[0] == (100, 50, 20)


def test_rainbow_is_colourful():
    frame = render("彩虹", t=0.5, count=8, base=(255, 255, 255), speed=50)
    assert len(frame) == 8
    assert len({colour for colour in frame}) > 3


def test_vu_meter_fills_from_level():
    frame = render("电平条", t=0.0, count=10, base=(255, 255, 255), palette=["#00ff00"], level=0.5)
    lit = [colour for colour in frame if colour != (0, 0, 0)]
    assert len(lit) == 5


def test_audio_pulse_uses_level():
    quiet = render("声控脉冲", t=0.0, count=2, base=(255, 255, 255), palette=["#ffffff"], level=0.0)
    loud = render("声控脉冲", t=0.0, count=2, base=(255, 255, 255), palette=["#ffffff"], level=1.0)
    assert quiet[0][0] < 30
    assert loud[0][0] > 240


def test_unknown_effect_falls_back_to_solid():
    frame = render("does-not-exist", t=0.0, count=2, base=(1, 2, 3), brightness=255)
    assert frame == [(1, 2, 3), (1, 2, 3)]


def test_dominant_average():
    assert dominant([(255, 0, 0), (0, 255, 0)]) == (127, 127, 0)
    assert dominant([(0, 0, 0)]) == (0, 0, 0)


def test_hsv_primary():
    assert hsv(0.0, 1.0, 1.0) == (255, 0, 0)
