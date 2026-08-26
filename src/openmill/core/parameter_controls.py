"""Portable interaction rules shared by touch-friendly parameter widgets."""

from __future__ import annotations

from openmill.core.registry import FieldSpec


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
