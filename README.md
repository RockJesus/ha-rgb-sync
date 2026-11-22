# RGB Sync · 全屋 RGB 同步

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
![HA Version](https://img.shields.io/badge/Home%20Assistant-2025.1%2B-03A9F4)

> English summary: a Home Assistant hub that keeps every RGB controller in the house in sync over
> WLED (WiFi), generic HTTP/TCP/UDP controllers, Bluetooth LE, Matter lights and MQTT topics.
> One group light, per-device lights, a whole-house link switch, eleven software effects, scene
> presets, audio-reactive mode and an audible confirmation beep.

一个「中枢」把家里所有 RGB 灯控拉到同一状态：**单独控制每一盏，也能一键全屋同步**。
灯效由集成自己渲染，所以 WLED 灯带、杂牌网络灯控、蓝牙灯带看到的是同一套颜色和同一套动画。

## 支持的接入方式

| 协议 | 对接对象 | 控制通道 | 灯效 |
| --- | --- | --- | --- |
| **WLED（WiFi）** | WLED 0.13+ 固件 | HTTP `POST /json/state` 保存静态状态；UDP `21324` DRGB 实时帧 | 全帧动画，最高约 25 fps |
| **网络灯控** | 任意 HTTP / TCP / UDP 灯控（ESP8266、MagicHome、自研板子等） | 可配置 URL、方法、报文模板；TCP 长连接；UDP 数据报 | 报文模板渲染，HTTP 约 5-8 fps |
| **蓝牙 LE** | Triones / ELK-BLEDOM 兼容灯带，或自定义指令集 | HA `bluetooth` 的 BLE 连接，写入特征值 | 颜色帧，约 4 fps |
| **Matter** | 已通过 Matter 集成接入 HA 的灯泡 / 灯带 | 转发现有 `light` 实体：`light.turn_on/off` 下发颜色与亮度 | 颜色帧，约 4 fps |
| **MQTT** | 任意订阅同一主题的灯控 / 桥接程序（ESPHome、自研网关、Node-RED） | 向可配置主题发布报文，支持 QoS 0-2 与 retain | 颜色帧，约 7 fps |

> WLED 的灯珠数量会在配置时自动读取（`/json/info`），无需手工填写。

**Matter 说明**：Matter 的协议栈在 Home Assistant 内部，灯是以 `light` 实体出现的，所以这种接入方式是「选一个已有灯实体，让全屋同步引擎驱动它」。它不会重新配对设备，也不会绕过 Matter 控制器；在同步里得到的颜色/亮度会转发给该实体，动效以约 4 fps 推颜色帧。

**MQTT 说明**：默认报文为 `{"state": "{state}", "brightness": {brightness}, "color": {"r": {r}, "g": {g}, "b": {b}}}`，主题不能带 `+` / `#` 通配符。模板可用 `{state}`、`{on}`、`{brightness}`、`{brightness_pct}`、`{r}`、`{g}`、`{b}`、`{hex}`、`{effect}`、`{speed}`，按需改成 Zigbee2MQTT、Tasmota 或自研网关认识的格式。

```yaml
# Tasmota / Zigbee2MQTT 风格示例
topic: rgb_sync/desk
body: '{"state": "{state}", "brightness": {brightness_pct}, "color": {"r": {r}, "g": {g}, "b": {b}}}'
```

## 自动发现设备

不用再手抄 IP 和 MAC，集成会自己在蓝牙、Matter 和局域网里找灯：

| 来源 | 怎么找 | 能发现什么 |
| --- | --- | --- |
| **蓝牙 LE** | HA `bluetooth` 集成的广播缓存，匹配 `0000fff0-…` 服务或 Triones / ELK-BLEDOM / LEDBLE 之类的广播名 | 未配置的蓝牙灯带，自动带出 MAC 和广播名 |
| **Matter** | 读实体注册表里 `platform=matter` 的 `light` 实体 | 已配对但还没纳入全屋同步的 Matter 灯 |
| **mDNS** | 浏览 `_wled._tcp.local.` 约 3 秒 | 局域网里的 WLED 控制器，带出主机与端口 |

三个入口，按场景挑一个：

1. **手动扫一遍**：集成卡片 →「配置」→「自动发现设备」，扫描后列出所有未配置的灯，勾选保存即可，一次可以加多台。
2. **HA 的发现提示**：蓝牙或 mDNS 广播出现时，Home Assistant 会弹「发现新设备」，点进去确认一次就加入现有中枢；重复设备会被跳过。
3. **蓝牙自动加入**：中枢设置里的「自动加入新出现的蓝牙灯」默认开启。新灯带上电后会自动进设备清单并重载，实体立刻可用；关掉后只保留发现提示，不会自己改配置。

说明与边界：

- 只会添加**还没有配置过**的设备，按「蓝牙 MAC / Matter 实体 ID / 主机+端口」去重，重复扫描不会造成重复实体。
- MQTT 灯需要明确主题和报文格式，没有统一的广播约定，因此不参与自动发现，仍在配置表单里手填。
- 通用网络灯控（HTTP / TCP / UDP）同样没有统一广播协议，继续手填 IP。
- 自动加入只对蓝牙生效：mDNS 与 Matter 的结果会以发现提示或手动勾选的方式呈现，避免一次广播就悄悄改掉中枢配置。

## 功能

- **全屋总控**：`light.全屋灯光` 一个实体控制全部设备（开关 / 亮度 / RGB / 灯效）。
- **单独控制**：每台设备都有自己的灯实体，互不影响。
- **全屋同步开关**：打开后，任意一盏灯改颜色、亮度或灯效，其余灯立即跟随；关闭后各灯独立。**开关仍按灯独立**，避免「开一盏全屋亮」。
- **调色**：RGB 三通道 + 16 进制颜色，支持服务调用与自动化。
- **11 套软件灯效**：固定、呼吸、彩虹、追光、烛光、频闪、极光、声控脉冲、电平条、星火、渐变。
- **场景预设**：暖白、冷白、日落、极光、烛光、派对、电影之夜、赛博朋克、冰蓝、阅读。
- **声音反馈**：
  - **声音律动**：把麦克风 / ESPHome 传感器 / 浏览器的电平推进来，灯随音量起伏；
  - **操作提示音**：每次开灯、调色、换灯效时在指定媒体播放器上播一声短提示音。
- **自动发现**：蓝牙广播、Matter 实体和 mDNS 上的 WLED 会被扫出来，勾选即加入；蓝牙灯还可以上电自动加入。
- **诊断**：在线设备数、帧率、音量电平和每台设备的最后错误，全部是实体。

## 安装

1. **市场 / HACS**：添加自定义仓库 `https://github.com/RockJesus/ha-rgb-sync`，类型选「集成」，安装后重启 Home Assistant。
2. **手动**：把 `custom_components/rgb_sync` 整个目录放进 `/config/custom_components/`，重启。

重启后：**设置 → 设备与服务 → 添加集成 → 搜索「RGB Sync / 全屋 RGB 同步」**。

首次配置会让你挑接入方式添加灯具：WLED（填 IP）、网络灯控（选 HTTP/TCP/UDP 并填报文）、蓝牙（填 MAC）、Matter（选已有灯实体）、MQTT（填主题与报文），可混合添加后完成。后续增删设备走集成卡片上的「配置」，也可以直接让它「自动发现设备」。

## 实体一览

| 实体 | 作用 |
| --- | --- |
| `light.<中枢>_all_lights` | 全屋灯光总控 |
| `light.<设备名>` | 单灯控制（开关 / 亮度 / 颜色 / 灯效） |
| `switch.<中枢>_link` | 全屋同步：颜色、亮度、灯效是否互相跟随 |
| `switch.<中枢>_audio_reactive` | 声音律动开关 |
| `switch.<中枢>_cue` | 操作提示音开关 |
| `number.<中枢>_speed` | 默认灯效速度 1-100 |
| `number.<中枢>_sensitivity` | 声音灵敏度 0-100 |
| `number.<中枢>_smoothing` | 声音平滑度 0-95 |
| `select.<中枢>_scene` | 场景预设 |
| `sensor.<中枢>_online_devices` | 在线设备数（含每台设备状态） |
| `sensor.<中枢>_audio_level` | 当前音量电平 % |
| `sensor.<中枢>_frame_rate` | 灯效渲染帧率 |
| `button.<中枢>_identify` | 全部闪白 1.2 秒，用来找灯 |
| `button.<中枢>_ping` | 立刻重新探测在线状态 |
| `button.<中枢>_test_cue` | 播一次提示音 |

## 服务

| 服务 | 说明 |
| --- | --- |
| `rgb_sync.apply` | 设置开关 / 亮度 / RGB / 16 进制颜色 / 灯效 / 速度 / 配色；target 留空=全部 |
| `rgb_sync.effect` | 直接启动灯效，可带配色与速度 |
| `rgb_sync.scene` | 应用场景预设 |
| `rgb_sync.audio_level` | 推入 0-1 音量电平（可选 48 段频谱） |
| `rgb_sync.cue` | 播一次提示音 |
| `rgb_sync.identify` | 闪白定位（可指定单台） |
| `rgb_sync.ping` | 重新探测全部设备 |

```yaml
# 全屋切成日落渐变
service: rgb_sync.scene
data:
  scene: 日落

# 只让书房灯变青蓝并呼吸
service: rgb_sync.apply
target:
  entity_id: light.shufang
data:
  rgb_color: [0, 229, 255]
  brightness: 180
  effect: 呼吸
```

## 网络灯控的报文模板

`body` 支持这些占位符，**其他花括号保持原样**（所以可以直接写 JSON）：

| 占位符 | 含义 |
| --- | --- |
| `{on}` | 1 / 0 |
| `{state}` | ON / OFF |
| `{brightness}` | 0-255 |
| `{brightness_pct}` | 0-100 |
| `{r}` `{g}` `{b}` | 颜色通道 |
| `{hex}` | `#rrggbb` |
| `{effect}` `{speed}` | 灯效名 / 速度 |

```json
{"on": {on}, "bri": {brightness}, "color": "{hex}"}
```

TCP / UDP 报文支持 `\xNN` 转义，例如 `\x7e\x00\x05\x03\xff\x00\x00\x00\x00\x00\xef`。

## 声音律动怎么接

三种方式任选：

1. **ESPHome / 任意传感器**（推荐）：把 0-100% 或 0-255 的电平实体填进「音量来源」，打开「声音律动」即可；也可以用自动化调用服务：

   ```yaml
   trigger:
     - platform: state
       entity_id: sensor.living_room_mic_level
   action:
     - service: rgb_sync.audio_level
       data:
         level: "{{ states('sensor.living_room_mic_level') | float(0) / 100 }}"
   ```

2. **浏览器 / 卡片**：任意前端页面通过 WebSocket 推送，适合做麦克风频谱卡：

   ```js
   await hass.connection.sendMessagePromise({
     type: "rgb_sync/audio_level",
     level: 0.42,
     bands: [0.1, 0.3, 0.8],
   });
   ```

3. **媒体播放器音量**：把音量实体当电平源，灯会跟着播放器音量走。

提示音使用集成内置的 `beep.wav`（`/rgb_sync/beep.wav`），在「中枢设置」里选一个 `media_player` 即可。

## 蓝牙灯控说明

- `triones` 协议：开灯 `CC 23 33`、关灯 `CC 24 33`、颜色 `56 RR GG BB 00 F0 AA`，亮度通过按比例缩放 RGB 实现，不改写设备自带亮度字节。
- `generic` 协议：自己填服务 UUID、特征 UUID、颜色模板（`{r:02x}` 形式）、开关指令。模板里的空格 / 逗号 / `0x` 前缀都会被忽略。
- 蓝牙连接按需建立，断开后下次写入自动重连；设备不在附近时实体显示不可用，并在属性里给出原因。

## 已知边界

- 灯效由 HA 渲染并推流。WLED 走 UDP 实时帧时会进入 live 模式，停止灯效后会自动回到静态颜色。
- HTTP 灯控的帧率受请求开销限制（约 5-8 fps），需要高帧率动画请优先用 WLED 或 UDP/TCP。
- BLE 的写入间隔约 250 ms，适合呼吸 / 渐变 / 声控脉冲，不适合高频频闪。
- 集成重启后灯默认为关闭状态；颜色 / 灯效会在下一次控制时重新下发。

## 隐私

仓库内不含任何域名、IP、MAC、令牌或个人信息。所有设备地址只存在你的 Home Assistant 配置里。

## License

MIT
