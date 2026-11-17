#!/usr/bin/env python3
"""Regenerate the application font with a pinned lv_font_conv 1.5.3 executable."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import hashlib

from check_glyphs import scan_source

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ("main/travel_ui.c", "main/travel_demo.c", "main/travel_app.c")


def required_codepoints() -> set[int]:
    points = set(range(0x20, 0x7f))
    for source in SOURCES:
        for literal in scan_source((ROOT / source).read_text(encoding="utf-8")):
            points.update(point for point in literal.codepoints if point >= 0x20)
    return points


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--converter", default="lv_font_conv")
    parser.add_argument("--source-font", type=Path, help="rebuild the TTF subset from the original upstream font")
    args = parser.parse_args()
    version = subprocess.check_output([args.converter, "--version"], text=True).strip()
    if version != "1.5.3":
        raise SystemExit(f"Expected lv_font_conv 1.5.3, got {version}")
    symbols = "".join(chr(point) for point in sorted(required_codepoints()))
    destination = ROOT / "assets/fonts"
    if args.source_font:
        from fontTools import subset, version as fonttools_version
        from fontTools.varLib.instancer import instantiateVariableFont
        if fonttools_version != "4.60.1":
            raise SystemExit("Subsetting requires fontTools 4.60.1")
        if hashlib.sha256(args.source_font.read_bytes()).hexdigest() != "a3041811a78c361b1de50f953c805e0244951c21c5bd412f7232ef0d899af0da":
            raise SystemExit("Source font does not match the recorded upstream SHA-256")
        options = subset.Options()
        font = subset.load_font(str(args.source_font), options)
        # The upstream variable font defaults to Thin; use a readable fixed weight.
        instantiateVariableFont(font, {"wght": 500}, inplace=True)
        worker = subset.Subsetter(options=options)
        worker.populate(unicodes=required_codepoints())
        worker.subset(font)
        subset.save_font(font, str(destination / "NotoSansSC-TravelSubset.ttf"), options)
    (destination / "travel_characters.txt").write_text(symbols + "\n", encoding="utf-8")
    subprocess.run([
        args.converter, "--font", str(destination / "NotoSansSC-TravelSubset.ttf"),
        "--symbols", symbols, "--size", "18", "--bpp", "4", "--format", "lvgl",
        "--no-compress", "--no-kerning", "--lv-font-name", "travel_font_18",
        "--lv-include", "lvgl.h", "--output", str(destination / "travel_font_18.c"),
    ], check=True)
    # Converter paths/argv are local details; keep the generated header reproducible.
    output = destination / "travel_font_18.c"
    text = output.read_text(encoding="utf-8")
    lines = text.splitlines()
    lines = [line for line in lines if not line.startswith(" * Opts:")]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Generated {output.relative_to(ROOT)} ({len(symbols)} printable codepoints)")


if __name__ == "__main__":
    main()
