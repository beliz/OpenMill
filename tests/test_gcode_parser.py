from __future__ import annotations

import unittest

from openmill.core.gcode_parser import parse_gcode
from openmill.core.models import MotionKind, OriginMode, Tool


class GcodeParserTests(unittest.TestCase):
    def test_linear_absolute_and_incremental_moves_are_converted(self) -> None:
        parsed = parse_gcode("G21 G90\nG0 X10 Y5 Z2\nG1 Z-1 F120\nG91\nG1 X4\n")
        motions = parsed.result.toolpaths[0].motions
        self.assertEqual((motions[0].end.x, motions[0].end.y, motions[0].end.z), (10, 5, 2))
        self.assertEqual(motions[1].kind, MotionKind.PLUNGE)
        self.assertEqual((motions[-1].end.x, motions[-1].end.z), (14, -1))

    def test_inch_program_is_normalized_to_millimetres(self) -> None:
        parsed = parse_gcode("G20 G90\nG1 X1 Y0.5 F10")
        motion = parsed.result.toolpaths[0].motions[0]
        self.assertAlmostEqual(motion.end.x, 25.4)
        self.assertAlmostEqual(motion.end.y, 12.7)
        self.assertAlmostEqual(motion.feed, 254)

    def test_ijk_arc_is_interpolated_for_preview(self) -> None:
        parsed = parse_gcode("G21 G90 G17\nG0 X1 Y0\nG3 X0 Y1 I-1 J0 F200")
        motions = parsed.result.toolpaths[0].motions
        self.assertGreater(len(motions), 3)
        self.assertAlmostEqual(motions[-1].end.x, 0)
        self.assertAlmostEqual(motions[-1].end.y, 1)

    def test_openmill_stock_metadata_is_reused(self) -> None:
        parsed = parse_gcode(
            '(OPENMILL_STOCK {"width":140,"height":95,"thickness":18,"origin":"center"})\nG0 X0'
        )
        self.assertEqual(parsed.project.stock.width, 140)
        self.assertEqual(parsed.project.stock.origin, OriginMode.CENTER)

    def test_tool_table_diameter_is_used(self) -> None:
        parsed = parse_gcode(
            "T7 M6\nG1 X10",
            tool_lookup=lambda number: Tool(number, 12.0, "Fraise test"),
        )
        self.assertEqual(parsed.result.toolpaths[0].tool.number, 7)
        self.assertEqual(parsed.result.toolpaths[0].tool.diameter, 12)

    def test_source_lines_are_mapped_to_completed_preview_movements(self) -> None:
        parsed = parse_gcode("(entete)\nG0 X1\n\nG1 X2\nM30")
        self.assertEqual(parsed.line_motion_counts, {1: 0, 2: 1, 3: 1, 4: 2, 5: 2})

    def test_radius_arc_is_interpolated(self) -> None:
        parsed = parse_gcode("G0 X0 Y0\nG2 X10 Y0 R5")
        self.assertFalse(parsed.warnings)
        self.assertGreater(len(parsed.result.toolpaths[0].motions), 5)
        self.assertAlmostEqual(parsed.result.toolpaths[0].motions[-1].end.x, 10)

    def test_impossible_radius_arc_falls_back_with_warning(self) -> None:
        parsed = parse_gcode("G0 X0 Y0\nG2 X10 Y0 R2")
        self.assertEqual(len(parsed.warnings), 1)
        self.assertIn("rayon R impossible", parsed.warnings[0])


if __name__ == "__main__":
    unittest.main()
