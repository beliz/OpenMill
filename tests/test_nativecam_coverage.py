from __future__ import annotations

from pathlib import Path
import re
import unittest


class NativeCamCoverageTests(unittest.TestCase):
    def test_every_nativecam_mill_menu_component_is_accounted_for(self) -> None:
        document = (
            Path(__file__).parents[1] / "docs" / "nativecam-coverage.md"
        ).read_text(encoding="utf-8")
        rows = re.findall(r"^\|\s*(\d+)\s*\|\s*`([^`]+)`\s*\|", document, re.MULTILINE)
        self.assertEqual([int(number) for number, _component in rows], list(range(1, 51)))
        self.assertEqual(len({component for _number, component in rows}), 50)

    def test_coverage_totals_match_the_fifty_component_catalog(self) -> None:
        document = (
            Path(__file__).parents[1] / "docs" / "nativecam-coverage.md"
        ).read_text(encoding="utf-8")
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
