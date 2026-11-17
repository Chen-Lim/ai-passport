#!/usr/bin/env python3
"""Check the exact application font, its coverage and uncompressed bitmap bounds."""

from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from check_glyphs import font_codepoints, parse_ints  # noqa: E402
from generate_travel_font import required_codepoints  # noqa: E402


class TravelFontTest(unittest.TestCase):
    def test_exact_font_covers_all_application_text(self):
        path = ROOT / "assets/fonts/travel_font_18.c"
        actual = font_codepoints(path.read_text(), str(path))
        self.assertIsNotNone(actual)
        self.assertFalse(required_codepoints() - actual)
        self.assertNotIn(0x9f98, actual)  # runtime negative probe
        inventory = set(map(ord, (ROOT / "assets/fonts/travel_characters.txt").read_text().rstrip("\n")))
        self.assertEqual(inventory, required_codepoints())

    def test_glyph_bitmaps_are_nonempty_and_within_bounds(self):
        text = (ROOT / "assets/fonts/travel_font_18.c").read_text()
        bitmap = re.search(r"glyph_bitmap\[\]\s*=\s*\{(.*?)\};", text, re.S).group(1)
        bitmap = re.sub(r"/\*.*?\*/", "", bitmap, flags=re.S)
        data = bytes(parse_ints(bitmap))
        glyphs = re.findall(r"\{\.bitmap_index = (\d+), \.adv_w = (\d+), \.box_w = (\d+), \.box_h = (\d+),", text)
        self.assertGreater(len(glyphs), 100)
        for index, advance, width, height in glyphs:
            index, width, height = int(index), int(width), int(height)
            size = (width * height + 1) // 2
            self.assertLessEqual(index + size, len(data))
            if width and height:
                self.assertTrue(any(data[index:index + size]))
        self.assertIn(".bpp = 4", text)
        self.assertIn(".bitmap_format = 0", text)


if __name__ == "__main__":
    unittest.main()
