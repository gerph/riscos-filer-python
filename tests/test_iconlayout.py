#!/usr/bin/env python3
"""
Tests for the layout of the icons of an explorer window. No toolkit is needed.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import iconlayout


class LayoutTests(unittest.TestCase):

    def layout(self, count, width, top=0):
        layout = iconlayout.IconLayout(cell_width=100, cell_height=50, spacing=10, margin=8)
        height = layout.layout(count, width, top)
        return (layout, height)

    def test_cells_fill_a_row_then_wrap(self):
        (layout, height) = self.layout(5, 350)
        # (350 - 16 + 10) // 110 = 3 across
        self.assertEqual(layout.columns, 3)
        self.assertEqual(layout.rects[0], (8, 8, 100, 50))
        self.assertEqual(layout.rects[2], (228, 8, 100, 50))
        self.assertEqual(layout.rects[3], (8, 68, 100, 50))
        self.assertEqual(height, 8 + 50 + 10 + 50 + 8)

    def test_at_least_one_cell_is_across_in_a_narrow_panel(self):
        (layout, height) = self.layout(3, 20)
        self.assertEqual(layout.columns, 1)
        self.assertEqual(height, 8 + 3 * 50 + 2 * 10 + 8)

    def test_space_is_left_for_a_title(self):
        (layout, height) = self.layout(1, 200, top=40)
        self.assertEqual(layout.rects[0], (8, 48, 100, 50))
        self.assertEqual(height, 40 + 8 + 50 + 8)

    def test_no_cells(self):
        (layout, height) = self.layout(0, 200)
        self.assertEqual(layout.rects, [])
        self.assertEqual(height, 16)
        self.assertIsNone(layout.hit(10, 10))

    def test_a_click_finds_the_cell(self):
        (layout, _) = self.layout(5, 350)
        self.assertEqual(layout.hit(8, 8), 0)
        self.assertEqual(layout.hit(107, 57), 0)
        self.assertEqual(layout.hit(120, 20), 1)
        self.assertEqual(layout.hit(250, 20), 2)
        self.assertEqual(layout.hit(20, 70), 3)
        self.assertEqual(layout.hit(130, 70), 4)

    def test_a_click_between_cells_or_outside_finds_none(self):
        (layout, _) = self.layout(5, 350)
        self.assertIsNone(layout.hit(0, 0))           # the margin
        self.assertIsNone(layout.hit(108, 20))        # the space between 0 and 1
        self.assertIsNone(layout.hit(20, 58))         # the space between the rows
        self.assertIsNone(layout.hit(340, 20))        # beyond the last column
        self.assertIsNone(layout.hit(240, 70))        # where a sixth cell would be
        self.assertIsNone(layout.hit(20, 400))        # below


if __name__ == '__main__':
    unittest.main()
