<p align="right">
  <a href="README.zh_CN.md">简体中文</a> · <strong>English</strong>
</p>

# Assets

This directory stores reusable fonts, images, music, sound effects, and battery profiles, organized by asset type.

Keep each asset in the matching subdirectory and document its destination, naming, integration method, and source/license. Do not mix binary assets with Markdown documentation.

## Fonts

Store reusable font files and generated font sources in `fonts/`.

- Use descriptive names that include the family, weight, size, and format when relevant.
- Document the source, license, character range, conversion command, and expected destination.
- Check Flash and internal-RAM impact before adding a font; the ESP32-C3 has no PSRAM.
- Do not commit fonts whose license does not permit redistribution.

### Travel Pocket font

[`fonts/NotoSansSC-TravelSubset.ttf`](fonts/NotoSansSC-TravelSubset.ttf) is an
application subset of [Google Fonts Noto Sans SC](https://github.com/google/fonts/tree/main/ofl/notosanssc),
distributed under [SIL OFL 1.1](fonts/OFL.txt). The upstream variable font was
downloaded on 2026-11-17; original SHA-256:
`a3041811a78c361b1de50f953c805e0244951c21c5bd412f7232ef0d899af0da`.
fontTools 4.60.1 fixes weight at 500 and subsets its Unicode cmap to the printable ASCII and application
characters collected by `required_codepoints()` in `tools/generate_travel_font.py`.
The full upstream file is not retained. The subset is 41,196 bytes; adding a
character outside it requires obtaining the matching upstream font and rebuilding
the subset first.

[`fonts/travel_characters.txt`](fonts/travel_characters.txt) is the exact printable
inventory. [`fonts/travel_font_18.c`](fonts/travel_font_18.c) is the 18 px, 4 bpp,
uncompressed LVGL bitmap font, generated with lv_font_conv 1.5.3 and no kerning.
It is compiled by `main/CMakeLists.txt`; Chinese labels explicitly select it,
and runtime checks validate the font actually selected by each widget. Unknown
characters use an explicit unsupported-text message. ASCII service numbers use
Montserrat 32; clock values use Montserrat 20.

Regenerate using an installed, pinned converter:

```bash
python3 tools/generate_travel_font.py --converter /path/to/lv_font_conv
python3 tests/test_travel_font.py
```

To rebuild the TTF subset as well, install fontTools 4.60.1 in a local Python
environment and add `--source-font /path/to/original/NotoSansSC-Variable.ttf`
to the generator command. The source SHA-256 and tool version are verified.

The script fixes `--size 18 --bpp 4 --format lvgl --no-compress --no-kerning
--lv-font-name travel_font_18 --lv-include lvgl.h`, and passes the recorded
inventory via `--symbols`. Its tests check this font's actual cmap, a missing-glyph
negative case, and bitmap bounds/nonempty glyphs. Device rendering remains a
separate acceptance check.

## Images

Store reusable source images and generated display assets in `images/`.

| File | Dimensions and format | Use and source |
| --- | --- | --- |
| [`images/home.jpg`](images/home.jpg) | 3840 × 2160, JPEG | Product hero image embedded in both project README files to foreground AI Passport and its open, maker-oriented identity. |
| [`images/readme-hardware-specs.png`](images/readme-hardware-specs.png) | 2172 × 724, PNG RGBA | Optional technical infographic retained as a reference asset; it is no longer used as the homepage hero. Generated for this repository with the built-in image generation tool on 2026-09-17; the six labels and values were checked against the documented hardware contract. |
| [`images/logo-wordmark.png`](images/logo-wordmark.png) | 1648 × 336, PNG RGBA | Transparent black wordmark extracted from the repository's original `images/logo.png`; embedded in both project README files for light backgrounds. |
| [`images/logo-wordmark-dark.png`](images/logo-wordmark-dark.png) | 1648 × 336, PNG RGBA | White version of the extracted wordmark, used by the README `<picture>` element when GitHub is in dark mode. |

- Use descriptive names and document dimensions, pixel format, conversion steps, and destination.
- Prefer formats suitable for the 240 × 320 RGB565 display and account for Flash and internal RAM.
- Preserve editable sources where licensing permits, and record the source and license.
- Never commit device QR secrets, credentials, or personal data in images.

## Music and sound effects

Store reusable music and sound-effect sources in `music/`.

- Document the source, license, sample rate, bit depth, channels, conversion command, and destination.
- Prefer 16 kHz, 16-bit mono PCM when it matches the current BSP audio path.
- Check Flash and internal-RAM cost before embedding audio; stream or chunk long recordings.
- Do not commit media without redistribution permission.

## Battery profiles

[`battery/wanli-500mah-profile2-xil40x-20261020.txt`](battery/wanli-500mah-profile2-xil40x-20261020.txt)
contains the supplied CW2017 profile for the Wanli New Energy 500 mAh cell
(profile2, XIL40X, 2026-10-20). It is an unchanged copy of the project-supplied
file, retained at the maintainer's request for this firmware update. Its
original filename is recorded in the paired Chinese document. No separate
license was included in the supplied file.

The format is 80 lines of two hexadecimal digits, one byte per line in register
order. The BSP embeds those bytes in `components/bsp/src/bsp_battery.c`; the
host gate checks the source file and initializer for an exact match. Text-file
SHA-256: `7ea96eba4634f4495a37c25ffacd54c1deaa0693b162c892d671a2ba68460919`.
Decoded 80-byte SHA-256:
`fa7365671093ef449c5bdcfb4adb279e3d275f888109f50b6b2f21e9b96220d5`.
This is a fuel-gauge profile, not a charging configuration or a generic profile
for every 500 mAh cell; see the [hardware guide](../docs/hardware-design/AI_HARDWARE_DEVELOPMENT_GUIDE.md#9-cw2017-fuel-gauge).
