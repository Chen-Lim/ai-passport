#!/usr/bin/env python3
"""Positive and negative payload tests for the public display contract."""

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from validate_travel_json import SCHEMA, load_snapshot, validate_snapshot  # noqa: E402
from check_glyphs import font_codepoints  # noqa: E402
from render_travel_preview import snapshot_header  # noqa: E402


class TravelJsonTest(unittest.TestCase):
    def setUp(self):
        self.value = load_snapshot(ROOT / "tests/fixtures/travel/snapshot.json")

    def test_samples_and_optional_fields(self):
        self.assertEqual(validate_snapshot(self.value), [])
        self.assertEqual(validate_snapshot(load_snapshot(ROOT / "tests/fixtures/travel/empty.json")), [])
        for trip in self.value["trips"]:
            for field in ("gate", "seat", "estimated_departure", "actual_departure", "planned_arrival"):
                trip.pop(field)
        self.assertEqual(validate_snapshot(self.value), [])

    def test_wrong_types_unknown_fields_and_milliseconds(self):
        for field, replacement in (("revision", True), ("revision", 0), ("revision", 1.5), ("updated_at", 1794873600000), ("updated_at", 4102444800.0), ("timezone", "UTC"), ("source", "unknown")):
            value = copy.deepcopy(self.value)
            value[field] = replacement
            self.assertTrue(validate_snapshot(value), field)
        self.value["count"] = 2
        self.assertTrue(validate_snapshot(self.value))

    def test_render_adapter_maps_nulls_enums_and_empty_lists(self):
        text = snapshot_header(self.value)
        self.assertIn(".source = TRAVEL_SOURCE_DEMO", text)
        self.assertIn(".status = TRAVEL_DELAYED", text)
        self.assertIn(".actual_departure = INT64_C(-1)", text)
        self.assertIn('.gate = ""', text)
        empty = load_snapshot(ROOT / "tests/fixtures/travel/empty.json")
        self.assertIn(".count = 0", snapshot_header(empty))

    def test_text_and_service_limits(self):
        for field, replacement in (("origin", "上海虹桥机场"), ("origin", "龘"), ("gate", "ABCDEFGH"), ("seat", "08车 06AB"), ("service", "G123\n"), ("service", "WWWWWWW")):
            value = copy.deepcopy(self.value)
            value["trips"][0][field] = replacement
            self.assertTrue(validate_snapshot(value), field)
        for service in ("12345", "G12345"):
            self.value["trips"][0]["service"] = service
            self.assertEqual(validate_snapshot(self.value), [])
        self.value["trips"][1]["service"] = "WW9999W"
        self.assertEqual(validate_snapshot(self.value), [])

    def test_status_limits_and_null(self):
        for status in SCHEMA["$defs"]["trip"]["properties"]["status"]["enum"]:
            self.value["trips"][0]["status"] = status
            self.assertEqual(validate_snapshot(self.value), [])
        self.value["trips"][0]["status"] = "on_time"
        self.assertTrue(validate_snapshot(self.value))

    def test_semantic_and_update_ordering(self):
        value = copy.deepcopy(self.value)
        value["trips"][1]["id"] = value["trips"][0]["id"]
        self.assertTrue(validate_snapshot(value))
        value = copy.deepcopy(self.value)
        value["expires_at"] = value["updated_at"]
        self.assertTrue(validate_snapshot(value))
        value = copy.deepcopy(self.value)
        value["trips"][0]["planned_arrival"] = 0
        self.assertTrue(validate_snapshot(value))
        value = copy.deepcopy(self.value)
        value["revision"] += 1
        self.assertEqual(validate_snapshot(value, self.value), [])
        self.assertTrue(validate_snapshot(self.value, self.value))
        value["updated_at"] -= 1
        self.assertTrue(validate_snapshot(value, self.value))
        value["updated_at"] += 1
        value["source"] = "live"
        self.assertTrue(validate_snapshot(value, self.value))

    def test_maximum_trips(self):
        self.value["trips"] *= 3
        self.assertTrue(validate_snapshot(self.value))

    def test_schema_name_alphabet_matches_the_actual_font(self):
        font = ROOT / "assets/fonts/travel_font_18.c"
        points = font_codepoints(font.read_text(), str(font))
        pattern = SCHEMA["$defs"]["display_name"]["pattern"]
        import re
        accepted = {ord(c) for c in pattern if ord(c) > 127}
        self.assertEqual(accepted, {cp for cp in points if cp > 127})
        self.assertTrue(re.fullmatch(pattern, "上海虹桥"))
        self.assertFalse(re.fullmatch(pattern, "重庆"))

    def test_message_size_duplicate_keys_and_invalid_numbers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "payload.json"
            for bad in (b'{"revision":1,"revision":2}', b'{"value":NaN}', b' ' * 4097, b'\xff'):
                path.write_bytes(bad)
                with self.assertRaises((ValueError, UnicodeError)):
                    load_snapshot(path)


if __name__ == "__main__":
    unittest.main()
