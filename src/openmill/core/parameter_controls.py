"""Portable interaction rules shared by touch-friendly parameter widgets."""

from __future__ import annotations

import ast
import math

from openmill.core.registry import FieldSpec


class NumericExpressionError(ValueError):
    """Raised when a parameter expression is unsafe or cannot be evaluated."""


def evaluate_numeric_expression(expression: str) -> float:
    """Evaluate a small arithmetic expression without executing Python code.

    Decimal commas are accepted for French shop-floor input.  Only numeric
    literals, parentheses and the four basic operators are supported.
    """

    source = expression.strip().replace(",", ".")
    if not source:
        raise NumericExpressionError("Saisis une valeur ou un calcul.")
    if len(source) > 128:
        raise NumericExpressionError("Le calcul est trop long.")
    try:
        tree = ast.parse(source, mode="eval")
    except (SyntaxError, ValueError) as error:
        raise NumericExpressionError("Calcul incomplet ou invalide.") from error
    if sum(1 for _node in ast.walk(tree)) > 64:
        raise NumericExpressionError("Le calcul est trop complexe.")

    def calculate(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return calculate(node.body)
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, int | float)
            and not isinstance(node.value, bool)
        ):
            return float(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd | ast.USub):
            value = calculate(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and isinstance(
            node.op, ast.Add | ast.Sub | ast.Mult | ast.Div
        ):
            left = calculate(node.left)
            right = calculate(node.right)
            try:
                if isinstance(node.op, ast.Add):
                    value = left + right
                elif isinstance(node.op, ast.Sub):
                    value = left - right
                elif isinstance(node.op, ast.Mult):
                    value = left * right
                else:
                    value = left / right
            except ZeroDivisionError as error:
                raise NumericExpressionError("La division par zéro est impossible.") from error
            if not math.isfinite(value):
                raise NumericExpressionError("Le résultat du calcul est trop grand.")
            return value
        raise NumericExpressionError(
            "Utilise uniquement des nombres, +, -, *, / et des parenthèses."
        )

    result = calculate(tree)
    if not math.isfinite(result):
        raise NumericExpressionError("Le résultat du calcul n’est pas un nombre valide.")
    return result


def is_calculation_expression(expression: str) -> bool:
    """Return whether an accepted expression contains a binary calculation."""

    try:
        tree = ast.parse(expression.strip().replace(",", "."), mode="eval")
    except (SyntaxError, ValueError):
        return False
    return any(isinstance(node, ast.BinOp) for node in ast.walk(tree))


def recommended_step(specification: FieldSpec) -> float:
    if specification.kind == "int":
        if specification.key == "spindle_rpm":
            return 250
        return 1
    if specification.unit == "°":
        return 5
    if specification.unit == "%":
        return 5
    if specification.unit == "mm/min":
        return 25
    if specification.key in {"z_start", "z_final", "step_down", "peck"}:
        return 0.1
    return 1


def normalize_dial_angle(angle: float, minimum: float, maximum: float) -> float:
    if minimum > maximum:
        raise ValueError("La plage angulaire est invalide.")
    normalized = angle % 360
    if minimum < 0:
        normalized = (normalized + 180) % 360 - 180
    elif normalized == 0 and minimum > 0 and maximum >= 360:
        normalized = 360
    return min(maximum, max(minimum, normalized))


def uses_angle_dial(specification: FieldSpec) -> bool:
    return specification.unit == "°" and specification.maximum - specification.minimum >= 90


def uses_percentage_slider(specification: FieldSpec) -> bool:
    return specification.unit == "%" and 0 <= specification.minimum < specification.maximum <= 100
