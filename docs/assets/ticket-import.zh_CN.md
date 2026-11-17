简体中文 · [English](ticket-import.md)

# 票务导入协议

采用两个独立的单条记录 Schema：

- [机票导入](../../main/import/flight.schema.json)：依据[机票字段文档](https://thedafeige.feishu.cn/wiki/FZd6wOGRniIWytkDoh9cfy2gnmg)第 2 节，读取版本 1090。
- [火车票导入](../../main/import/train.schema.json)：依据[火车票字段文档](https://thedafeige.feishu.cn/wiki/Xr1Gwz6g7iDCIKk10w5cGDrTnVd)第 2 节，读取版本 1668。

保留原始 camelCase 列名。机票覆盖表格的全部 46 个字段，以及说明中提到的 6 个导出 ID
字段；火车票覆盖全部 38 个字段、75 个铁路运营商。两者的必填／空值规则、当地时间格式
和枚举不同，分开校验更明确。[显示快照](../../main/travel_snapshot.schema.json)继续作为
紧凑的 UI 协议；转换输出该协议，完整票务元数据另行保留。

## 必填与空值

机票必须提供 `flightNo`、`departureTime`、`arrivalTime`，并在每组代码中至少提供
一个非空值：

- `airlineIata` 或 `airlineIcao`；
- `departureIata` 或 `departureIcao`；
- `arrivalIata` 或 `arrivalIcao`。

未使用的另一项可省略、填 `null` 或空字符串。可选导出 ID 保留文档的匹配优先级，
不会取消文档明确的代码二选一要求。航司 IATA 代码两位、机场 IATA 三位、航司 ICAO
三位、机场 ICAO 四位。

火车票以下字段必须有非空值：

`departureStation`、`departureRegionCode`、`arrivalStation`、`arrivalRegionCode`、
`departureTime`、`departureTimeZone`、`arrivalTimeZone`、`seatType`。

黄色字段也必须存在，但允许 `null` 或 `""`：

`railwayOperator`、`trainNo`、`arrivalTime`、`carNo`、`seatNo`。

这支持历史车票的未知到达时间、不指定车次，以及无座／自由席等情况。国家／地区、
货币代码保留文档规定的两位／三位形式。导入阶段的文本不受显示字体和四字符限制。
车厢、座位和票号保留字符串，避免丢失前导零。导出 ID 和序号允许字符串或整数，
因为文档没有规定它们在 JSON 中的表示方式。

## 时间和数字处理

- 机票使用当地时间 `yyyy-MM-ddTHH:mm`。到达、实际到达采用到达机场时区；
  出发、实际出发和登机采用出发机场时区。
- 火车票使用当地时间 `yyyy-MM-dd HH:mm`，并使用明确给出的
  `departureTimeZone`／`arrivalTimeZone`。
- 检查日历日期和已知 IANA 时区。机票文档没有时区列，投影为显示快照时需要在独立
  context 文件中指定时区；不根据国家、航司或机场代码猜测。
- 转换 UTC 后检查先后顺序。夏令时跳过的当地时刻会被拒绝；重复出现的时刻需要在
  context 中明确指定 `fold` 为 0 或 1。
- 数字支持 JSON 数值或 CSV 数字字符串。本地校验策略要求价格、积分和里程非负，
  经度在 -180..180、纬度在 -90..90；整数积分拒绝小数。

Schema 记录文档默认值，普通 JSON Schema 校验不会自动填入。转换会在元数据中报告
实际采用的默认值。例如机票 `serviceStatus=normal`、`barcodeFormat=qr`、
`reimburseStatus=no`，火车票 `propulsionType=unknown`、`qrCodeFormat=qr`。
火车票报销状态接受 `yes` 或空值，机票还接受 `no`。保留原始枚举拼写与大小写，
包括 `dynamicUrl`、`eLoco`、`afterChangingStation` 和 `origRefunded`。

## 校验 JSON 或 CSV

```bash
python3 tools/validate_travel_json.py --kind flight tests/fixtures/travel/import-flight.json
python3 tools/validate_travel_json.py --kind train tests/fixtures/travel/import-train.json
python3 tools/validate_travel_json.py --kind train tickets.csv
```

每个 Schema 描述单条记录。CLI 还接受同类记录数组，或列名一致的 UTF-8 CSV（可含 BOM）。
拒绝重复表头／JSON 键、列数错误、未知字段和非法取值。导入文件最多 1 MiB、1000 条记录，
每条解码后的记录最多 64 KiB；这是本地工具的资源预算，不是外部文档规定的限制。

## 转换为当前界面

```bash
python3 tools/import_travel_json.py tests/fixtures/travel/import-flight.json \
  --kind flight --context tests/fixtures/travel/flight-context.json \
  --source demo --updated-at 1790049600 \
  --output build/imported-flight.json --metadata-output build/imported-flight-metadata.json

python3 tools/import_travel_json.py tests/fixtures/travel/import-train.json \
  --kind train --source demo --updated-at 1794873600 \
  --output build/imported-train.json

python3 tools/render_travel_preview.py --lvgl-source managed_components/lvgl__lvgl \
  --input build/imported-flight.json --output build/import-preview
```

转换默认采用 `source=live`、`revision=1`、导入接收时间作为 `updated_at`，有效期 300 秒。
这表示导入数据的新鲜度，不证明实时数据服务检查过运行状态。合并实时更新时，应显式
传入 `--revision`、`--updated-at`、`--expires-at`。超过四条导入记录，需要明确选择
从零开始的索引，例如 `--indexes 0,2,4`；转换不会悄悄丢弃其余数据。

| 导入字段 | 显示结果 |
| --- | --- |
| `flightNo`／`trainNo` | 航班／车次；未指定车次时显示 `--` |
| 机场 IATA／ICAO／车站名 | 路线标签 |
| `departureTime` | 按时区转换为 `planned_departure` |
| `arrivalTime` | `planned_arrival`；火车票未知到达时间转换为 `null` |
| `actualDepartureTime` | `actual_departure` |
| `departureGate`／`ticketGate` | 登机口／检票口；不把航站楼或候车室当作口号 |
| `seatNo`、火车票 `carNo` | 座位，保留车厢前导零 |
| 机票 `serviceStatus=cancelled` | `cancelled` |
| 其他票务记录 | 默认 `unknown`；可在 context 中提供明确的运行状态 |

`boardingTime` 不是预计出发时间，`actualArrivalTime` 不会覆盖计划到达时间。
实际承运航司／航班、经停、退改、乘客、费用、设备、二维码／条形码等字段保留在
原始输入和可选元数据输出中。退票和换开描述票务状态，不会把正常运行的车次／航班
变成取消。`returned`、`diverted` 会保留并发出提示，因为当前 UI 没有对应的专用状态。
转换不会请求条形码／动态二维码 URL。

## 显示 context 与元数据

[机票 context 示例](../../tests/fixtures/travel/flight-context.json)提供出发、到达地 IANA
时区。`records` 数组可按原始输入索引指定简短 UI 标签：

```json
{
  "departureTimeZone": "Asia/Shanghai",
  "arrivalTimeZone": "Asia/Shanghai",
  "records": [
    { "origin": "BJW", "destination": "HKW", "service": "G108" }
  ]
}
```

这些短标签是显示别名，不代表断言它们属于车站字典代码。context 可指定 `id`、
`origin`、`destination`、`service`、`gate`、`seat`、`status` 和每段机票的时区。
不能替换火车票文档已给出的时区，也不能把已取消的航班显示为有效状态。
每段记录的 `folds` 对象使用源时间字段名，例如
`{"departureTime":0,"arrivalTime":1}`，用于处理夏令时重复小时。

显示标签随后按当前字体、长度和车次／航班格式校验。长站名或不支持的字符需要明确的
短标签，或后续扩展字体／界面。设备仍统一显示转换后的 UTC+8 时间。

元数据保留源记录、UTC 时间、有效默认值和有序匹配候选：航司／机场 ID 优先于 ICAO，
ICAO 优先于 IATA；实际承运航司 ID 优先于 IATA；经停 ID 优先于代码；机型 ID 优先于
ICAO 再到机型名。当前没有执行字典查询，不能确认 ID／代码一致性或是否存在。
元数据可能包含乘客、票号或二维码信息，应保留在本地并避免提交；只有紧凑显示快照
用于设备。

火车票和机票分别校验；转换后的行程列表可以放入同一个显示快照，总数保持最多四段，
并使用一致的版本号、更新时间和过期时间。

设备的外部 JSON 接收入口仍未实现。这些工具在本地校验、转换和预览，不会通过 USB
传输，也不会向外部车票票 App 导入数据。
