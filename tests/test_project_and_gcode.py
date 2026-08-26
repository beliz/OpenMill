from __future__ import annotations

import unittest

from openmill.adapters.mock import MockMachineAdapter
from openmill.core.engine import build_project, create_demo_project
from openmill.core.gcode import generate_gcode
from openmill.core.models import OriginMode, Project, Stock
from openmill.core.project_io import dumps_project, loads_project
from openmill.core.registry import registry


class ProjectAndGcodeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = MockMachineAdapter()
        self.project = create_demo_project()
        self.result = build_project(self.project, self.adapter)

    def test_demo_project_builds_without_errors(self) -> None:
        self.assertFalse(self.result.errors)
        self.assertEqual(len(self.result.toolpaths), 3)

    def test_project_json_roundtrip_preserves_operations(self) -> None:
        restored = loads_project(dumps_project(self.project))
        self.assertEqual(restored.name, self.project.name)
        self.assertEqual([operation.uid for operation in restored.operations], [operation.uid for operation in self.project.operations])

    def test_center_origin_roundtrip(self) -> None:
        restored = loads_project(dumps_project(Project(stock=Stock(origin=OriginMode.CENTER))))
        self.assertEqual(restored.stock.origin, OriginMode.CENTER)

    def test_unknown_schema_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            loads_project('{"schema_version": 99}')

    def test_nonobject_json_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            loads_project("[]")

    def test_gcode_uses_linuxcnc_modal_header(self) -> None:
        output = generate_gcode(self.project, self.result.toolpaths)
        output.encode("ascii")
        self.assertIn("G90 G21 G17 G40 G49 G80", output)
        self.assertIn("G54", output)
        self.assertTrue(output.endswith("M30\n%\n"))

    def test_gcode_comments_are_ascii_for_probe_basic(self) -> None:
        self.project.name = "Pièce ébauche Ø 8"
        output = generate_gcode(self.project, self.result.toolpaths)
        self.assertIn("(OPENMILL - Piece ebauche  8)", output)
        self.assertNotIn("é", output)

    def test_gcode_contains_tool_changes(self) -> None:
        output = generate_gcode(self.project, self.result.toolpaths)
        for tool in (4, 1, 5):
            self.assertIn(f"T{tool} M6", output)
            self.assertIn(f"G43 H{tool}", output)

    def test_gcode_contains_machine_readable_stock_metadata(self) -> None:
        output = generate_gcode(self.project, self.result.toolpaths)
        self.assertIn('(OPENMILL_STOCK {"width":140,"height":95,"thickness":18', output)

    def test_first_motion_of_each_operation_sets_absolute_xy(self) -> None:
        output = generate_gcode(self.project, self.result.toolpaths)
        lines = output.splitlines()
        for index, line in enumerate(lines):
            if line.startswith("S") and line.endswith(" M3"):
                self.assertTrue(lines[index + 1].startswith("G0 Z"))
                self.assertIn("X", lines[index + 2])
                self.assertIn("Y", lines[index + 2])

    def test_invalid_work_offset_is_rejected(self) -> None:
        self.project.work_offset = "G54\nM30"
        with self.assertRaises(ValueError):
            generate_gcode(self.project, self.result.toolpaths)

    def test_unsupported_fractional_work_offset_is_rejected(self) -> None:
        self.project.work_offset = "G54.1"
        with self.assertRaises(ValueError):
            generate_gcode(self.project, self.result.toolpaths)

    def test_extended_linuxcnc_work_offset_is_accepted(self) -> None:
        self.project.work_offset = "G59.3"
        self.assertIn("\nG59.3\n", generate_gcode(self.project, self.result.toolpaths))

    def test_first_plunge_at_origin_is_preceded_by_safe_absolute_rapid(self) -> None:
        stock = Stock(origin=OriginMode.CENTER)
        operation = registry.get("pocket_circle").create_record(stock)
        operation.parameters.update(diameter=6, center_x=0, center_y=0)
        project = Project(stock=stock, operations=[operation])
        result = build_project(project, self.adapter)
        output = generate_gcode(project, result.toolpaths)
        self.assertIn("G0 Z5.0000\nG0 X0.0000 Y0.0000\nG1 X0.0000 Y0.0000 Z-1.0000", output)

    def test_comments_cannot_break_out_with_newline(self) -> None:
        self.project.name = "Nom\r\nM30 (test)"
        line = generate_gcode(self.project, self.result.toolpaths).splitlines()[1]
        self.assertEqual(line, "(OPENMILL - Nom  M30 [test])")

    def test_cloned_operation_gets_distinct_uid(self) -> None:
        cloned = self.project.operations[0].clone()
        self.assertNotEqual(cloned.uid, self.project.operations[0].uid)
        self.assertEqual(cloned.parameters, self.project.operations[0].parameters)


if __name__ == "__main__":
    unittest.main()
