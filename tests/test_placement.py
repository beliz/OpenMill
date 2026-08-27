from __future__ import annotations

import math
import unittest

from openmill.adapters.mock import MockMachineAdapter
from openmill.core.engine import build_project
from openmill.core.gcode import generate_gcode
from openmill.core.models import (
    MotionKind,
    PlacementMode,
    Project,
    RepetitionBlock,
    RepetitionOrder,
    Stock,
)
from openmill.core.placement import placement_instances
from openmill.core.project_io import dumps_project, loads_project
from openmill.core.registry import registry


class PlacementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stock = Stock(width=120, height=80, thickness=16)
        self.adapter = MockMachineAdapter()

    def operation(self, plugin_id: str = "drill_single"):
        return registry.get(plugin_id).create_record(self.stock, 5)

    def test_old_projects_without_placement_remain_compatible(self) -> None:
        restored = loads_project(
            '{"name":"Ancien","stock":{"width":120,"height":80,"thickness":16},'
            '"operations":[{"plugin_id":"drill_single","title":"Trou",'
            '"tool_number":5,"parameters":{}}]}'
        )
        self.assertEqual(restored.operations[0].placement.mode, PlacementMode.SINGLE)

    def test_pattern_roundtrip_preserves_every_setting(self) -> None:
        operation = self.operation()
        operation.placement.mode = PlacementMode.GRID
        operation.placement.columns = 4
        operation.placement.rows = 3
        operation.placement.grid_angle = 30
        operation.placement.rotate_geometry = True
        restored = loads_project(dumps_project(Project(stock=self.stock, operations=[operation])))
        placement = restored.operations[0].placement
        self.assertEqual(placement.mode, PlacementMode.GRID)
        self.assertEqual((placement.columns, placement.rows), (4, 3))
        self.assertEqual(placement.grid_angle, 30)
        self.assertTrue(placement.rotate_geometry)

    def test_schema_two_stores_repetition_outside_operations(self) -> None:
        operation = self.operation()
        operation.placement.mode = PlacementMode.POLAR
        payload = dumps_project(Project(stock=self.stock, operations=[operation]))
        self.assertIn('"repetitions":', payload)
        operation_payload = payload.split('"operations":', 1)[1].split('"repetitions":', 1)[0]
        self.assertNotIn('"placement":', operation_payload)

    def test_schema_one_pattern_is_migrated_to_a_repetition_block(self) -> None:
        restored = loads_project(
            '{"schema_version":1,"operations":[{"plugin_id":"drill_single",'
            '"title":"Trou","placement":{"mode":"polar","count":5}}]}'
        )
        self.assertEqual(restored.schema_version, 2)
        self.assertEqual(restored.repetitions[0].placement.mode, PlacementMode.POLAR)
        self.assertEqual(restored.repetitions[0].placement.count, 5)

    def test_linear_pattern_expands_one_cycle_at_every_position(self) -> None:
        operation = self.operation()
        operation.parameters.update(center_x=10, center_y=12, z_final=-4)
        operation.placement.mode = PlacementMode.LINEAR
        operation.placement.start_x = 20
        operation.placement.start_y = 15
        operation.placement.count = 3
        operation.placement.step_x = 25
        operation.placement.step_y = 5
        result = build_project(Project(stock=self.stock, operations=[operation]), self.adapter)
        self.assertFalse(result.errors)
        path = result.toolpaths[0]
        plunges = [motion for motion in path.motions if motion.kind is MotionKind.PLUNGE]
        self.assertEqual(path.instance_count, 3)
        self.assertEqual([(motion.end.x, motion.end.y) for motion in plunges], [(20, 15), (45, 20), (70, 25)])

    def test_grid_uses_serpentine_order_and_rotation(self) -> None:
        operation = self.operation()
        placement = operation.placement
        placement.mode = PlacementMode.GRID
        placement.start_x = 10
        placement.start_y = 20
        placement.columns = 3
        placement.rows = 2
        placement.spacing_x = 10
        placement.spacing_y = 5
        placement.grid_angle = 90
        placement.serpentine = True
        positions = placement_instances(operation, self.stock)
        expected = [(10, 20), (10, 30), (10, 40), (5, 40), (5, 30), (5, 20)]
        for position, target in zip(positions, expected, strict=True):
            self.assertTrue(math.isclose(position.x, target[0], abs_tol=1e-8))
            self.assertTrue(math.isclose(position.y, target[1], abs_tol=1e-8))

    def test_polar_pattern_does_not_duplicate_full_circle_endpoint(self) -> None:
        operation = self.operation()
        placement = operation.placement
        placement.mode = PlacementMode.POLAR
        placement.center_x = 50
        placement.center_y = 40
        placement.diameter = 40
        placement.count = 4
        placement.start_angle = 0
        placement.sweep = 360
        positions = placement_instances(operation, self.stock)
        expected = [(70, 40), (50, 60), (30, 40), (50, 20)]
        for position, target in zip(positions, expected, strict=True):
            self.assertTrue(math.isclose(position.x, target[0], abs_tol=1e-8))
            self.assertTrue(math.isclose(position.y, target[1], abs_tol=1e-8))

    def test_connectors_never_traverse_laterally_below_clearance(self) -> None:
        operation = self.operation()
        operation.placement.mode = PlacementMode.LINEAR
        operation.placement.count = 3
        operation.placement.step_x = 20
        result = build_project(Project(stock=self.stock, operations=[operation]), self.adapter)
        clearance = operation.parameters["clearance"]
        for motion in result.toolpaths[0].motions:
            lateral = abs(motion.start.x - motion.end.x) > 1e-8 or abs(motion.start.y - motion.end.y) > 1e-8
            if motion.kind is MotionKind.RAPID and lateral:
                self.assertGreaterEqual(motion.start.z, clearance)
                self.assertGreaterEqual(motion.end.z, clearance)

    def test_invalid_pattern_is_reported_on_its_operation(self) -> None:
        operation = self.operation()
        operation.placement.mode = PlacementMode.LINEAR
        operation.placement.count = 2
        operation.placement.step_x = 0
        operation.placement.step_y = 0
        result = build_project(Project(stock=self.stock, operations=[operation]), self.adapter)
        self.assertFalse(result.toolpaths)
        self.assertIn("incrément", result.errors[0].message)

    def test_gcode_identifies_conversational_pattern(self) -> None:
        operation = self.operation()
        operation.placement.mode = PlacementMode.LINEAR
        operation.placement.count = 2
        result = build_project(Project(stock=self.stock, operations=[operation]), self.adapter)
        output = generate_gcode(Project(stock=self.stock, operations=[operation]), result.toolpaths)
        self.assertIn("(MOTIF - Ligne - 2 positions - 2 appels)", output)

    def test_user_can_execute_nested_operations_by_position(self) -> None:
        first = self.operation()
        first.title = "Premier"
        second = self.operation("drill_dwell")
        second.title = "Second"
        repetition = RepetitionBlock(
            operation_uids=[first.uid, second.uid],
            execution_order=RepetitionOrder.BY_POSITION,
        )
        repetition.placement.mode = PlacementMode.LINEAR
        repetition.placement.count = 2
        project = Project(
            stock=self.stock,
            operations=[first, second],
            repetitions=[repetition],
        )
        result = build_project(project, self.adapter)
        self.assertEqual(
            [(path.operation_title, path.repetition_position) for path in result.toolpaths],
            [("Premier", 1), ("Second", 1), ("Premier", 2), ("Second", 2)],
        )

    def test_user_can_execute_nested_operations_by_operation(self) -> None:
        first = self.operation()
        first.title = "Premier"
        second = self.operation("drill_dwell")
        second.title = "Second"
        repetition = RepetitionBlock(
            operation_uids=[first.uid, second.uid],
            execution_order=RepetitionOrder.BY_OPERATION,
        )
        repetition.placement.mode = PlacementMode.LINEAR
        repetition.placement.count = 2
        project = Project(
            stock=self.stock,
            operations=[first, second],
            repetitions=[repetition],
        )
        result = build_project(project, self.adapter)
        self.assertEqual(
            [(path.operation_title, path.instance_count) for path in result.toolpaths],
            [("Premier", 2), ("Second", 2)],
        )
        self.assertIn("ordre par operation", generate_gcode(project, result.toolpaths))


class HoleCycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stock = Stock(width=120, height=80, thickness=16)
        self.adapter = MockMachineAdapter()

    def build(self, plugin_id: str, **parameters):
        operation = registry.get(plugin_id).create_record(self.stock, 5)
        operation.parameters.update(parameters)
        project = Project(stock=self.stock, operations=[operation])
        result = build_project(project, self.adapter)
        self.assertFalse(result.errors)
        return project, result.toolpaths[0]

    def test_expected_conversational_hole_cycles_are_registered(self) -> None:
        expected = {"drill_single", "drill_peck", "drill_dwell", "ream", "tap_rigid"}
        self.assertTrue(expected.issubset({plugin.id for plugin in registry.all()}))

    def test_dwell_cycle_generates_g4(self) -> None:
        project, path = self.build("drill_dwell", dwell=0.75)
        self.assertEqual(sum(motion.kind is MotionKind.DWELL for motion in path.motions), 1)
        self.assertIn("G4 P0.7500", generate_gcode(project, [path]))

    def test_reaming_returns_at_programmed_feed(self) -> None:
        _project, path = self.build("ream", z_start=0, z_final=-6, retract_feed=240)
        returns = [
            motion
            for motion in path.motions
            if motion.kind is MotionKind.PLUNGE and motion.end.z > motion.start.z
        ]
        self.assertEqual(len(returns), 1)
        self.assertEqual(returns[0].feed, 240)

    def test_rigid_tapping_generates_one_synchronized_cycle(self) -> None:
        project, path = self.build("tap_rigid", pitch=1.25, z_final=-12)
        output = generate_gcode(project, [path])
        self.assertIn("G33.1 Z-12.0000 K1.2500", output)
        self.assertEqual(output.count("G33.1"), 1)
        self.assertIn("codeur de broche", path.warnings[0])

    def test_left_hand_tapping_uses_reverse_spindle(self) -> None:
        project, path = self.build("tap_rigid", direction="left")
        self.assertIn(" M4", generate_gcode(project, [path]))


if __name__ == "__main__":
    unittest.main()
