from __future__ import annotations

import json
import math
import re
import tempfile
import unittest
from pathlib import Path

from openmill.core.models import MotionKind, Stock, Tool
from openmill.core.registry import registry
from openmill.operations.nativecam_catalog import NATIVECAM_COMPONENT_IDS


class NativeCamCoverageTests(unittest.TestCase):
    def test_all_fifty_components_are_registered_once(self) -> None:
        plugins = [plugin for plugin in registry.all() if hasattr(plugin, "nativecam_source_id")]
        self.assertEqual(len(plugins), 50)
        self.assertEqual(
            {plugin.nativecam_source_id for plugin in plugins}, set(NATIVECAM_COMPONENT_IDS)
        )

    def test_every_nativecam_label_and_choice_has_us_translation(self) -> None:
        catalog = json.loads(
            (Path(__file__).parents[1] / "src/openmill/translations/openmill_en.json").read_text(
                encoding="utf-8"
            )
        )["messages"]
        for plugin in registry.all():
            if not hasattr(plugin, "nativecam_source_id"):
                continue
            strings = [plugin.label, plugin.category, plugin.description]
            strings.extend(field.label for field in plugin.all_fields())
            strings.extend(
                label for field in plugin.all_fields() for _value, label in field.choices
            )
            for source in strings:
                self.assertIn(source, catalog, f"Traduction US absente : {source}")

    def test_every_component_generates_motions_or_linuxcnc_lines(self) -> None:
        stock = Stock()
        tool = Tool(1, 6.0, "Test")
        with tempfile.TemporaryDirectory() as directory:
            included = Path(directory) / "included.ngc"
            included.write_text("G4 P0.1\n", encoding="ascii")
            for plugin in registry.all():
                if not hasattr(plugin, "nativecam_source_id"):
                    continue
                operation = plugin.create_record(stock)
                if plugin.nativecam_source_id == "gcode":
                    operation.parameters["content"] = "G4 P0.1"
                elif plugin.nativecam_source_id == "gcode_file":
                    operation.parameters["content"] = str(included)
                path = plugin.generate(operation, stock, tool)
                self.assertTrue(
                    path.motions or path.program_lines,
                    f"{plugin.nativecam_source_id} ne produit aucun résultat",
                )

    def test_custom_gcode_rejects_program_termination(self) -> None:
        plugin = registry.get("nativecam_gcode")
        operation = plugin.create_record(Stock())
        operation.parameters["content"] = "M30"
        with self.assertRaisesRegex(ValueError, "M2/M30"):
            plugin.generate(operation, Stock(), Tool(1, 6.0, "Test"))

    def test_two_point_circle_uses_diameter_endpoints(self) -> None:
        plugin = registry.get("nativecam_circle2")
        operation = plugin.create_record(Stock())
        operation.parameters.update(start_x=20, start_y=40, end_x=60, end_y=40, side="on")

        path = plugin.generate(operation, Stock(), Tool(1, 6.0, "Test"))
        points = [motion.end for motion in path.motions if motion.kind is MotionKind.CUT]

        self.assertAlmostEqual(min(point.x for point in points), 20, places=4)
        self.assertAlmostEqual(max(point.x for point in points), 60, places=4)
        self.assertAlmostEqual(
            (min(point.y for point in points) + max(point.y for point in points)) / 2, 40, places=4
        )

    def test_irregular_drilling_uses_each_entered_angle(self) -> None:
        plugin = registry.get("nativecam_drill_circle_irr")
        operation = plugin.create_record(Stock(), 5)
        operation.parameters.update(center_x=50, center_y=30, diameter=20, angles="0;45;170;271")

        path = plugin.generate(operation, Stock(), Tool(5, 5.0, "Drill"))

        self.assertEqual(sum(motion.kind is MotionKind.PLUNGE for motion in path.motions), 4)

    def test_thread_milling_is_a_three_dimensional_helix(self) -> None:
        plugin = registry.get("nativecam_thread_milling")
        operation = plugin.create_record(Stock())
        operation.parameters.update(
            major_diameter=20,
            minor_diameter=17,
            pitch=2,
            z_start=0,
            z_final=-8,
        )

        path = plugin.generate(operation, Stock(), Tool(1, 6.0, "Thread mill"))
        cuts = [motion for motion in path.motions if motion.kind is MotionKind.CUT]

        self.assertGreater(len(cuts), 200)
        self.assertAlmostEqual(cuts[-1].end.z, -8, places=4)
        radii = [math.hypot(motion.end.x - 60, motion.end.y - 40) for motion in cuts]
        self.assertAlmostEqual(min(radii), 7, places=3)
        self.assertAlmostEqual(max(radii), 7, places=3)

    def test_counterbore_contains_hole_and_bore_depths(self) -> None:
        plugin = registry.get("nativecam_cb_single")
        operation = plugin.create_record(Stock())
        operation.parameters.update(hole_depth=-12, bore_depth=-4, bore_diameter=14)

        path = plugin.generate(operation, Stock(), Tool(1, 6.0, "End mill"))
        plunge_depths = [
            motion.end.z for motion in path.motions if motion.kind is MotionKind.PLUNGE
        ]

        self.assertIn(-12, plunge_depths)
        self.assertIn(-4, plunge_depths)

    def test_every_nativecam_mill_menu_component_is_accounted_for(self) -> None:
        document = (Path(__file__).parents[1] / "docs" / "nativecam-coverage.md").read_text(
            encoding="utf-8"
        )
        rows = re.findall(r"^\|\s*(\d+)\s*\|\s*`([^`]+)`\s*\|", document, re.MULTILINE)
        self.assertEqual([int(number) for number, _component in rows], list(range(1, 51)))
        self.assertEqual(len({component for _number, component in rows}), 50)

    def test_coverage_totals_match_the_fifty_component_catalog(self) -> None:
        document = (Path(__file__).parents[1] / "docs" / "nativecam-coverage.md").read_text(
            encoding="utf-8"
        )
        totals = {
            label: int(count)
            for label, count in re.findall(
                r"^\| (Disponible|Partiel|Fourni par Probe Basic|Manquant) \| (\d+) \|$",
                document,
                re.MULTILINE,
            )
        }
        self.assertEqual(sum(totals.values()), 50)


if __name__ == "__main__":
    unittest.main()
