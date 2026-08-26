from __future__ import annotations

import unittest

from openmill.core.parameter_controls import (
    normalize_dial_angle,
    recommended_step,
    uses_angle_dial,
    uses_percentage_slider,
)
from openmill.core.registry import FieldSpec


class ParameterInteractionTests(unittest.TestCase):
    def test_angle_controls_increment_by_five_degrees(self) -> None:
        self.assertEqual(recommended_step(FieldSpec("rotation", "Orientation", 0, unit="°")), 5)

    def test_percentage_controls_increment_by_five(self) -> None:
        self.assertEqual(recommended_step(FieldSpec("step_over", "Engagement", 45, unit="%")), 5)

    def test_depth_controls_increment_by_tenth(self) -> None:
        self.assertEqual(recommended_step(FieldSpec("z_final", "Z final", -2)), 0.1)

    def test_spindle_controls_increment_by_250_rpm(self) -> None:
        field = FieldSpec("spindle_rpm", "Broche", 12_000, unit="tr/min", kind="int")
        self.assertEqual(recommended_step(field), 250)

    def test_signed_angle_uses_shortest_representation(self) -> None:
        self.assertEqual(normalize_dial_angle(270, -360, 360), -90)

    def test_unsigned_angle_wraps(self) -> None:
        self.assertEqual(normalize_dial_angle(450, 0, 360), 90)

    def test_complete_sweep_remains_360_degrees(self) -> None:
        self.assertEqual(normalize_dial_angle(0, 0.1, 360), 360)

    def test_invalid_angle_bounds_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            normalize_dial_angle(45, 180, 0)

    def test_degrees_select_a_dial(self) -> None:
        self.assertTrue(uses_angle_dial(FieldSpec("rotation", "Orientation", 0, unit="°", minimum=-360, maximum=360)))

    def test_percentage_selects_a_fader(self) -> None:
        self.assertTrue(uses_percentage_slider(FieldSpec("step_over", "Engagement", 45, unit="%", minimum=1, maximum=95)))

    def test_nonpercentage_does_not_select_a_fader(self) -> None:
        self.assertFalse(uses_percentage_slider(FieldSpec("width", "Largeur", 45, unit="mm")))


if __name__ == "__main__":
    unittest.main()
