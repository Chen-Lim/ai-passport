简体中文 · [English](README.en.md)

# eTicket

面向 FoloToy AI Passport 的中文火车／飞机行程卡片应用。

**当前版本是离线交互原型，所有行程均为内置静态或模拟数据，不提供真实铁路或航班状态。**
当前固件内置 2026-11-18 上海虹桥至杭州东的示例车次（G7687），模拟时钟随设备运行时间推进；
示例车次、检票口和座位不能用于出行。

## 显示与操作

- 首页：车次／航班号、路线、状态、计划或预计出发时间、检票口／登机口和座位。
- 详情：计划、预计、实际出发时间、计划到达时间和座位；所有时间按 UTC+8 显示。
- 上／下短按：切换行程；确定短按：打开或关闭详情。
- 详情页长按确定：返回首页。首页长按确定：切换静态示例与空行程场景。
- 双击按一次短按处理；不使用同时按键组合。
- 无操作 30 秒后调暗，60 秒后熄屏；熄屏后的首次按键只唤醒，不执行页面动作。

缺失字段显示“暂无信息”。空行程可通过首页长按确定切换回示例行程。电量不可用时显示 `--%`。

## 实现边界

固件入口为 [`main/travel_app.c`](main/travel_app.c)，使用独立票卡界面。
基线测试文件保留为参考和回归测试，未编入本应用，也没有从应用导航进入测试菜单的路径。
硬件通过 `components/bsp` 访问；没有修改 BSP、引脚或默认分区表。
无线功能关闭，行程和场景只保存在 RAM，重启恢复初始模拟场景。

中文使用 18 px Noto Sans SC 应用子集，覆盖所有固定界面和示例行程文字。运行时检查
实际控件字体；超出子集的文字显示“文字不支持”，不承诺任意中文地点名。来源、许可
和重新生成方法见 [`assets/README.md`](assets/README.md)。

可用 [`tools/render_travel_preview.py`](tools/render_travel_preview.py) 配合本地 LVGL 9.5.0
源码进行主机渲染检查（需要 CMake 和 Ninja）。它验证所有模拟场景的控件字体和文字边界，
并输出 PPM 预览；这不替代真机屏幕检查。

真实数据阶段需要确定服务覆盖、字段、更新延迟、额度、认证和设备联网方式，再实现
配网、时间同步、HTTPS、限长 JSON、重试、凭据管理和数据缓存。当前没有实现这些能力。
状态模型已将来源、更新时间、过期时间和计划／预计／实际时间分开。

原始票务数据采用独立的[机票导入 Schema](main/import/flight.schema.json)和
[火车票导入 Schema](main/import/train.schema.json)，使用文档中的原始列名和必填规则；
可校验 JSON／CSV 并转换，见[票务导入说明](docs/assets/ticket-import.zh_CN.md)。
用于界面的[显示快照 Schema](main/travel_snapshot.schema.json)、字体／长度限制和渲染方法
见 [JSON 接入说明](docs/assets/travel-json.zh_CN.md)。当前设备固件仍没有外部 JSON 接收入口。

## 构建和验收

激活 ESP-IDF 5.5.3，执行：

```bash
./tools/validate.sh --static
./tools/validate.sh
```

完整门禁生成 `build/FoloToy-AI-Passport-full.bin`，可从 `0x0` 刷写，并保留匹配的 ELF/MAP。
合并镜像可能重置 NVS 中已有数据；烧录前按 [固件布局政策](docs/development/engineering/firmware-layout.md)
确认数据影响。未经用户确认不烧录，不需要把读取旧固件作为前提。

真机验收：检查两类票卡、中文和混合字符、六种场景、详情与返回、反复切换、调暗／熄屏／唤醒，
以及启动日志、最小可用堆和实际功耗。自动构建和字体覆盖检查不能证明屏幕渲染或续航。

开发规范见 [`AGENTS.md`](AGENTS.md)。
