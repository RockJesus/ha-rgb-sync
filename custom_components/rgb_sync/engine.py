"""Synchronisation engine: owns devices, state, effects and audio feedback."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import replace
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.network import get_url

from .const import (
    AUDIO_EFFECTS,
    BEEP_PATH,
    CONF_AUDIO_ENTITY,
    CONF_AUDIO_REACTIVE,
    CONF_CUE,
    CONF_CUE_PLAYER,
    CONF_DEVICES,
    CONF_LINK,
    CONF_SENSITIVITY,
    CONF_SMOOTHING,
    CONF_SPEED,
    DEFAULT_FPS,
    DEFAULT_PALETTE,
    DEFAULT_SENSITIVITY,
    DEFAULT_SMOOTHING,
    DEFAULT_SPEED,
    DOMAIN,
    EFFECT_SOLID,
    PROBE_INTERVAL,
    SCENES,
)
from .effects import hex_to_rgb, render
from .models import DeviceState, device_enabled, device_name, device_pixels
from .transports import create_transport
from .transports.base import BaseTransport, TransportError

_LOGGER = logging.getLogger(__name__)

RGB = tuple[int, int, int]


class SyncEngine:
    """Central state store and fan-out for every configured device."""

    def __init__(self, hass: HomeAssistant, entry: Any) -> None:
        self.hass = hass
        self.entry = entry
        options = entry.options or {}
        data = entry.data or {}
        self.devices: list[dict[str, Any]] = list(options.get(CONF_DEVICES, data.get(CONF_DEVICES, [])))
        self.states: dict[str, DeviceState] = {}
        self.transports: dict[str, BaseTransport] = {}

        self.link: bool = bool(options.get(CONF_LINK, False))
        self.audio_reactive: bool = bool(options.get(CONF_AUDIO_REACTIVE, False))
        self.audio_entity: str | None = options.get(CONF_AUDIO_ENTITY) or None
        self.cue_enabled: bool = bool(options.get(CONF_CUE, False))
        self.cue_player: str | None = options.get(CONF_CUE_PLAYER) or None
        self.sensitivity: int = int(options.get(CONF_SENSITIVITY, DEFAULT_SENSITIVITY))
        self.smoothing: int = int(options.get(CONF_SMOOTHING, DEFAULT_SMOOTHING))
        self.speed: int = int(options.get(CONF_SPEED, DEFAULT_SPEED))

        self.audio_level: float = 0.0
        self.audio_bands: list[float] = []
        self.fps: float = 0.0
        self.scene: str = "自定义"

        self._raw_level: float = 0.0
        self._listeners: list[Callable[[], None]] = []
        self._tick_task: asyncio.Task[None] | None = None
        self._tasks: set[asyncio.Task[Any]] = set()
        self._inflight: set[str] = set()
        self._started_at = time.monotonic()
        self._last_cue = 0.0
        self._last_probe = 0.0
        self._frame_count = 0
        self._closing = False

    # ------------------------------------------------------------------
    # Setup / teardown
    # ------------------------------------------------------------------
    async def async_start(self) -> None:
        for device in self.devices:
            dev_id = str(device.get("id"))
            self.states[dev_id] = DeviceState()
            try:
                transport = create_transport(self.hass, device)
                await transport.async_setup()
            except TransportError as err:
                _LOGGER.warning("Device %s could not be prepared: %s", device_name(device), err)
                continue
            self.transports[dev_id] = transport

        self._started_at = time.monotonic()
        await self.async_ping()
        self._tick_task = self.hass.async_create_background_task(
            self._async_tick(), f"{DOMAIN}_tick", eager_start=False
        )

    async def async_stop(self) -> None:
        self._closing = True
        if self._tick_task is not None:
            self._tick_task.cancel()
            self._tick_task = None
        for task in list(self._tasks):
            task.cancel()
        self._tasks.clear()
        for transport in self.transports.values():
            await transport.async_close()
        self.transports.clear()
        self._listeners.clear()

    # ------------------------------------------------------------------
    # Listener plumbing
    # ------------------------------------------------------------------
    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(listener)

        @callback
        def _remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return _remove

    @callback
    def async_notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def device(self, dev_id: str) -> dict[str, Any] | None:
        for device in self.devices:
            if str(device.get("id")) == dev_id:
                return device
        return None

    def enabled_devices(self) -> list[dict[str, Any]]:
        return [device for device in self.devices if device_enabled(device)]

    def state(self, dev_id: str) -> DeviceState:
        return self.states.setdefault(dev_id, DeviceState())

    @property
    def any_on(self) -> bool:
        return any(self.state(str(device["id"])).on for device in self.enabled_devices())

    @property
    def online_count(self) -> int:
        return sum(1 for transport in self.transports.values() if transport.online)

    def representative(self) -> DeviceState | None:
        enabled = self.enabled_devices()
        if not enabled:
            return None
        return self.state(str(enabled[0]["id"]))

    def common_effect(self) -> str:
        effects = {self.state(str(device["id"])).effect for device in self.enabled_devices()}
        return effects.pop() if len(effects) == 1 else EFFECT_SOLID

    # ------------------------------------------------------------------
    # State changes
    # ------------------------------------------------------------------
    async def async_set(
        self,
        dev_id: str,
        *,
        on: bool | None = None,
        brightness: int | None = None,
        rgb: RGB | None = None,
        effect: str | None = None,
        speed: int | None = None,
        palette: list[str] | None = None,
        source: str = "user",
        propagate: bool = True,
    ) -> None:
        device = self.device(dev_id)
        if device is None or not device_enabled(device):
            return

        targets = [dev_id]
        # Colour / effect / brightness follow the whole-house link. Power stays
        # per-device so that individual switches keep working.
        if propagate and self.link and source == "user":
            targets = [str(item["id"]) for item in self.enabled_devices()]

        for target in targets:
            state = self.state(target)
            if on is not None:
                state.on = on
            if brightness is not None:
                state.brightness = max(0, min(255, int(brightness)))
            if rgb is not None:
                state.rgb = (int(rgb[0]), int(rgb[1]), int(rgb[2]))
            if effect is not None:
                state.effect = effect
            if speed is not None:
                state.speed = max(1, min(100, int(speed)))
            if palette is not None:
                state.palette = list(palette)
            self._schedule_apply(target)

        self.async_notify()
        if source in ("user", "group"):
            self._frame_count = 0
            await self.async_cue()

    async def async_set_all(
        self,
        *,
        on: bool | None = None,
        brightness: int | None = None,
        rgb: RGB | None = None,
        effect: str | None = None,
        speed: int | None = None,
        palette: list[str] | None = None,
        source: str = "group",
    ) -> None:
        for device in self.enabled_devices():
            await self.async_set(
                str(device["id"]),
                on=on,
                brightness=brightness,
                rgb=rgb,
                effect=effect,
                speed=speed,
                palette=palette,
                source=source,
                propagate=False,
            )

    async def async_apply_scene(self, name: str) -> None:
        scene = SCENES.get(name)
        if not scene:
            raise ValueError(f"unknown scene {name}")
        self.scene = name
        palette = [str(color) for color in scene.get("palette", DEFAULT_PALETTE)]
        brightness = scene.get("brightness")
        effect = str(scene.get("effect", EFFECT_SOLID))
        speed = scene.get("speed")
        if brightness == 0:
            await self.async_set_all(on=False, source="user")
            return
        await self.async_set_all(
            on=True,
            brightness=int(brightness) if brightness is not None else None,
            rgb=hex_to_rgb(palette[0]),
            palette=palette,
            effect=effect,
            speed=int(speed) if speed is not None else None,
            source="user",
        )

    async def async_set_option(self, key: str, value: Any) -> None:
        if key == CONF_LINK:
            self.link = bool(value)
        elif key == CONF_AUDIO_REACTIVE:
            self.audio_reactive = bool(value)
            if not value:
                self.audio_level = 0.0
                self._raw_level = 0.0
        elif key == CONF_CUE:
            self.cue_enabled = bool(value)
        elif key == CONF_SENSITIVITY:
            self.sensitivity = max(0, min(100, int(value)))
        elif key == CONF_SMOOTHING:
            self.smoothing = max(0, min(95, int(value)))
        elif key == CONF_SPEED:
            self.speed = max(1, min(100, int(value)))
        self.async_notify()

    # ------------------------------------------------------------------
    # Audio
    # ------------------------------------------------------------------
    async def async_audio_level(self, level: float, bands: list[float] | None = None) -> None:
        self._raw_level = max(0.0, min(1.0, float(level)))
        if bands is not None:
            self.audio_bands = [max(0.0, min(1.0, float(value))) for value in bands][:48]

    def _read_audio_entity(self) -> float:
        if not self.audio_entity:
            return self._raw_level
        state = self.hass.states.get(self.audio_entity)
        if state is None or state.state in ("unknown", "unavailable"):
            return 0.0
        try:
            value = float(state.state)
        except (TypeError, ValueError):
            return 0.0
        unit = state.attributes.get("unit_of_measurement")
        if unit == "%":
            return max(0.0, min(1.0, value / 100.0))
        if value <= 1.0:
            return max(0.0, value)
        return max(0.0, min(1.0, value / 255.0))

    # ------------------------------------------------------------------
    # Feedback
    # ------------------------------------------------------------------
    async def async_cue(self, force: bool = False) -> None:
        if not self.cue_enabled and not force:
            return
        if not self.cue_player:
            return
        now = time.monotonic()
        if not force and now - self._last_cue < 1.5:
            return
        self._last_cue = now
        try:
            base = get_url(self.hass, prefer_external=False, allow_internal=True)
        except Exception:  # noqa: BLE001 - URL lookup is best effort
            base = ""
        if not base:
            return
        try:
            await self.hass.services.async_call(
                "media_player",
                "play_media",
                {
                    "entity_id": self.cue_player,
                    "media_content_id": f"{base}{BEEP_PATH}",
                    "media_content_type": "music",
                },
                blocking=False,
            )
        except Exception as err:  # noqa: BLE001 - cue must never break control
            _LOGGER.debug("Cue playback failed: %s", err)

    async def async_identify(self, dev_id: str | None = None) -> None:
        targets = [dev_id] if dev_id else [str(device["id"]) for device in self.enabled_devices()]
        previous = {target: replace(self.state(target)) for target in targets if target in self.states}
        for target in targets:
            if target not in self.states:
                continue
            self.states[target].on = True
            self.states[target].brightness = 255
            self.states[target].rgb = (255, 255, 255)
            self.states[target].effect = EFFECT_SOLID
            self._schedule_apply(target)
        self.async_notify()

        async def _restore() -> None:
            await asyncio.sleep(1.2)
            for target, state in previous.items():
                self.states[target] = state
                self._schedule_apply(target)
            self.async_notify()

        self.hass.async_create_task(_restore())

    # ------------------------------------------------------------------
    # Probing
    # ------------------------------------------------------------------
    async def async_ping(self) -> None:
        self._last_probe = time.monotonic()

        async def _probe(transport: BaseTransport) -> None:
            try:
                await transport.async_probe()
            except Exception as err:  # noqa: BLE001 - a probe must never raise
                _LOGGER.debug("Probe failed: %s", err)

        await asyncio.gather(*(_probe(transport) for transport in self.transports.values()))
        self.async_notify()

    # ------------------------------------------------------------------
    # Frame loop
    # ------------------------------------------------------------------
    def _schedule_apply(self, dev_id: str) -> None:
        transport = self.transports.get(dev_id)
        if transport is None:
            return
        state = self.state(dev_id)
        task = self.hass.async_create_task(self._async_apply(transport, state))
        self._track(task)

    async def _async_apply(self, transport: BaseTransport, state: DeviceState) -> None:
        try:
            await transport.async_apply(state)
        except TransportError as err:
            _LOGGER.debug("Apply failed on %s: %s", transport.device_id, err)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Unexpected apply error on %s: %s", transport.device_id, err)
        self.async_notify()

    def _track(self, task: asyncio.Task[Any]) -> None:
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _async_tick(self) -> None:
        frame_interval = 1.0 / DEFAULT_FPS
        while not self._closing:
            started = time.monotonic()
            t = started - self._started_at

            if self.audio_reactive and self.audio_entity:
                self._raw_level = self._read_audio_entity()
            target_level = self._raw_level * (self.sensitivity / 100.0) * 1.6
            target_level = max(0.0, min(1.0, target_level))
            alpha = max(0.05, 1.0 - self.smoothing / 100.0)
            self.audio_level += (target_level - self.audio_level) * alpha
            if not self.audio_reactive:
                self.audio_level = 0.0
            self._raw_level *= 0.92

            for device in self.enabled_devices():
                dev_id = str(device["id"])
                transport = self.transports.get(dev_id)
                state = self.state(dev_id)
                if transport is None or not state.on:
                    continue
                if state.effect == EFFECT_SOLID and state.effect not in AUDIO_EFFECTS:
                    continue
                if dev_id in self._inflight:
                    continue
                count = device_pixels(device) if device.get("protocol") != "ble" else 1
                frame = render(
                    state.effect,
                    t=t,
                    count=count,
                    base=state.rgb,
                    palette=state.palette or [self._rgb_hex(state.rgb)],
                    level=self.audio_level,
                    speed=state.speed or self.speed,
                    brightness=state.brightness,
                )
                self._inflight.add(dev_id)
                task = self.hass.async_create_task(self._async_frame(transport, frame, state, dev_id))
                self._track(task)

            self._frame_count += 1
            elapsed = time.monotonic() - started
            self.fps = round(1.0 / elapsed, 1) if elapsed > 0 else 0.0
            if self._frame_count % 20 == 0:
                self.async_notify()
            if time.monotonic() - self._last_probe > PROBE_INTERVAL:
                self.hass.async_create_task(self.async_ping())
                self._last_probe = time.monotonic()

            await asyncio.sleep(max(0.0, frame_interval - (time.monotonic() - started)))

    async def _async_frame(
        self, transport: BaseTransport, frame: list[RGB], state: DeviceState, dev_id: str
    ) -> None:
        try:
            await transport.async_frame(frame, state)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Frame failed on %s: %s", dev_id, err)
        finally:
            self._inflight.discard(dev_id)

    @staticmethod
    def _rgb_hex(rgb: RGB) -> str:
        return "#{:02x}{:02x}{:02x}".format(*rgb)
