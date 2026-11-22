"""Config and options flows for RGB Sync."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

try:  # Home Assistant 2026.10+ migrated data_entry_flow to probatio
    from probatio import Optional, Required, Schema  # type: ignore[assignment]
except ImportError:  # pragma: no cover - older Home Assistant
    from voluptuous import Optional, Required, Schema  # type: ignore[assignment]

from .const import (
    BLE_PROFILES,
    CONF_ADDRESS,
    CONF_AUDIO_ENTITY,
    CONF_AUDIO_REACTIVE,
    CONF_BLE_PROFILE,
    CONF_BODY,
    CONF_CHAR_UUID,
    CONF_COLOR_TEMPLATE,
    CONF_CUE,
    CONF_CUE_PLAYER,
    CONF_DEVICES,
    CONF_DEVICE_ID,
    CONF_ENABLED,
    CONF_ENTITY_ID,
    CONF_QOS,
    CONF_RETAIN,
    CONF_TOPIC,
    CONF_HEADERS,
    CONF_HOST,
    CONF_LINK,
    CONF_METHOD,
    CONF_NAME,
    CONF_NET_PROTOCOL,
    CONF_PATH,
    CONF_PIXELS,
    CONF_PORT,
    CONF_POWER_OFF_HEX,
    CONF_POWER_ON_HEX,
    CONF_PROTOCOL,
    CONF_SENSITIVITY,
    CONF_SERVICE_UUID,
    CONF_SMOOTHING,
    CONF_SPEED,
    DEFAULT_BLE_CHAR_UUID,
    DEFAULT_BLE_SERVICE_UUID,
    DEFAULT_COLOR_TEMPLATE,
    DEFAULT_MQTT_BODY,
    DEFAULT_MQTT_QOS,
    DEFAULT_MQTT_RETAIN,
    DEFAULT_NET_BODY,
    DEFAULT_NET_PATH,
    DEFAULT_PIXELS,
    DEFAULT_POWER_OFF_HEX,
    DEFAULT_POWER_ON_HEX,
    DEFAULT_SENSITIVITY,
    DEFAULT_SMOOTHING,
    DEFAULT_SPEED,
    DOMAIN,
    NET_PROTOCOLS,
    PROTOCOL_BLE,
    PROTOCOL_MATTER,
    PROTOCOL_MQTT,
    PROTOCOL_NETWORK,
    PROTOCOL_WLED,
)
from .transports import async_validate_device

_LOGGER = logging.getLogger(__name__)

DEFAULT_TITLE = "全屋 RGB"


def _port_selector() -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(min=1, max=65535, mode=selector.NumberSelectorMode.BOX)
    )


def _pixels_selector() -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(min=1, max=1000, mode=selector.NumberSelectorMode.BOX)
    )


def _wled_schema(defaults: dict[str, Any] | None = None) -> Any:
    defaults = defaults or {}
    return Schema(
        {
            Required(CONF_NAME, default=defaults.get(CONF_NAME, "WLED 灯带")): str,
            Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
            Optional(CONF_PORT, default=defaults.get(CONF_PORT, 80)): _port_selector(),
            Optional(CONF_PIXELS, default=defaults.get(CONF_PIXELS, DEFAULT_PIXELS)): _pixels_selector(),
            Optional(CONF_ENABLED, default=defaults.get(CONF_ENABLED, True)): selector.BooleanSelector(),
        }
    )


def _network_schema(defaults: dict[str, Any] | None = None) -> Any:
    defaults = defaults or {}
    return Schema(
        {
            Required(CONF_NAME, default=defaults.get(CONF_NAME, "网络灯控")): str,
            Optional(CONF_NET_PROTOCOL, default=defaults.get(CONF_NET_PROTOCOL, "http")): selector.SelectSelector(
                selector.SelectSelectorConfig(options=NET_PROTOCOLS, mode=selector.SelectSelectorMode.DROPDOWN)
            ),
            Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
            Optional(CONF_PORT, default=defaults.get(CONF_PORT, 80)): _port_selector(),
            Optional(CONF_PATH, default=defaults.get(CONF_PATH, DEFAULT_NET_PATH)): str,
            Optional(CONF_METHOD, default=defaults.get(CONF_METHOD, "POST")): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["POST", "PUT", "GET"], mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
            Optional(CONF_BODY, default=defaults.get(CONF_BODY, DEFAULT_NET_BODY)): selector.TextSelector(
                selector.TextSelectorConfig(multiline=True)
            ),
            Optional(CONF_PIXELS, default=defaults.get(CONF_PIXELS, DEFAULT_PIXELS)): _pixels_selector(),
            Optional(CONF_ENABLED, default=defaults.get(CONF_ENABLED, True)): selector.BooleanSelector(),
        }
    )


def _ble_schema(defaults: dict[str, Any] | None = None) -> Any:
    defaults = defaults or {}
    return Schema(
        {
            Required(CONF_NAME, default=defaults.get(CONF_NAME, "蓝牙灯带")): str,
            Required(CONF_ADDRESS, default=defaults.get(CONF_ADDRESS, "")): str,
            Optional(CONF_BLE_PROFILE, default=defaults.get(CONF_BLE_PROFILE, "triones")): selector.SelectSelector(
                selector.SelectSelectorConfig(options=BLE_PROFILES, mode=selector.SelectSelectorMode.DROPDOWN)
            ),
            Optional(CONF_SERVICE_UUID, default=defaults.get(CONF_SERVICE_UUID, DEFAULT_BLE_SERVICE_UUID)): str,
            Optional(CONF_CHAR_UUID, default=defaults.get(CONF_CHAR_UUID, DEFAULT_BLE_CHAR_UUID)): str,
            Optional(CONF_COLOR_TEMPLATE, default=defaults.get(CONF_COLOR_TEMPLATE, DEFAULT_COLOR_TEMPLATE)): str,
            Optional(CONF_POWER_ON_HEX, default=defaults.get(CONF_POWER_ON_HEX, DEFAULT_POWER_ON_HEX)): str,
            Optional(CONF_POWER_OFF_HEX, default=defaults.get(CONF_POWER_OFF_HEX, DEFAULT_POWER_OFF_HEX)): str,
            Optional(CONF_ENABLED, default=defaults.get(CONF_ENABLED, True)): selector.BooleanSelector(),
        }
    )


def _matter_schema(defaults: dict[str, Any] | None = None) -> Any:
    defaults = defaults or {}
    return Schema(
        {
            Required(CONF_NAME, default=defaults.get(CONF_NAME, "Matter 灯")): str,
            Required(CONF_ENTITY_ID, default=defaults.get(CONF_ENTITY_ID, "")): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="light")
            ),
            Optional(CONF_ENABLED, default=defaults.get(CONF_ENABLED, True)): selector.BooleanSelector(),
        }
    )


def _mqtt_schema(defaults: dict[str, Any] | None = None) -> Any:
    defaults = defaults or {}
    return Schema(
        {
            Required(CONF_NAME, default=defaults.get(CONF_NAME, "MQTT 灯")): str,
            Required(CONF_TOPIC, default=defaults.get(CONF_TOPIC, "rgb_sync/light/state")): str,
            Optional(CONF_QOS, default=defaults.get(CONF_QOS, DEFAULT_MQTT_QOS)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=2, mode=selector.NumberSelectorMode.BOX)
            ),
            Optional(CONF_RETAIN, default=defaults.get(CONF_RETAIN, DEFAULT_MQTT_RETAIN)): selector.BooleanSelector(),
            Optional(CONF_BODY, default=defaults.get(CONF_BODY, DEFAULT_MQTT_BODY)): selector.TextSelector(
                selector.TextSelectorConfig(multiline=True)
            ),
            Optional(CONF_ENABLED, default=defaults.get(CONF_ENABLED, True)): selector.BooleanSelector(),
        }
    )


def _new_device(protocol: str, user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalise a submitted form into a stored device definition."""
    device: dict[str, Any] = {
        CONF_DEVICE_ID: uuid.uuid4().hex[:10],
        CONF_NAME: str(user_input[CONF_NAME]).strip() or "RGB",
        CONF_PROTOCOL: protocol,
        CONF_ENABLED: bool(user_input.get(CONF_ENABLED, True)),
        CONF_PIXELS: int(user_input.get(CONF_PIXELS, 1)),
    }
    if protocol == PROTOCOL_MATTER:
        device.update(
            {
                CONF_ENTITY_ID: str(user_input[CONF_ENTITY_ID]).strip().lower(),
                CONF_PIXELS: 1,
            }
        )
    elif protocol == PROTOCOL_MQTT:
        device.update(
            {
                CONF_TOPIC: str(user_input[CONF_TOPIC]).strip(),
                CONF_QOS: int(user_input.get(CONF_QOS, DEFAULT_MQTT_QOS)),
                CONF_RETAIN: bool(user_input.get(CONF_RETAIN, DEFAULT_MQTT_RETAIN)),
                CONF_BODY: str(user_input.get(CONF_BODY, DEFAULT_MQTT_BODY)),
                CONF_PIXELS: 1,
            }
        )
    elif protocol == PROTOCOL_WLED:
        device.update(
            {
                CONF_HOST: str(user_input[CONF_HOST]).strip(),
                CONF_PORT: int(user_input.get(CONF_PORT, 80)),
            }
        )
    elif protocol == PROTOCOL_NETWORK:
        device.update(
            {
                CONF_NET_PROTOCOL: str(user_input.get(CONF_NET_PROTOCOL, "http")),
                CONF_HOST: str(user_input[CONF_HOST]).strip(),
                CONF_PORT: int(user_input.get(CONF_PORT, 80)),
                CONF_PATH: str(user_input.get(CONF_PATH, DEFAULT_NET_PATH)),
                CONF_METHOD: str(user_input.get(CONF_METHOD, "POST")),
                CONF_BODY: str(user_input.get(CONF_BODY, DEFAULT_NET_BODY)),
                CONF_HEADERS: dict(user_input.get(CONF_HEADERS) or {}),
            }
        )
    else:
        device.update(
            {
                CONF_ADDRESS: str(user_input[CONF_ADDRESS]).strip().upper(),
                CONF_BLE_PROFILE: str(user_input.get(CONF_BLE_PROFILE, "triones")),
                CONF_SERVICE_UUID: str(user_input.get(CONF_SERVICE_UUID, DEFAULT_BLE_SERVICE_UUID)),
                CONF_CHAR_UUID: str(user_input.get(CONF_CHAR_UUID, DEFAULT_BLE_CHAR_UUID)),
                CONF_COLOR_TEMPLATE: str(user_input.get(CONF_COLOR_TEMPLATE, DEFAULT_COLOR_TEMPLATE)),
                CONF_POWER_ON_HEX: str(user_input.get(CONF_POWER_ON_HEX, DEFAULT_POWER_ON_HEX)),
                CONF_POWER_OFF_HEX: str(user_input.get(CONF_POWER_OFF_HEX, DEFAULT_POWER_OFF_HEX)),
                CONF_PIXELS: 1,
            }
        )
    return device


class RgbSyncConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Create the whole-house hub and its first devices."""

    VERSION = 1

    def __init__(self) -> None:
        self._name = DEFAULT_TITLE
        self._devices: list[dict[str, Any]] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            self._name = str(user_input.get(CONF_NAME) or DEFAULT_TITLE)
            return await self.async_step_add_menu()
        return self.async_show_form(
            step_id="user",
            data_schema=Schema({Required(CONF_NAME, default=DEFAULT_TITLE): str}),
        )

    async def async_step_add_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        return self.async_show_menu(
            step_id="add_menu",
            menu_options=["wled", "network", "ble", "matter", "mqtt", "finish"],
        )

    async def async_step_wled(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        return await self._async_device_step(PROTOCOL_WLED, user_input, _wled_schema())

    async def async_step_network(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        return await self._async_device_step(PROTOCOL_NETWORK, user_input, _network_schema())

    async def async_step_ble(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        return await self._async_device_step(PROTOCOL_BLE, user_input, _ble_schema())

    async def async_step_matter(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        return await self._async_device_step(PROTOCOL_MATTER, user_input, _matter_schema())

    async def async_step_mqtt(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        return await self._async_device_step(PROTOCOL_MQTT, user_input, _mqtt_schema())

    async def _async_device_step(
        self, protocol: str, user_input: dict[str, Any] | None, schema: Any
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            device = _new_device(protocol, user_input)
            error = await async_validate_device(self.hass, device)
            if error:
                return self.async_show_form(
                    step_id=protocol,
                    data_schema=schema,
                    errors={"base": error},
                )
            self._devices.append(device)
            return await self.async_step_add_menu()
        return self.async_show_form(step_id=protocol, data_schema=schema)

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if not self._devices:
            return await self.async_step_add_menu()
        return self.async_create_entry(
            title=self._name,
            data={
                CONF_DEVICES: self._devices,
                CONF_LINK: False,
                CONF_AUDIO_REACTIVE: False,
                CONF_SENSITIVITY: DEFAULT_SENSITIVITY,
                CONF_SMOOTHING: DEFAULT_SMOOTHING,
                CONF_SPEED: DEFAULT_SPEED,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return RgbSyncOptionsFlow()


class RgbSyncOptionsFlow(config_entries.OptionsFlow):
    """Add / edit / remove devices and change hub behaviour."""

    def __init__(self) -> None:
        self._devices: list[dict[str, Any]] = []
        self._options: dict[str, Any] = {}
        self._edit_id: str | None = None
        self._initialized = False

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        if not self._initialized:
            entry = self.config_entry
            data = dict(entry.options or entry.data)
            self._devices = [dict(device) for device in data.get(CONF_DEVICES, [])]
            self._options = {
                CONF_DEVICES: self._devices,
                CONF_LINK: bool(data.get(CONF_LINK, False)),
                CONF_AUDIO_REACTIVE: bool(data.get(CONF_AUDIO_REACTIVE, False)),
                CONF_AUDIO_ENTITY: data.get(CONF_AUDIO_ENTITY),
                CONF_CUE: bool(data.get(CONF_CUE, False)),
                CONF_CUE_PLAYER: data.get(CONF_CUE_PLAYER),
                CONF_SENSITIVITY: int(data.get(CONF_SENSITIVITY, DEFAULT_SENSITIVITY)),
                CONF_SMOOTHING: int(data.get(CONF_SMOOTHING, DEFAULT_SMOOTHING)),
                CONF_SPEED: int(data.get(CONF_SPEED, DEFAULT_SPEED)),
            }
            self._initialized = True
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "add_wled",
                "add_network",
                "add_ble",
                "add_matter",
                "add_mqtt",
                "edit",
                "remove",
                "settings",
                "save",
            ],
        )

    async def async_step_add_wled(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        return await self._async_add(PROTOCOL_WLED, user_input, _wled_schema())

    async def async_step_add_network(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        return await self._async_add(PROTOCOL_NETWORK, user_input, _network_schema())

    async def async_step_add_ble(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        return await self._async_add(PROTOCOL_BLE, user_input, _ble_schema(), step="add_ble")

    async def async_step_add_matter(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        return await self._async_add(PROTOCOL_MATTER, user_input, _matter_schema(), step="add_matter")

    async def async_step_add_mqtt(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        return await self._async_add(PROTOCOL_MQTT, user_input, _mqtt_schema(), step="add_mqtt")

    async def _async_add(
        self, protocol: str, user_input: dict[str, Any] | None, schema: Any, step: str | None = None
    ) -> config_entries.ConfigFlowResult:
        step = step or f"add_{protocol}"
        if user_input is not None:
            device = _new_device(protocol, user_input)
            error = await async_validate_device(self.hass, device)
            if error:
                return self.async_show_form(step_id=step, data_schema=schema, errors={"base": error})
            self._devices.append(device)
            return await self.async_step_init()
        return self.async_show_form(step_id=step, data_schema=schema)

    async def async_step_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if not self._devices:
            return await self.async_step_init()
        if user_input is not None:
            self._edit_id = str(user_input[CONF_DEVICE_ID])
            device = self._device(self._edit_id)
            if device is None:
                return await self.async_step_init()
            schema = self._edit_schema(device)
            return self.async_show_form(
                step_id="edit_device",
                data_schema=schema,
                description_placeholders={"name": str(device.get(CONF_NAME))},
            )
        return self.async_show_form(
            step_id="edit",
            data_schema=Schema({Required(CONF_DEVICE_ID): self._device_selector()}),
        )

    async def async_step_edit_device(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        device = self._device(self._edit_id) if self._edit_id else None
        if device is None:
            return await self.async_step_init()
        if user_input is not None:
            device[CONF_NAME] = str(user_input[CONF_NAME]).strip() or device.get(CONF_NAME, "RGB")
            device[CONF_ENABLED] = bool(user_input[CONF_ENABLED])
            protocol = device.get(CONF_PROTOCOL)
            if protocol == PROTOCOL_BLE:
                device[CONF_ADDRESS] = str(user_input.get(CONF_ADDRESS, device.get(CONF_ADDRESS))).upper()
            elif protocol == PROTOCOL_MATTER:
                device[CONF_ENTITY_ID] = str(
                    user_input.get(CONF_ENTITY_ID, device.get(CONF_ENTITY_ID, ""))
                ).strip().lower()
            elif protocol == PROTOCOL_MQTT:
                device[CONF_TOPIC] = str(user_input.get(CONF_TOPIC, device.get(CONF_TOPIC, ""))).strip()
                device[CONF_QOS] = int(user_input.get(CONF_QOS, device.get(CONF_QOS, DEFAULT_MQTT_QOS)))
                device[CONF_RETAIN] = bool(user_input.get(CONF_RETAIN, device.get(CONF_RETAIN, False)))
            else:
                device[CONF_HOST] = str(user_input.get(CONF_HOST, device.get(CONF_HOST, ""))).strip()
                device[CONF_PORT] = int(user_input.get(CONF_PORT, device.get(CONF_PORT, 80)))
                device[CONF_PIXELS] = int(user_input.get(CONF_PIXELS, device.get(CONF_PIXELS, 1)))
            return await self.async_step_init()
        return self.async_show_form(step_id="edit_device", data_schema=self._edit_schema(device))

    async def async_step_remove(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if not self._devices:
            return await self.async_step_init()
        if user_input is not None:
            target = str(user_input[CONF_DEVICE_ID])
            self._devices[:] = [device for device in self._devices if device.get(CONF_DEVICE_ID) != target]
            self._options[CONF_DEVICES] = self._devices
            return await self.async_step_init()
        return self.async_show_form(
            step_id="remove",
            data_schema=Schema({Required(CONF_DEVICE_ID): self._device_selector()}),
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            self._options.update(
                {
                    CONF_LINK: bool(user_input.get(CONF_LINK, False)),
                    CONF_AUDIO_REACTIVE: bool(user_input.get(CONF_AUDIO_REACTIVE, False)),
                    CONF_AUDIO_ENTITY: user_input.get(CONF_AUDIO_ENTITY) or None,
                    CONF_CUE: bool(user_input.get(CONF_CUE, False)),
                    CONF_CUE_PLAYER: user_input.get(CONF_CUE_PLAYER) or None,
                    CONF_SENSITIVITY: int(user_input.get(CONF_SENSITIVITY, DEFAULT_SENSITIVITY)),
                    CONF_SMOOTHING: int(user_input.get(CONF_SMOOTHING, DEFAULT_SMOOTHING)),
                    CONF_SPEED: int(user_input.get(CONF_SPEED, DEFAULT_SPEED)),
                }
            )
            return await self.async_step_init()
        return self.async_show_form(step_id="settings", data_schema=self._settings_schema())

    async def async_step_save(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        self._options[CONF_DEVICES] = self._devices
        return self.async_create_entry(title="", data=self._options)

    # -- helpers -------------------------------------------------------
    def _device(self, dev_id: str) -> dict[str, Any] | None:
        for device in self._devices:
            if str(device.get(CONF_DEVICE_ID)) == dev_id:
                return device
        return None

    def _device_selector(self) -> selector.SelectSelector:
        options = [
            selector.SelectOptionDict(
                value=str(device.get(CONF_DEVICE_ID)),
                label=f"{device.get(CONF_NAME)} ({device.get(CONF_PROTOCOL)})",
            )
            for device in self._devices
        ]
        return selector.SelectSelector(
            selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.DROPDOWN)
        )

    @staticmethod
    def _edit_schema(device: dict[str, Any]) -> Any:
        fields: dict[Any, Any] = {
            Required(CONF_NAME, default=device.get(CONF_NAME, "RGB")): str,
            Optional(CONF_ENABLED, default=device.get(CONF_ENABLED, True)): selector.BooleanSelector(),
        }
        protocol = device.get(CONF_PROTOCOL)
        if protocol == PROTOCOL_BLE:
            fields[Optional(CONF_ADDRESS, default=device.get(CONF_ADDRESS, ""))] = str
        elif protocol == PROTOCOL_MATTER:
            fields[Optional(CONF_ENTITY_ID, default=device.get(CONF_ENTITY_ID, ""))] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="light")
            )
        elif protocol == PROTOCOL_MQTT:
            fields[Optional(CONF_TOPIC, default=device.get(CONF_TOPIC, ""))] = str
            fields[Optional(CONF_QOS, default=device.get(CONF_QOS, DEFAULT_MQTT_QOS))] = selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=2, mode=selector.NumberSelectorMode.BOX)
            )
            fields[Optional(CONF_RETAIN, default=device.get(CONF_RETAIN, False))] = selector.BooleanSelector()
        else:
            fields[Optional(CONF_HOST, default=device.get(CONF_HOST, ""))] = str
            fields[Optional(CONF_PORT, default=device.get(CONF_PORT, 80))] = _port_selector()
            fields[Optional(CONF_PIXELS, default=device.get(CONF_PIXELS, 1))] = _pixels_selector()
        return Schema(fields)

    def _settings_schema(self) -> Any:
        return Schema(
            {
                Optional(CONF_LINK, default=self._options.get(CONF_LINK, False)): selector.BooleanSelector(),
                Optional(
                    CONF_AUDIO_REACTIVE, default=self._options.get(CONF_AUDIO_REACTIVE, False)
                ): selector.BooleanSelector(),
                Optional(CONF_AUDIO_ENTITY, default=self._options.get(CONF_AUDIO_ENTITY) or ""): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["sensor", "input_number"])
                ),
                Optional(CONF_CUE, default=self._options.get(CONF_CUE, False)): selector.BooleanSelector(),
                Optional(CONF_CUE_PLAYER, default=self._options.get(CONF_CUE_PLAYER) or ""): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="media_player")
                ),
                Optional(
                    CONF_SENSITIVITY, default=self._options.get(CONF_SENSITIVITY, DEFAULT_SENSITIVITY)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=100, mode=selector.NumberSelectorMode.SLIDER)
                ),
                Optional(
                    CONF_SMOOTHING, default=self._options.get(CONF_SMOOTHING, DEFAULT_SMOOTHING)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=95, mode=selector.NumberSelectorMode.SLIDER)
                ),
                Optional(
                    CONF_SPEED, default=self._options.get(CONF_SPEED, DEFAULT_SPEED)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=100, mode=selector.NumberSelectorMode.SLIDER)
                ),
            }
        )


__all__ = ["RgbSyncConfigFlow", "RgbSyncOptionsFlow"]
