"""Software light-effect renderer shared by every transport.

The renderer is pure: it maps ``(effect, time, pixel index)`` to a colour so
that the same effect looks identical on WLED strips, generic network
controllers and BLE controllers.
"""

from __future__ import annotations

import colorsys
import math
from typing import Iterable

from .const import (
    DEFAULT_PALETTE,
    EFFECT_AUDIO_PULSE,
    EFFECT_AURORA,
    EFFECT_BREATHE,
    EFFECT_CANDLE,
    EFFECT_CHASE,
    EFFECT_GRADIENT,
    EFFECT_RAINBOW,
    EFFECT_SPARKLE,
    EFFECT_STROBE,
    EFFECT_VU_METER,
)

RGB = tuple[int, int, int]


def hex_to_rgb(value: str) -> RGB:
    """Convert ``#rrggbb`` / ``rrggbb`` to an RGB tuple."""
    text = str(value).strip().lstrip("#")
    if len(text) == 3:
        text = "".join(char * 2 for char in text)
    if len(text) != 6:
        return (255, 255, 255)
    try:
        return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))
    except ValueError:
        return (255, 255, 255)


def rgb_to_hex(color: RGB) -> str:
    """Convert an RGB tuple to ``#rrggbb``."""
    return "#" + "".join(f"{max(0, min(255, int(channel))):02x}" for channel in color)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def scale(color: RGB, factor: float) -> RGB:
    """Scale a colour by ``factor`` (0..1)."""
    factor = _clamp(factor)
    return (
        int(color[0] * factor),
        int(color[1] * factor),
        int(color[2] * factor),
    )


def blend(first: RGB, second: RGB, ratio: float) -> RGB:
    """Linear blend between two colours."""
    ratio = _clamp(ratio)
    return (
        int(first[0] + (second[0] - first[0]) * ratio),
        int(first[1] + (second[1] - first[1]) * ratio),
        int(first[2] + (second[2] - first[2]) * ratio),
    )


def hsv(hue: float, saturation: float, value: float) -> RGB:
    """HSV (all 0..1) to RGB."""
    red, green, blue = colorsys.hsv_to_rgb(_clamp(hue), _clamp(saturation), _clamp(value))
    return (int(red * 255), int(green * 255), int(blue * 255))


def normalise_palette(palette: Iterable[str] | None, fallback: RGB = (255, 255, 255)) -> list[RGB]:
    """Turn a list of hex strings into RGB tuples."""
    colors = [hex_to_rgb(item) for item in (palette or []) if str(item).strip()]
    if not colors:
        colors = [hex_to_rgb(item) for item in DEFAULT_PALETTE]
    if not colors:
        colors = [fallback]
    return colors


def palette_at(colors: list[RGB], position: float) -> RGB:
    """Sample a wrapped palette at ``position`` (0..1)."""
    if len(colors) == 1:
        return colors[0]
    position = position % 1.0
    scaled = position * len(colors)
    index = int(scaled)
    ratio = scaled - index
    return blend(colors[index % len(colors)], colors[(index + 1) % len(colors)], ratio)


def _rate(speed: int) -> float:
    """Map a 1..100 speed slider to an animation rate multiplier."""
    return 0.15 + _clamp(float(speed) / 100.0) * 2.85


def _spark(position: float, seed: int, t: float) -> float:
    """Deterministic flicker value in 0..1 for a pixel."""
    noise = math.sin((position * 977.0 + seed * 131.0 + t * 7.3) * 12.9898) * 43758.5453
    return abs(noise - math.floor(noise))


def render(
    effect: str,
    *,
    t: float,
    count: int,
    base: RGB,
    palette: list[str] | None = None,
    level: float = 0.0,
    speed: int = 50,
    brightness: int = 255,
) -> list[RGB]:
    """Render one frame of ``effect`` as ``count`` colours."""
    count = max(1, int(count))
    colors = normalise_palette(palette, base)
    rate = _rate(speed)
    factor = _clamp(float(brightness) / 255.0)
    level = _clamp(level)

    if effect == EFFECT_RAINBOW:
        hues = [(index / count + t * rate * 0.18) % 1.0 for index in range(count)]
        frame = [hsv(hue, 1.0, 1.0) for hue in hues]
    elif effect == EFFECT_CHASE:
        head = (t * rate * 0.35) % 1.0
        frame = []
        for index in range(count):
            distance = abs((index / count) - head)
            distance = min(distance, 1.0 - distance)
            intensity = math.exp(-(distance ** 2) * 18.0)
            frame.append(scale(palette_at(colors, index / count), 0.05 + 0.95 * intensity))
    elif effect == EFFECT_BREATHE:
        wave = 0.5 - 0.5 * math.cos(2 * math.pi * 0.12 * rate * t)
        frame = [scale(palette_at(colors, index / count), 0.06 + 0.94 * wave) for index in range(count)]
    elif effect == EFFECT_CANDLE:
        frame = []
        for index in range(count):
            flicker = (
                0.75
                + 0.12 * math.sin(t * 7.0 + index)
                + 0.08 * math.sin(t * 13.7 + index * 2.1)
                + 0.05 * _spark(index / max(1, count), 3, t)
            )
            color = palette_at(colors, 0.08 * _spark(index, 5, t))
            frame.append(scale(color, _clamp(flicker)))
    elif effect == EFFECT_STROBE:
        frequency = 3.0 + _clamp(float(speed) / 100.0) * 17.0
        gate = 1.0 if (t * frequency) % 1.0 < 0.35 else 0.0
        frame = [scale(palette_at(colors, 0.5), gate) for _ in range(count)]
    elif effect == EFFECT_AURORA:
        frame = []
        for index in range(count):
            position = index / count
            drift = position * 0.7 + t * rate * 0.08
            wave = 0.55 + 0.45 * math.sin(2 * math.pi * (position * 1.7 - t * rate * 0.12))
            frame.append(scale(palette_at(colors, drift), wave))
    elif effect == EFFECT_AUDIO_PULSE:
        pulse = 0.08 + 0.92 * level
        frame = [scale(palette_at(colors, index / count), pulse) for index in range(count)]
    elif effect == EFFECT_VU_METER:
        filled = level * count
        frame = []
        for index in range(count):
            if index < filled:
                frame.append(scale(palette_at(colors, index / count), 1.0))
            elif index == int(filled):
                frame.append(scale(palette_at(colors, index / count), filled - int(filled)))
            else:
                frame.append((0, 0, 0))
    elif effect == EFFECT_SPARKLE:
        frame = []
        for index in range(count):
            sparkle = _spark(index / max(1, count), 11, t * rate)
            intensity = sparkle if sparkle > 0.72 else 0.02
            frame.append(scale(palette_at(colors, index / count), intensity))
    elif effect == EFFECT_GRADIENT:
        frame = [
            scale(palette_at(colors, index / count + t * rate * 0.05), 1.0)
            for index in range(count)
        ]
    else:  # EFFECT_SOLID and unknown names
        frame = [base for _ in range(count)]

    return [scale(color, factor) for color in frame]


def dominant(frame: list[RGB]) -> RGB:
    """Pick a representative colour for single-colour controllers."""
    lit = [color for color in frame if color[0] or color[1] or color[2]]
    if not lit:
        return (0, 0, 0)
    red = sum(color[0] for color in lit) // len(lit)
    green = sum(color[1] for color in lit) // len(lit)
    blue = sum(color[2] for color in lit) // len(lit)
    return (red, green, blue)
