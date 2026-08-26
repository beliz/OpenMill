from __future__ import annotations

import math
import unittest

from openmill.core.geometry import (
    circle_points,
    depth_levels,
    linear_positions,
    regular_polygon_points,
    rotate_point,
    rounded_rectangle_points,
)


class GeometryTests(unittest.TestCase):
    def test_depth_levels_include_exact_final_depth(self) -> None:
        self.assertEqual(depth_levels(0, -5, 2), [-2, -4, -5])

    def test_depth_levels_reject_upward_cut(self) -> None:
        with self.assertRaises(ValueError):
            depth_levels(0, 1, 1)

    def test_depth_levels_reject_nonpositive_step(self) -> None:
        with self.assertRaises(ValueError):
            depth_levels(0, -1, 0)

    def test_linear_positions_never_exceed_maximum_step(self) -> None:
        positions = linear_positions(0, 10, 3)
        self.assertEqual(positions[0], 0)
        self.assertEqual(positions[-1], 10)
        self.assertTrue(all(right - left <= 3 for left, right in zip(positions, positions[1:])))

    def test_descending_positions_work(self) -> None:
        self.assertEqual(linear_positions(6, 0, 2), [6, 4, 2, 0])

    def test_circle_is_closed(self) -> None:
        points = circle_points(10, 20, 4, segments=32)
        self.assertEqual(len(points), 33)
        self.assertAlmostEqual(points[0][0], points[-1][0])
        self.assertAlmostEqual(points[0][1], points[-1][1])

    def test_zero_radius_circle_is_a_single_point(self) -> None:
        self.assertEqual(circle_points(4, 8, 0), [(4, 8)])

    def test_rounded_rectangle_stays_within_bounds(self) -> None:
        for x, y in rounded_rectangle_points(0, 0, 20, 10, 3):
            self.assertLessEqual(abs(x), 10 + 1e-7)
            self.assertLessEqual(abs(y), 5 + 1e-7)

    def test_polygon_has_requested_apothem(self) -> None:
        points = regular_polygon_points(0, 0, 10, sides=6)
        self.assertEqual(len(points), 7)
        circumradius = math.hypot(*points[0])
        self.assertAlmostEqual(circumradius * math.cos(math.pi / 6), 10)

    def test_rotation(self) -> None:
        x, y = rotate_point(3, 0, 90)
        self.assertAlmostEqual(x, 0)
        self.assertAlmostEqual(y, 3)


if __name__ == "__main__":
    unittest.main()
