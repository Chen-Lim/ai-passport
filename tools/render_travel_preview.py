#!/usr/bin/env python3
"""Render the real application UI using a local LVGL 9.5.0 source checkout."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile

from validate_travel_json import load_snapshot, validate_snapshot

ROOT = Path(__file__).resolve().parents[1]


def snapshot_header(value: dict) -> str:
    """Translate a validated protocol payload to the actual C model for rendering."""
    errors = validate_snapshot(value)
    if errors:
        raise ValueError("; ".join(errors))
    kinds = {"train": "TRAVEL_TRAIN", "flight": "TRAVEL_FLIGHT"}
    statuses = {name: "TRAVEL_" + name.upper() for name in ("scheduled", "boarding", "delayed", "departed", "arrived", "cancelled", "unknown")}
    rows = []
    for trip in value["trips"]:
        fields = [f".{field} = {json.dumps(trip.get(field) or '', ensure_ascii=True)}"
                  for field in ("id", "service", "origin", "destination", "gate", "seat")]
        fields.extend([f".kind = {kinds[trip['kind']]}", f".status = {statuses[trip['status']]}"])
        for field in ("planned_departure", "estimated_departure", "actual_departure", "planned_arrival"):
            number = trip.get(field)
            fields.append(f".{field} = INT64_C({int(number) if number is not None else -1})")
        rows.append("    {" + ", ".join(fields) + "}")
    # Fixed-size arrays use a zero initializer for an explicitly empty snapshot.
    trip_rows = ",\n".join(rows) if rows else "    {0}"
    return ("static const travel_snapshot_t preview_snapshot = {\n"
            f".count = {len(rows)}, .revision = {int(value['revision'])}U,\n"
            f".updated_at = INT64_C({int(value['updated_at'])}), .expires_at = INT64_C({int(value['expires_at'])}),\n"
            f".source = TRAVEL_SOURCE_{value['source'].upper()}, .trips = {{\n{trip_rows}\n}}\n}};\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lvgl-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "build/travel-preview")
    parser.add_argument("--input", type=Path, help="render this validated JSON snapshot instead of built-in scenarios")
    parser.add_argument("--now", type=int, help="preview UTC time; defaults to the input updated_at")
    args = parser.parse_args()
    source = args.lvgl_source.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ai-passport-ui-", dir="/tmp") as directory:
        temp = Path(directory)
        input_definitions = ""
        if args.input:
            value = load_snapshot(args.input)
            (temp / "travel_input.h").write_text(snapshot_header(value), encoding="utf-8")
            now = args.now if args.now is not None else int(value["updated_at"])
            if now < 0 or now > 4102444799:
                raise ValueError("Preview time must be a supported UTC timestamp")
            input_definitions = f"target_compile_definitions(travel_preview PRIVATE TRAVEL_PREVIEW_INPUT PREVIEW_NOW={now}LL)\n"
        pins = (ROOT / "components/bsp/include/bsp_pins.h").read_text()
        constants = []
        for name in ("BSP_LCD_W", "BSP_LCD_H"):
            value = re.search(rf"#define\s+{name}\s+(\d+)", pins).group(1)
            constants.append(f"#define {name} {value}")
        (temp / "bsp_pins.h").write_text("\n".join(constants) + "\n")
        (temp / "lv_conf.h").write_text("""#pragma once
#define LV_CONF_H
#define LV_COLOR_DEPTH 16
#define LV_USE_STDLIB_MALLOC LV_STDLIB_CLIB
#define LV_FONT_MONTSERRAT_14 1
#define LV_FONT_MONTSERRAT_20 1
#define LV_FONT_MONTSERRAT_32 1
#define LV_USE_FONT_PLACEHOLDER 1
#define LV_BUILD_EXAMPLES 0
#define LV_USE_LOG 1
""")
        (temp / "CMakeLists.txt").write_text(f"""cmake_minimum_required(VERSION 3.16)
project(travel_preview C)
set(LV_CONF_PATH "{temp / 'lv_conf.h'}" CACHE STRING "" FORCE)
set(LV_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(LV_BUILD_DEMOS OFF CACHE BOOL "" FORCE)
add_subdirectory("{source}" lvgl-build)
add_executable(travel_preview
  "{ROOT / 'tests/travel_ui_preview.c'}"
  "{ROOT / 'main/travel_ui.c'}"
  "{ROOT / 'main/travel_state.c'}"
  "{ROOT / 'main/travel_demo.c'}"
  "{ROOT / 'assets/fonts/travel_font_18.c'}")
target_include_directories(travel_preview PRIVATE "{temp}" "{ROOT / 'main'}")
target_link_libraries(travel_preview PRIVATE lvgl)
{input_definitions}
""")
        subprocess.run(["cmake", "-S", str(temp), "-B", str(temp / "build"), "-G", "Ninja"], check=True)
        subprocess.run(["cmake", "--build", str(temp / "build"), "--target", "travel_preview", "--parallel", "4"], check=True)
        subprocess.run([str(temp / "build/travel_preview"), str(output)], check=True)


if __name__ == "__main__":
    main()
