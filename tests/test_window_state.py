#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tester för core/window_state.py – fönstret ska alltid synas på skärmen.

Körs utan Qt (ren beräkning).

    python -m unittest discover -s tests -v
    python tests/test_window_state.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.window_state import (  # noqa: E402
    MIN_HEIGHT,
    MIN_VISIBLE_H,
    MIN_VISIBLE_W,
    MIN_WIDTH,
    clamp_geometry,
)

PRIMARY = (0, 0, 1920, 1040)
SECONDARY = (1920, 0, 1280, 1024)


class ClampGeometryTests(unittest.TestCase):
    """clamp_geometry – placering inom skärmarnas synliga yta."""

    def test_geometry_inside_primary_is_kept(self) -> None:
        self.assertEqual(
            clamp_geometry(100, 80, 1200, 800, [PRIMARY]), (100, 80, 1200, 800)
        )

    def test_geometry_on_secondary_screen_is_kept(self) -> None:
        self.assertEqual(
            clamp_geometry(2000, 100, 1000, 700, [PRIMARY, SECONDARY]),
            (2000, 100, 1000, 700),
        )

    def test_window_on_removed_screen_is_centered(self) -> None:
        # Sparad på en skärm som inte längre finns (t.ex. 3000, 2000)
        x, y, w, h = clamp_geometry(3000, 2000, 1200, 800, [PRIMARY])
        self.assertEqual((w, h), (1200, 800))
        self.assertEqual(x, (1920 - 1200) // 2)
        self.assertEqual(y, (1040 - 800) // 2)

    def test_window_off_left_edge_is_moved_in(self) -> None:
        x, y, _, _ = clamp_geometry(-5000, -3000, 1200, 800, [PRIMARY])
        self.assertGreaterEqual(x, 0)
        self.assertGreaterEqual(y, 0)

    def test_small_visible_sliver_is_rejected(self) -> None:
        # Bara 40 px av fönstret syns → räknas som utanför
        x, _, _, _ = clamp_geometry(1920 - 40, 100, 1200, 800, [PRIMARY])
        self.assertLess(x + 1200, 1920 + 1)
        self.assertGreaterEqual(
            min(1920, x + 1200) - max(0, x), MIN_VISIBLE_W
        )

    def test_too_small_size_is_grown(self) -> None:
        _, _, w, h = clamp_geometry(10, 10, 100, 100, [PRIMARY])
        self.assertEqual((w, h), (MIN_WIDTH, MIN_HEIGHT))

    def test_bigger_than_screen_is_anchored(self) -> None:
        x, y, w, h = clamp_geometry(0, 0, 4000, 3000, [(0, 0, 800, 600)])
        self.assertEqual((x, y), (0, 0))
        self.assertEqual((w, h), (4000, 3000))
        # Minst det synliga minimumet ryms
        self.assertGreaterEqual(w, MIN_VISIBLE_W)
        self.assertGreaterEqual(h, MIN_VISIBLE_H)

    def test_without_screens_nothing_moves(self) -> None:
        self.assertEqual(clamp_geometry(50, 60, 900, 700, []), (50, 60, 900, 700))

    def test_negative_screen_origin(self) -> None:
        # Skärm placerad till vänster om huvudskärmen
        left_screen = (-1920, 0, 1920, 1040)
        self.assertEqual(
            clamp_geometry(-1500, 100, 1200, 800, [PRIMARY, left_screen]),
            (-1500, 100, 1200, 800),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
