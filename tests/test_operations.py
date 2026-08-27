from __future__ import annotations

import math
import unittest

from openmill.adapters.mock import MockMachineAdapter
from openmill.core.engine import build_project
from openmill.core.models import MotionKind, OriginMode, Project, Stock, Tool
from openmill.core.registry import registry


class OperationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stock = Stock(width=120, height=80, thickness=16)
        self.adapter = MockMachineAdapter()

    def make_path(self, plugin_id: str, *, tool: int = 1, **parameters):
        operation = registry.get(plugin_id).create_record(self.stock, tool)
        operation.parameters.update(parameters)
        return registry.get(plugin_id).generate(operation, self.stock, self.adapter.get_tool(tool))

    def test_all_expected_operations_are_registered(self) -> None:
        registered = {plugin.id for plugin in registry.all()}
        expected = {
            "facing",
            "pocket_rectangle",
            "pocket_circle",
            "hexagon",
            "drill_circle",
            "drill_grid",
            "profile_rectangle",
            "profile_circle",
            "profile_polygon",
            "slot_straight",
        }
        self.assertTrue(expected.issubset(registered))

    def test_facing_extends_beyond_stock_edges(self) -> None:
        path = self.make_path("facing", tool=4)
        cuts = [motion for motion in path.motions if motion.kind is MotionKind.CUT]
        self.assertLess(min(min(motion.start.x, motion.end.x) for motion in cuts), self.stock.x_min)
        self.assertGreater(max(max(motion.start.x, motion.end.x) for motion in cuts), self.stock.x_max)

    def test_facing_reaches_final_depth(self) -> None:
        path = self.make_path("facing", z_final=-2.5, step_down=1)
        self.assertAlmostEqual(min(motion.end.z for motion in path.motions), -2.5)

    def test_rectangle_rejects_tool_larger_than_pocket(self) -> None:
        with self.assertRaises(ValueError):
            self.make_path("pocket_rectangle", width=4)

    def test_rectangle_warns_about_impossible_corner_radius(self) -> None:
        path = self.make_path("pocket_rectangle", corner_radius=1)
        self.assertTrue(path.warnings)

    def test_rectangle_remains_inside_requested_boundary_after_tool_compensation(self) -> None:
        path = self.make_path("pocket_rectangle", center_x=50, center_y=40, width=40, height=30)
        radius = path.tool.diameter / 2
        cuts = [motion for motion in path.motions if motion.kind is not MotionKind.RAPID]
        self.assertTrue(all(30 + radius - 1e-7 <= motion.end.x <= 70 - radius + 1e-7 for motion in cuts))

    def test_circle_rejects_too_small_diameter(self) -> None:
        with self.assertRaises(ValueError):
            self.make_path("pocket_circle", diameter=5)

    def test_circle_respects_requested_outer_diameter(self) -> None:
        path = self.make_path("pocket_circle", center_x=30, center_y=25, diameter=30)
        max_radius = max(
            math.hypot(motion.end.x - 30, motion.end.y - 25)
            for motion in path.motions
            if motion.kind is not MotionKind.RAPID
        )
        self.assertAlmostEqual(max_radius + path.tool.diameter / 2, 15, places=5)

    def test_interior_hexagon_warns_about_corner_radius(self) -> None:
        path = self.make_path("hexagon", mode="interior")
        self.assertTrue(path.warnings)

    def test_exterior_hexagon_is_larger_than_interior_path(self) -> None:
        interior = self.make_path("hexagon", mode="interior", across_flats=30)
        exterior = self.make_path("hexagon", mode="exterior", across_flats=30)
        first_interior = next(motion for motion in interior.motions if motion.kind is MotionKind.PLUNGE)
        first_exterior = next(motion for motion in exterior.motions if motion.kind is MotionKind.PLUNGE)
        self.assertGreater(first_exterior.end.x, first_interior.end.x)

    def test_rectangle_profile_compensates_inside_and_outside(self) -> None:
        inside = self.make_path(
            "profile_rectangle",
            center_x=50,
            center_y=40,
            width=40,
            height=30,
            corner_radius=0,
            mode="inside",
            side_allowance=0,
        )
        outside = self.make_path(
            "profile_rectangle",
            center_x=50,
            center_y=40,
            width=40,
            height=30,
            corner_radius=0,
            mode="outside",
            side_allowance=0,
        )
        inside_x = [
            motion.end.x for motion in inside.motions if motion.kind is MotionKind.CUT
        ]
        outside_x = [
            motion.end.x for motion in outside.motions if motion.kind is MotionKind.CUT
        ]
        self.assertAlmostEqual(min(inside_x), 30 + inside.tool.diameter / 2)
        self.assertAlmostEqual(max(inside_x), 70 - inside.tool.diameter / 2)
        self.assertAlmostEqual(min(outside_x), 30 - outside.tool.diameter / 2)
        self.assertAlmostEqual(max(outside_x), 70 + outside.tool.diameter / 2)

    def test_circle_profile_finish_pass_reaches_exact_compensation(self) -> None:
        path = self.make_path(
            "profile_circle",
            center_x=0,
            center_y=0,
            diameter=40,
            mode="outside",
            side_allowance=0.4,
            finish_pass="enabled",
        )
        radii = [
            math.hypot(motion.end.x, motion.end.y)
            for motion in path.motions
            if motion.kind is MotionKind.CUT
        ]
        self.assertAlmostEqual(min(radii), 20 + path.tool.diameter / 2)
        self.assertAlmostEqual(max(radii), 20 + path.tool.diameter / 2 + 0.4)

    def test_profile_on_the_line_ignores_compensation_and_allowance(self) -> None:
        path = self.make_path(
            "profile_circle",
            center_x=0,
            center_y=0,
            diameter=40,
            mode="on",
            side_allowance=0.4,
        )
        radii = [
            math.hypot(motion.end.x, motion.end.y)
            for motion in path.motions
            if motion.kind is MotionKind.CUT
        ]
        self.assertTrue(radii)
        self.assertTrue(all(math.isclose(radius, 20, abs_tol=1e-6) for radius in radii))

    def test_polygon_profile_accepts_variable_side_count(self) -> None:
        path = self.make_path(
            "profile_polygon",
            sides=8,
            across_flats=40,
            mode="outside",
            side_allowance=0,
        )
        cuts = [motion for motion in path.motions if motion.kind is MotionKind.CUT]
        self.assertGreaterEqual(len(cuts), 8)

    def test_straight_slot_respects_requested_outer_dimensions(self) -> None:
        path = self.make_path(
            "slot_straight",
            center_x=0,
            center_y=0,
            length=50,
            width=16,
            rotation=0,
            side_allowance=0,
        )
        cuts = [motion.end for motion in path.motions if motion.kind is MotionKind.CUT]
        self.assertAlmostEqual(max(point.x for point in cuts) + path.tool.diameter / 2, 25)
        self.assertAlmostEqual(min(point.x for point in cuts) - path.tool.diameter / 2, -25)
        self.assertAlmostEqual(max(point.y for point in cuts) + path.tool.diameter / 2, 8)
        self.assertAlmostEqual(min(point.y for point in cuts) - path.tool.diameter / 2, -8)

    def test_straight_slot_rejects_impossible_dimensions(self) -> None:
        with self.assertRaises(ValueError):
            self.make_path("slot_straight", length=10, width=12)
        with self.assertRaises(ValueError):
            self.make_path("slot_straight", length=20, width=4)

    def test_circular_drilling_creates_exactly_requested_holes(self) -> None:
        path = self.make_path("drill_circle", tool=5, hole_count=9)
        self.assertEqual(sum(motion.kind is MotionKind.PLUNGE for motion in path.motions), 9)

    def test_partial_drilling_arc_includes_both_endpoints(self) -> None:
        path = self.make_path("drill_circle", tool=5, center_x=0, center_y=0, diameter=20, hole_count=3, sweep=180)
        positions = [motion.end for motion in path.motions if motion.kind is MotionKind.PLUNGE]
        self.assertAlmostEqual(positions[0].x, 10)
        self.assertAlmostEqual(positions[-1].x, -10)

    def test_peck_drilling_retracts_between_depths(self) -> None:
        path = self.make_path("drill_circle", tool=5, hole_count=2, z_final=-5, peck=2)
        self.assertEqual(sum(motion.kind is MotionKind.PLUNGE for motion in path.motions), 6)

    def test_drilling_grid_creates_rows_times_columns(self) -> None:
        path = self.make_path("drill_grid", tool=5, columns=4, rows=3)
        self.assertEqual(sum(motion.kind is MotionKind.PLUNGE for motion in path.motions), 12)

    def test_center_origin_changes_new_operation_defaults(self) -> None:
        stock = Stock(width=100, height=80, thickness=10, origin=OriginMode.CENTER)
        operation = registry.get("pocket_circle").create_record(stock)
        self.assertEqual(operation.parameters["center_x"], 0)
        self.assertEqual(operation.parameters["center_y"], 0)

    def test_project_build_isolates_invalid_operations(self) -> None:
        valid = registry.get("facing").create_record(self.stock)
        invalid = registry.get("pocket_circle").create_record(self.stock)
        invalid.parameters["diameter"] = 1
        result = build_project(Project(stock=self.stock, operations=[valid, invalid]), self.adapter)
        self.assertEqual(len(result.toolpaths), 1)
        self.assertEqual(len(result.errors), 1)

    def test_project_build_recomputes_tool_diameter_formulas(self) -> None:
        adapter = MockMachineAdapter((Tool(9, 20.0, "Foret de test", 40.0),))
        operation = registry.get("drill_single").create_record(self.stock, 9)
        operation.parameters["center_x"] = 0
        operation.expressions["center_x"] = "5+tool_diam/2"

        result = build_project(Project(stock=self.stock, operations=[operation]), adapter)

        self.assertFalse(result.errors)
        plunge = next(
            motion for motion in result.toolpaths[0].motions if motion.kind is MotionKind.PLUNGE
        )
        self.assertEqual(plunge.end.x, 15)
        self.assertEqual(operation.parameters["center_x"], 0)

    def test_project_build_recomputes_stock_dimension_formulas(self) -> None:
        operation = registry.get("drill_single").create_record(self.stock, 5)
        operation.parameters.update(center_x=0, center_y=0)
        operation.expressions.update(center_x="stock_x/2", center_y="brut_y/2")

        result = build_project(Project(stock=self.stock, operations=[operation]), self.adapter)

        self.assertFalse(result.errors)
        plunge = next(
            motion for motion in result.toolpaths[0].motions if motion.kind is MotionKind.PLUNGE
        )
        self.assertEqual((plunge.end.x, plunge.end.y), (60, 40))
        self.assertEqual((operation.parameters["center_x"], operation.parameters["center_y"]), (0, 0))

    def test_disabled_operations_are_ignored(self) -> None:
        operation = registry.get("facing").create_record(self.stock)
        operation.enabled = False
        self.assertFalse(build_project(Project(stock=self.stock, operations=[operation]), self.adapter).toolpaths)

    def test_depth_beyond_stock_generates_warning(self) -> None:
        operation = registry.get("drill_circle").create_record(self.stock, 5)
        operation.parameters["z_final"] = -20
        result = build_project(Project(stock=self.stock, operations=[operation]), self.adapter)
        self.assertTrue(any("face inférieure" in issue.message for issue in result.warnings))

    def test_cutting_beyond_stock_sides_generates_warning(self) -> None:
        operation = registry.get("pocket_circle").create_record(self.stock)
        operation.parameters.update(center_x=2, diameter=20)
        result = build_project(Project(stock=self.stock, operations=[operation]), self.adapter)
        self.assertTrue(any("limites latérales" in issue.message for issue in result.warnings))

    def test_facing_overshoot_does_not_generate_false_stock_warning(self) -> None:
        operation = registry.get("facing").create_record(self.stock, 4)
        result = build_project(Project(stock=self.stock, operations=[operation]), self.adapter)
        self.assertFalse(any("limites latérales" in issue.message for issue in result.warnings))

    def test_lateral_rapid_motions_stay_at_clearance_height(self) -> None:
        for plugin in registry.all():
            operation = plugin.create_record(self.stock, 5 if plugin.id.startswith("drill_") else 1)
            # Program/meta components (comments, probing commands, file
            # inclusion, tool selection) intentionally have no clearance
            # plane or preview motions.
            if "clearance" not in operation.parameters:
                continue
            path = plugin.generate(operation, self.stock, self.adapter.get_tool(operation.tool_number))
            clearance = operation.parameters["clearance"]
            for motion in path.motions:
                has_lateral_movement = abs(motion.start.x - motion.end.x) > 1e-7 or abs(motion.start.y - motion.end.y) > 1e-7
                if motion.kind is MotionKind.RAPID and has_lateral_movement:
                    self.assertGreaterEqual(motion.start.z, clearance - 1e-7, plugin.id)
                    self.assertGreaterEqual(motion.end.z, clearance - 1e-7, plugin.id)


if __name__ == "__main__":
    unittest.main()
