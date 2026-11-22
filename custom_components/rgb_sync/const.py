"""Constants for the RGB Sync integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "rgb_sync"
NAME: Final = "RGB Sync"
VERSION: Final = "1.0.5"

PLATFORMS: Final = ["button", "light", "number", "select", "sensor", "switch"]

# ---------------------------------------------------------------------------
# Configuration keys
# ---------------------------------------------------------------------------
CONF_DEVICES: Final = "devices"
CONF_NAME: Final = "name"
CONF_LINK: Final = "link"
CONF_AUDIO_REACTIVE: Final = "audio_reactive"
CONF_AUDIO_ENTITY: Final = "audio_entity"
CONF_CUE: Final = "cue"
CONF_CUE_PLAYER: Final = "cue_player"
CONF_SENSITIVITY: Final = "sensitivity"
CONF_SMOOTHING: Final = "smoothing"
CONF_SPEED: Final = "speed"
CONF_SCENE: Final = "scene"
CONF_AUTO_ADD: Final = "auto_add"
CONF_CANDIDATES: Final = "candidates"

CONF_DEVICE_ID: Final = "id"
CONF_PROTOCOL: Final = "protocol"
CONF_PIXELS: Final = "pixels"
CONF_ENABLED: Final = "enabled"

CONF_HOST: Final = "host"
CONF_PORT: Final = "port"
CONF_PATH: Final = "path"
CONF_METHOD: Final = "method"
CONF_HEADERS: Final = "headers"
CONF_BODY: Final = "body"
CONF_CONTENT_TYPE: Final = "content_type"
CONF_NET_PROTOCOL: Final = "net_protocol"
CONF_APPEND_NEWLINE: Final = "append_newline"
CONF_ALLOW_HTTP_FRAMES: Final = "allow_http_frames"

CONF_ADDRESS: Final = "address"
CONF_BLE_PROFILE: Final = "ble_profile"
CONF_SERVICE_UUID: Final = "service_uuid"
CONF_CHAR_UUID: Final = "char_uuid"
CONF_POWER_ON_HEX: Final = "power_on_hex"
CONF_POWER_OFF_HEX: Final = "power_off_hex"
CONF_COLOR_TEMPLATE: Final = "color_template"
CONF_ENTITY_ID: Final = "entity_id"
CONF_TOPIC: Final = "topic"
CONF_QOS: Final = "qos"
CONF_RETAIN: Final = "retain"

# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------
PROTOCOL_WLED: Final = "wled"
PROTOCOL_NETWORK: Final = "network"
PROTOCOL_BLE: Final = "ble"
PROTOCOL_MATTER: Final = "matter"
PROTOCOL_MQTT: Final = "mqtt"
PROTOCOLS: Final = [
    PROTOCOL_WLED,
    PROTOCOL_NETWORK,
    PROTOCOL_BLE,
    PROTOCOL_MATTER,
    PROTOCOL_MQTT,
]

NET_HTTP: Final = "http"
NET_TCP: Final = "tcp"
NET_UDP: Final = "udp"
NET_PROTOCOLS: Final = [NET_HTTP, NET_TCP, NET_UDP]

BLE_PROFILE_TRIONES: Final = "triones"
BLE_PROFILE_GENERIC: Final = "generic"
BLE_PROFILES: Final = [BLE_PROFILE_TRIONES, BLE_PROFILE_GENERIC]

DEFAULT_BLE_SERVICE_UUID: Final = "0000fff0-0000-1000-8000-00805f9b34fb"
DEFAULT_BLE_CHAR_UUID: Final = "0000fff3-0000-1000-8000-00805f9b34fb"
# Triones / ELK-BLEDOM compatible controllers.
DEFAULT_POWER_ON_HEX: Final = "cc2333"
DEFAULT_POWER_OFF_HEX: Final = "cc2433"
DEFAULT_COLOR_TEMPLATE: Final = "56{r:02x}{g:02x}{b:02x}00f0aa"

DEFAULT_NET_BODY: Final = '{"on": {on}, "bri": {brightness}, "r": {r}, "g": {g}, "b": {b}, "hex": "{hex}"}'
DEFAULT_NET_PATH: Final = "/color"

DEFAULT_MQTT_QOS: Final = 0
DEFAULT_MQTT_RETAIN: Final = False
DEFAULT_MQTT_BODY: Final = (
    '{"state": "{state}", "brightness": {brightness}, "'
    '"color": {"r": {r}, "g": {g}, "b": {b}}'
)

# ---------------------------------------------------------------------------
# Effects
# ---------------------------------------------------------------------------
EFFECT_SOLID: Final = "固定"
EFFECT_BREATHE: Final = "呼吸"
EFFECT_RAINBOW: Final = "彩虹"
EFFECT_CHASE: Final = "追光"
EFFECT_CANDLE: Final = "烛光"
EFFECT_STROBE: Final = "频闪"
EFFECT_AURORA: Final = "极光"
EFFECT_AUDIO_PULSE: Final = "声控脉冲"
EFFECT_VU_METER: Final = "电平条"
EFFECT_SPARKLE: Final = "星火"
EFFECT_GRADIENT: Final = "渐变"

EFFECTS: Final = [
    EFFECT_SOLID,
    EFFECT_BREATHE,
    EFFECT_RAINBOW,
    EFFECT_CHASE,
    EFFECT_CANDLE,
    EFFECT_STROBE,
    EFFECT_AURORA,
    EFFECT_AUDIO_PULSE,
    EFFECT_VU_METER,
    EFFECT_SPARKLE,
    EFFECT_GRADIENT,
]
AUDIO_EFFECTS: Final = [EFFECT_AUDIO_PULSE, EFFECT_VU_METER]

# ---------------------------------------------------------------------------
# Scenes (palette presets)
# ---------------------------------------------------------------------------
DEFAULT_PALETTE: Final = ["#ffffff"]

SCENES: Final[dict[str, dict[str, object]]] = {
    "关闭": {"effect": EFFECT_SOLID, "palette": ["#000000"], "brightness": 0},
    "暖白": {"effect": EFFECT_SOLID, "palette": ["#ffd6a5"], "brightness": 220},
    "冷白": {"effect": EFFECT_SOLID, "palette": ["#e8f4ff"], "brightness": 230},
    "日落": {
        "effect": EFFECT_GRADIENT,
        "palette": ["#ff7a18", "#ff2d55", "#7a1fff"],
        "brightness": 190,
        "speed": 35,
    },
    "极光": {
        "effect": EFFECT_AURORA,
        "palette": ["#00ffa3", "#00d0ff", "#7b2dff"],
        "brightness": 180,
        "speed": 40,
    },
    "烛光": {"effect": EFFECT_CANDLE, "palette": ["#ff9d3c"], "brightness": 150, "speed": 30},
    "派对": {
        "effect": EFFECT_RAINBOW,
        "palette": ["#ff004d", "#00e5ff", "#ffe600", "#8a2be2"],
        "brightness": 255,
        "speed": 70,
    },
    "电影之夜": {
        "effect": EFFECT_GRADIENT,
        "palette": ["#1b2a6b", "#4b1e78", "#0b0f24"],
        "brightness": 90,
        "speed": 15,
    },
    "赛博朋克": {
        "effect": EFFECT_AURORA,
        "palette": ["#b026ff", "#00e5ff", "#ff007a"],
        "brightness": 210,
        "speed": 55,
    },
    "冰蓝": {"effect": EFFECT_BREATHE, "palette": ["#7fd8ff"], "brightness": 160, "speed": 25},
    "阅读": {"effect": EFFECT_SOLID, "palette": ["#ffefc2"], "brightness": 240},
}

# ---------------------------------------------------------------------------
# Runtime behaviour
# ---------------------------------------------------------------------------
DEFAULT_FPS: Final = 20
MIN_FRAME_INTERVAL: Final = 0.05
DEFAULT_SPEED: Final = 50
DEFAULT_SENSITIVITY: Final = 60
DEFAULT_SMOOTHING: Final = 40
DEFAULT_PIXELS: Final = 30

WLED_REQUEST_TIMEOUT: Final = 5
WLED_UDP_PORT: Final = 21324
WLED_UDP_TIMEOUT: Final = 2
PROBE_INTERVAL: Final = 60
ONLINE_GRACE: Final = 3

SIGNAL_UPDATE: Final = f"{DOMAIN}_update"
SERVICE_APPLY: Final = "apply"
SERVICE_EFFECT: Final = "effect"
SERVICE_SCENE: Final = "scene"
SERVICE_AUDIO_LEVEL: Final = "audio_level"
SERVICE_CUE: Final = "cue"
SERVICE_IDENTIFY: Final = "identify"
SERVICE_PING: Final = "ping"

ATTR_DEVICE: Final = "device_id"
ATTR_ON: Final = "on"
ATTR_BRIGHTNESS: Final = "brightness"
ATTR_RGB: Final = "rgb_color"
ATTR_HEX: Final = "hex_color"
ATTR_EFFECT: Final = "effect"
ATTR_SPEED: Final = "speed"
ATTR_PALETTE: Final = "palette"
ATTR_SCENE: Final = "scene"
ATTR_LEVEL: Final = "level"
ATTR_BANDS: Final = "bands"

BEEP_PATH: Final = "/rgb_sync/beep.wav"
