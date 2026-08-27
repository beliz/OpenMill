from __future__ import annotations

import unittest

from openmill.core.parameter_controls import (
    NumericExpressionError,
    evaluate_field_expression,
    evaluate_numeric_expression,
    is_calculation_expression,
    normalize_dial_angle,
    recommended_step,
    uses_angle_dial,
    uses_percentage_slider,
)
from openmill.core.registry import FieldSpec


class ParameterInteractionTests(unittest.TestCase):
    def test_basic_arithmetic_expressions_are_evaluated(self) -> None:
        self.assertEqual(evaluate_numeric_expression("120/2"), 60)
        self.assertEqual(evaluate_numeric_expression("40+5"), 45)
        self.assertEqual(evaluate_numeric_expression("12*3"), 36)
        self.assertEqual(evaluate_numeric_expression("(20-5)*2"), 30)

    def test_decimal_comma_is_accepted(self) -> None:
        self.assertEqual(evaluate_numeric_expression("12,5/2"), 6.25)

    def test_tool_diameter_can_be_used_in_a_formula(self) -> None:
        self.assertEqual(
            evaluate_numeric_expression("5+tool_diam/2", {"tool_diam": 20}),
            15,
        )

    def test_tool_diameter_formula_is_normalized_for_the_field(self) -> None:
        specification = FieldSpec("offset", "Décalage", 0.0, decimals=2)
        self.assertEqual(
            evaluate_field_expression(
                specification,
                "5+tool_diam/3",
                {"tool_diam": 20},
            ),
            11.67,
        )

    def test_formula_detection_distinguishes_values_from_calculations(self) -> None:
        self.assertTrue(is_calculation_expression("120/2"))
        self.assertTrue(is_calculation_expression("tool_diam"))
        self.assertFalse(is_calculation_expression("-60"))

    def test_division_by_zero_is_rejected(self) -> None:
        with self.assertRaises(NumericExpressionError):
            evaluate_numeric_expression("120/0")

    def test_python_code_and_unsupported_operators_are_rejected(self) -> None:
        for expression in ("__import__('os')", "2**8", "10%3", "value+1"):
            with self.subTest(expression=expression), self.assertRaises(NumericExpressionError):
                evaluate_numeric_expression(expression)

    def test_unknown_variables_are_rejected(self) -> None:
        with self.assertRaisesRegex(NumericExpressionError, "Variable inconnue"):
            evaluate_numeric_expression("tool_diam/2")

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
