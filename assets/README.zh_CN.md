<p align="right">
  <strong>简体中文</strong> · <a href="README.md">English</a>
</p>

# 资源目录（Assets）

本目录集中存放可复用的资源（字库、图片、音乐、电池参数等），按资源类型分子目录管理。每个资源放在其类型对应的子目录，并记录放置路径、命名方式、集成方式与来源/许可。二进制资源（字体、图片、音频）不属于纯 markdown 文档，请勿与文档混放。涉及版权/授权的资源需注明来源与许可。

## 字库（fonts）

可复用的字库文件与生成的字库源码放在 `fonts/`。

- 命名要能反映字族、字重、字级与格式。
- 记录来源、许可、字符范围、转换命令与目标放置路径。
- 添加字库前评估 Flash 与内部 RAM 影响；ESP32-C3 无 PSRAM。
- 不提交许可不允许分发的字库。

### 出行口袋字库

[`fonts/NotoSansSC-TravelSubset.ttf`](fonts/NotoSansSC-TravelSubset.ttf) 是
[Google Fonts Noto Sans SC](https://github.com/google/fonts/tree/main/ofl/notosanssc)
的应用子集，遵循 [SIL OFL 1.1](fonts/OFL.txt)。上游可变字体下载日期为
2026-11-17，原始文件 SHA-256：
`a3041811a78c361b1de50f953c805e0244951c21c5bd412f7232ef0d899af0da`。
使用 fontTools 4.60.1 固定字重为 500，根据 `tools/generate_travel_font.py` 的
`required_codepoints()` 收集的可打印 ASCII 和应用字符裁剪 Unicode cmap。
不保留完整上游文件。子集为 41,196 字节；添加子集外的字符时，需要先获取
匹配的上游字体并重建源字体子集。

[`fonts/travel_characters.txt`](fonts/travel_characters.txt) 保存准确的可打印字符清单。
[`fonts/travel_font_18.c`](fonts/travel_font_18.c) 是由 lv_font_conv 1.5.3 生成的
18 px、4 bpp、无压缩、无字偶距 LVGL 位图字库，由 `main/CMakeLists.txt` 编译。
中文控件显式选择该字库，运行时检查控件实际选中的字体；未知字符显示明确的
“文字不支持”提示。ASCII 车次／航班号使用 Montserrat 32，时间使用 Montserrat 20。

使用已安装的固定版本转换器重新生成：

```bash
python3 tools/generate_travel_font.py --converter /path/to/lv_font_conv
python3 tests/test_travel_font.py
```

如需同时重建 TTF 子集，在本地 Python 环境安装 fontTools 4.60.1，并向生成命令
增加 `--source-font /path/to/original/NotoSansSC-Variable.ttf`。
脚本会验证源字体 SHA-256 和工具版本。

脚本固定使用 `--size 18 --bpp 4 --format lvgl --no-compress --no-kerning
--lv-font-name travel_font_18 --lv-include lvgl.h`，通过 `--symbols` 传入记录的字符清单。
测试检查该字库实际的 cmap、缺字反例、位图边界及非空字形。真机渲染需要单独验收。

## 图片（images）

可复用的源图与生成的显示资产放在 `images/`。

| 文件 | 尺寸与格式 | 用途与来源 |
| --- | --- | --- |
| [`images/home.jpg`](images/home.jpg) | 3840 × 2160，JPEG | 嵌入中英文项目 README 的产品主图，突出 AI Passport 产品形象与开放、人人可创作的理念。 |
| [`images/readme-hardware-specs.png`](images/readme-hardware-specs.png) | 2172 × 724，PNG RGBA | 保留为可选技术参考图，不再用于首页主视觉。于 2026-09-17 使用内置图像生成工具为本仓库生成；已根据文档中的硬件能力契约核对图中的六项标签与参数。 |
| [`images/logo-wordmark.png`](images/logo-wordmark.png) | 1648 × 336，PNG RGBA | 从仓库原始 `images/logo.png` 中精确裁切并去除背景的黑色字标；用于中英文项目 README 的浅色主题。 |
| [`images/logo-wordmark-dark.png`](images/logo-wordmark-dark.png) | 1648 × 336，PNG RGBA | 提取字标的白色版本；README 使用 `<picture>` 在 GitHub 深色主题下显示。 |

- 使用描述性命名，并记录尺寸、像素格式、转换步骤与目标路径。
- 优先采用适合 240 × 320 RGB565 显示的格式，并纳入 Flash 与内部 RAM 考量。
- 许可允许时保留可编辑源文件，并记录来源与许可。
- 图片中不得包含设备二维码秘密、凭证或个人数据。

## 音乐与音效（music）

可复用的音乐与音效源码放在 `music/`。

- 记录来源、许可、采样率、位深、声道、转换命令与目标路径。
- 与当前 BSP 音频路径匹配时优先采用 16 kHz、16 位单声道 PCM。
- 嵌入音频前评估 Flash 与内部 RAM 成本；长录音应流式或分块。
- 无再分发许可不提交媒体文件。

## 电池参数（battery）

[`battery/wanli-500mah-profile2-xil40x-20261020.txt`](battery/wanli-500mah-profile2-xil40x-20261020.txt)
保存万锂新能源 500 mAh 电芯的 CW2017 参数（profile2、XIL40X、2026-10-20）。
该文件是项目提供的 `喜梨_智能工卡_万锂新能源500mAh_profile2_XIL40X_20261020.txt`
的原样副本，按维护者要求保留用于本次固件更新；原文件没有附带单独的许可说明。

格式为 80 行两位十六进制数字，每行一个字节，按寄存器顺序排列。
BSP 在 `components/bsp/src/bsp_battery.c` 中嵌入这 80 字节，主机检查会验证
源文件及数组内容完全一致。文本文件 SHA-256：
`7ea96eba4634f4495a37c25ffacd54c1deaa0693b162c892d671a2ba68460919`。
解码后 80 字节 SHA-256：
`fa7365671093ef449c5bdcfb4adb279e3d275f888109f50b6b2f21e9b96220d5`。
这是电量计参数，不是充电配置，也不能通用于所有 500 mAh 电芯；详见
[硬件指南](../docs/hardware-design/AI_HARDWARE_DEVELOPMENT_GUIDE.zh_CN.md#9-cw2017-电池计)。
