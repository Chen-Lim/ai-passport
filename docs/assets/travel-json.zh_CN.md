简体中文 · [English](travel-json.md)

# 出行口袋 JSON 协议

权威 [JSON Schema](../../main/travel_snapshot.schema.json) 使用 Draft 2020-12，
协议版本为 1。它描述当前票卡界面使用的完整行程快照，一次最多四段火车或飞机行程。
[示例快照](../../tests/fixtures/travel/snapshot.json) 和
[空行程快照](../../tests/fixtures/travel/empty.json) 均为模拟测试数据。

源票务列使用独立的[机票／火车票导入协议](ticket-import.zh_CN.md)。
导入 Schema 保留完整票务记录，本 Schema 约束用于 UI 的紧凑投影。

## 输入与显示映射

| 字段 | 必填 | 含义和显示位置 |
| --- | --- | --- |
| `schema_version` | 是 | 固定为 `1` |
| `timezone` | 是 | 固定为 `Asia/Shanghai`；界面统一显示 UTC+8 |
| `source` | 是 | `demo` 显示模拟数据提示，`live` 显示数据来源标签 |
| `revision` | 是 | 1..4294967295 的整数，同一来源的数据流中严格递增 |
| `updated_at` | 是 | 数据源更新快照的 UTC Unix 秒级时间戳，显示为更新时间 |
| `expires_at` | 是 | 快照过期的 UTC 秒级时间戳，必须大于 `updated_at` |
| `trips` | 是 | 完整替换列表，0..4 段；`[]` 清空行程 |
| `trips[].id` | 是 | 唯一且稳定的 ASCII ID，最多 23 个字符；身份需要包含日期和路线 |
| `kind` | 是 | `train` 或 `flight`，决定交通类型和检票口／登机口标签 |
| `service` | 是 | 大字号车次／航班号，格式按交通类型区分，见 Schema |
| `origin`, `destination` | 是 | 简短显示名，每个 1..4 个受支持字符 |
| `status` | 是 | 固定状态枚举，映射见下表 |
| `planned_departure` | 是 | UTC 秒级时间戳，用于日期和计划出发时间 |
| `estimated_departure` | 否 | UTC 秒或 `null`；已知时首页优先显示预计出发时间 |
| `actual_departure` | 否 | UTC 秒或 `null`，显示在详情页 |
| `planned_arrival` | 否 | UTC 秒或 `null`，显示在详情页；不能早于计划出发时间 |
| `gate` | 否 | 1..7 个 ASCII 字母、数字或连字符，或 `null` |
| `seat` | 否 | 1..7 个 Schema 座位字符集中的字符，或 `null` |

可选字段省略时与 `null` 含义相同。不接受空字符串：未知的检票口／登机口或座位用
`null`。模型适配器把未知时间转换为 `TRAVEL_UNKNOWN_TIME`（`-1`），把未知口号和座位
转换为空 C 字符串。JSON 时间字段不使用 `-1`。支持 0..4102444799 的秒级时间戳，
拒绝毫秒时间戳和时间字符串。

状态枚举与现有中文标签的映射：

| 枚举 | 显示 |
| --- | --- |
| `scheduled` | 按计划 |
| `boarding` | 正在登乘 |
| `delayed` | 已延误 |
| `departed` | 已出发 |
| `arrived` | 已到达 |
| `cancelled` | 已取消 |
| `unknown` | 状态未知 |

状态由数据源明确提供。出发时间字段或当前时间经过计划时间都不会自行生成“已出发”
状态。取消、已出发、已到达、未知和过期行程不显示有效的出发倒计时。

## 字体与布局兼容性

版本 1 明确受当前字体和 192 像素标签宽度限制。火车车次允许最多两个大写字母加
1..5 位数字、三个字母加 1..4 位数字，或 6..7 位纯数字；`--` 表示未指定车次。
航班号允许两位大写航司代码、1..4 位数字及一个可选大写后缀，或三个 ICAO 字母加
1..4 位数字。任意长的航空公司名称不能作为航班号。

地点名只接受 ASCII 字母／数字和 `travel_font_18` 中已打包的中文字符。
Schema 包含准确的字符集。它支持当前示例地点，不支持任意中文城市或机场名称。
遇到不支持的地点，请提供简短 ASCII 地点代码，或扩充字体并经过兼容性检查更新协议。
每个地点最多四个字符，保证两端名称和路线分隔符能一起显示；口号和座位长度也为
现有标题预留了空间。

## 校验与更新

```bash
python3 tools/validate_travel_json.py your-snapshot.json
python3 tools/validate_travel_json.py next.json --previous previous.json
```

仓库校验器只依赖 Python 标准库，处理本 Schema 使用的关键字。
其他调用方可使用支持 Draft 2020-12 的校验器。标准 JSON Schema 本身不能比较两个
字段，也不能只针对对象数组里的 `id` 判断唯一性，因此还需执行以下语义校验：

- `expires_at > updated_at`，每段行程的 ID 唯一。
- 已知的计划到达时间不能早于计划出发时间。
- 相对上次接受的快照，版本号严格递增、更新时间不倒退；切换 `source` 时需要
  明确重置数据流，不能默默混合模拟数据和真实数据。
- 原始 JSON 最多 4096 UTF-8 字节，包括空白；拒绝重复对象键、控制字符、非法 UTF-8
  和非 JSON 数字。

不发送局部补丁。只包含一段行程的快照会把完整列表替换为该段行程。
过期快照仍可通过结构校验：当 `now >= expires_at`，界面保留缓存票卡，标注过期并
停止倒计时。消息校验失败时必须保留上次已接受的快照。

设备时钟是否有效、连接状态、选中项、详情页状态和电量读数属于本地状态，不是 JSON
字段。不能把数据源更新时间当作可信的设备时间同步结果。

## 接入设备前先渲染 JSON

依赖准备好后，可使用真实 LVGL 界面进行主机预览：

```bash
python3 tools/render_travel_preview.py \
  --lvgl-source managed_components/lvgl__lvgl \
  --input tests/fixtures/travel/snapshot.json \
  --output build/json-preview
```

工具先校验 JSON，再转换成实际的 `travel_snapshot_t`，为每段行程渲染首页和详情页，
检查控件实际字体和文字边界，并输出 PPM 图片。预览时间默认取 `updated_at`，
可以用 `--now <UTC-seconds>` 检查过期或计划时间已过的显示行为。
这只是合成的预览时钟，不是设备时间同步机制。

## 当前设备接入边界

当前已刷入的固件仍加载内置模拟场景，没有 USB JSON 指令、BLE JSON 服务或网络 API
接收入口。制定协议和提供原生 JSON 渲染工具不会让该固件自动接受外部数据。
后续接收模块需要先校验并转换快照，独立设置网络和时钟状态，调用
`travel_state_apply()`，然后在 `bsp_lvgl_lock()` 保护下更新界面。
USB／BLE／Wi-Fi 传输方式的选择与 Schema 分开。
