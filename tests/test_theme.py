from __future__ import annotations

import ast
from pathlib import Path
import unittest

from openmill.ui.theme import (
    PROBE_BASIC_MODERN_STYLESHEET,
    STYLESHEET,
    compose_probe_basic_theme,
    probe_basic_widget_override,
)


class ThemeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]

    def test_global_theme_is_appended_without_losing_host_theme(self) -> None:
        original = "QWidget { color: silver; }"
        composed = compose_probe_basic_theme(original)
        self.assertTrue(composed.startswith(original))
        self.assertIn("OPENMILL_PROBE_BASIC_THEME", composed)

    def test_global_theme_is_idempotent(self) -> None:
        once = compose_probe_basic_theme("host")
        self.assertEqual(compose_probe_basic_theme(once), once)

    def test_critical_probe_basic_controls_keep_explicit_rules(self) -> None:
        self.assertIn("QPushButton#exit_button", PROBE_BASIC_MODERN_STYLESHEET)
        self.assertIn("QPushButton#power_button:checked", PROBE_BASIC_MODERN_STYLESHEET)
        self.assertIn("#ff7383", PROBE_BASIC_MODERN_STYLESHEET)

    def test_openmill_theme_has_readable_dark_surface(self) -> None:
        self.assertIn("color: #e7edf7", STYLESHEET)
        self.assertIn("background-color: #0b101a", STYLESHEET)

    def test_local_override_beats_probe_basic_inline_style_by_object_id(self) -> None:
        style = probe_basic_widget_override({"QFrame", "QWidget"}, object_name="main_panel")
        self.assertIn("QFrame#main_panel", style)
        self.assertIn("background: #111827", style)

    def test_local_button_override_has_modern_states(self) -> None:
        style = probe_basic_widget_override({"ActionButton", "QPushButton"}, object_name="cycle_start")
        self.assertIn("QPushButton#cycle_start:checked", style)
        self.assertIn("#57d7a8", style)
        self.assertNotIn("font-family", style)
        self.assertNotIn("padding:", style)

    def test_machine_driven_styles_and_renderers_are_not_overridden(self) -> None:
        self.assertEqual(
            probe_basic_widget_override({"QPushButton"}, object_name="exit_button"), ""
        )
        self.assertEqual(
            probe_basic_widget_override({"QPushButton"}, rules='[{"property": "Style Sheet"}]'),
            "",
        )
        self.assertEqual(probe_basic_widget_override({"VTKBackPlot", "QWidget"}), "")

    def test_probe_basic_widget_requests_embedded_layout(self) -> None:
        source = ast.parse(
            (self.root / "src/openmill/integration/probe_basic.py").read_text(encoding="utf-8")
        )
        values = [
            keyword.value.value
            for node in ast.walk(source)
            if isinstance(node, ast.Call)
            for keyword in node.keywords
            if keyword.arg == "embedded" and isinstance(keyword.value, ast.Constant)
        ]
        self.assertEqual(values, [True])

    def test_user_tab_defaults_to_modern_theme_but_allows_original(self) -> None:
        source = (
            self.root / "examples/probe_basic/user_tabs/openmill/openmill.py"
        ).read_text(encoding="utf-8")
        self.assertIn('OPENMILL_THEME", "modern"', source)
        self.assertIn('"original"', source)


if __name__ == "__main__":
    unittest.main()
