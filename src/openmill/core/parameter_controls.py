"""Portable interaction rules shared by touch-friendly parameter widgets."""

from __future__ import annotations

import ast
import math
from collections.abc import Mapping

from openmill.core.registry import FieldSpec


class NumericExpressionError(ValueError):
    """Raised when a parameter expression is unsafe or cannot be evaluated."""


def machining_formula_variables(
    *,
    stock_x: float,
    stock_y: float,
    tool_diam: float | None = None,
) -> dict[str, float]:
    """Return the stable variables exposed by every conversational formula field.

    English names are canonical.  The French stock aliases remain accepted so
    existing workshop habits do not turn into opaque formula errors.
    """

    variables = {
        "stock_x": float(stock_x),
        "stock_y": float(stock_y),
        "brut_x": float(stock_x),
        "brut_y": float(stock_y),
    }
    if tool_diam is not None:
        variables["tool_diam"] = float(tool_diam)
    return variables


def evaluate_numeric_expression(
    expression: str,
    variables: Mapping[str, float] | None = None,
) -> float:
    """Evaluate a small arithmetic expression without executing Python code.

    Decimal commas are accepted for French shop-floor input.  Only numeric
    literals, named numeric variables, parentheses and the four basic
    operators are supported.
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

    named_values = dict(variables or {})

    def calculate(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return calculate(node.body)
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, int | float)
            and not isinstance(node.value, bool)
        ):
            return float(node.value)
        if isinstance(node, ast.Name):
            if node.id not in named_values:
                raise NumericExpressionError(f"Variable inconnue : {node.id}.")
            try:
                value = float(named_values[node.id])
            except (TypeError, ValueError) as error:
                raise NumericExpressionError(
                    f"La variable {node.id} ne contient pas un nombre."
                ) from error
            if not math.isfinite(value):
                raise NumericExpressionError(
                    f"La variable {node.id} ne contient pas un nombre valide."
                )
            return value
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
            "Utilise uniquement des nombres, des variables autorisées, +, -, *, / "
            "et des parenthèses."
        )

    result = calculate(tree)
    if not math.isfinite(result):
        raise NumericExpressionError("Le résultat du calcul n’est pas un nombre valide.")
    return result


def is_calculation_expression(expression: str) -> bool:
    """Return whether an accepted expression should be kept as a formula."""

    try:
        tree = ast.parse(expression.strip().replace(",", "."), mode="eval")
    except (SyntaxError, ValueError):
        return False
    return any(isinstance(node, ast.BinOp | ast.Name) for node in ast.walk(tree))


def evaluate_field_expression(
    specification: FieldSpec,
    expression: str,
    variables: Mapping[str, float] | None = None,
):
    """Evaluate and normalize an expression according to a field contract."""

    result = evaluate_numeric_expression(expression, variables)
    if not specification.minimum <= result <= specification.maximum:
        raise NumericExpressionError(
            f"Le résultat doit être compris entre {specification.minimum:g} "
            f"et {specification.maximum:g}."
        )
    if specification.kind == "int":
        if not math.isclose(result, round(result), abs_tol=1e-9):
            raise NumericExpressionError("Ce champ attend un nombre entier.")
        return int(round(result))
    return round(result, specification.decimals)


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
