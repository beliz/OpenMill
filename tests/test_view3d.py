from __future__ import annotations

import math
import unittest

from openmill.core.models import OriginMode, Point, Stock
from openmill.core.view3d import OrbitProjection, stock_corners


class OrbitProjectionTests(unittest.TestCase):
    def test_camera_centers_on_stock(self) -> None:
        stock = Stock(width=120, height=80, thickness=20)
        camera = OrbitProjection.from_stock(stock)
        self.assertEqual(camera.project(Point(60, 40, -10)), (0, 0))

    def test_center_origin_is_supported(self) -> None:
        stock = Stock(width=120, height=80, thickness=20, origin=OriginMode.CENTER)
        camera = OrbitProjection.from_stock(stock)
        self.assertEqual((camera.center_x, camera.center_y, camera.center_z), (0, 0, -10))

    def test_zero_angles_preserve_horizontal_and_vertical_axes(self) -> None:
        camera = OrbitProjection(0, 0, 0, yaw=0, pitch=0)
        self.assertEqual(camera.project(Point(12, 99, 5)), (12, 5))
        self.assertEqual(camera.depth(Point(12, 99, 5)), 99)

    def test_yaw_rotates_horizontal_axis(self) -> None:
        camera = OrbitProjection(0, 0, 0, yaw=90, pitch=0)
        horizontal, vertical = camera.project(Point(0, 8, 3))
        self.assertAlmostEqual(horizontal, -8)
        self.assertAlmostEqual(vertical, 3)

    def test_pitch_is_clamped_for_touch_rotation(self) -> None:
        camera = OrbitProjection(0, 0, 0)
        camera.orbit(0, 1_000)
        self.assertEqual(camera.pitch, 82)
        camera.orbit(0, -2_000)
        self.assertEqual(camera.pitch, -82)

    def test_yaw_wraps_into_stable_range(self) -> None:
        camera = OrbitProjection(0, 0, 0)
        camera.orbit(4_000, 0)
        self.assertGreaterEqual(camera.yaw, -180)
        self.assertLess(camera.yaw, 180)

    def test_zoom_is_clamped(self) -> None:
        camera = OrbitProjection(0, 0, 0)
        camera.magnify(10_000)
        self.assertEqual(camera.zoom, 5)
        camera.magnify(0.000001)
        self.assertEqual(camera.zoom, 0.25)

    def test_nonpositive_zoom_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            OrbitProjection(0, 0, 0).magnify(0)

    def test_stock_has_eight_distinct_corners(self) -> None:
        corners = stock_corners(Stock(width=120, height=80, thickness=20))
        self.assertEqual(len(corners), 8)
        self.assertEqual(len(set(corners)), 8)

    def test_projection_remains_finite_for_every_stock_corner(self) -> None:
        stock = Stock(width=120, height=80, thickness=20)
        camera = OrbitProjection.from_stock(stock)
        for point in stock_corners(stock):
            x, y = camera.project(point)
            self.assertTrue(math.isfinite(x) and math.isfinite(y))


if __name__ == "__main__":
    unittest.main()
