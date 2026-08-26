"""Reusable compensated contour strategies for common closed geometries."""

from __future__ import annotations

from collections.abc import Callable

from openmill.core.geometry import (
    circle_points,
    depth_levels,
    regular_polygon_points,
    rounded_rectangle_points,
)
from openmill.core.models import OperationRecord, Stock, Tool, Toolpath
from openmill.core.registry import FieldSpec, OperationPlugin, registry


PROFILE_STRATEGY_FIELDS = (
    FieldSpec(
        "mode",
        "Position de l’outil",
        "outside",
        unit="",
        kind="choice",
        choices=(
            ("inside", "Intérieur · compensation outil"),
            ("on", "Sur le tracé · sans compensation"),
            ("outside", "Extérieur · compensation outil"),
        ),
        section="Stratégie",
    ),
    FieldSpec(
        "milling_direction",
        "Sens de fraisage",
        "climb",
        unit="",
        kind="choice",
        choices=(("climb", "Avalant"), ("conventional", "Opposition")),
        section="Stratégie",
    ),
    FieldSpec(
        "finish_pass",
        "Passe de finition",
        "enabled",
        unit="",
        kind="choice",
        choices=(("enabled", "Activée"), ("disabled", "Désactivée")),
        section="Finition",
    ),
    FieldSpec(
        "side_allowance",
        "Surépaisseur latérale",
        0.2,
        section="Finition",
        minimum=0,
        tip="Matière laissée pendant l’ébauche, retirée par la passe de finition.",
    ),
)


ContourFactory = Callable[[float, bool], list[tuple[float, float]]]


def _validate_strategy(parameters: dict, tool: Tool) -> tuple[str, bool, float, bool]:
    mode = str(parameters["mode"])
    direction = str(parameters["milling_direction"])
    finish_mode = str(parameters["finish_pass"])
    finish_enabled = finish_mode == "enabled"
    allowance = float(parameters["side_allowance"])
    if mode not in {"inside", "on", "outside"}:
        raise ValueError("La position de contournage est inconnue.")
    if direction not in {"climb", "conventional"}:
        raise ValueError("Le sens de fraisage est inconnu.")
    if finish_mode not in {"enabled", "disabled"}:
        raise ValueError("Le mode de finition est inconnu.")
    if allowance < 0:
        raise ValueError("La surépaisseur latérale ne peut pas être négative.")
    if mode == "on":
        allowance = 0.0
        finish_enabled = False
    if tool.diameter <= 0:
        raise ValueError("Le diamètre d’outil doit être positif.")

    # With a clockwise spindle viewed from +Z: climb is clockwise outside and
    # counter-clockwise inside.  "On the line" follows the outside convention.
    clockwise = (mode != "inside") == (direction == "climb")
    return mode, clockwise, allowance, finish_enabled


def _tool_offset(mode: str, tool_radius: float, allowance: float) -> float:
    if mode == "inside":
        return -(tool_radius + allowance)
    if mode == "outside":
        return tool_radius + allowance
    return 0.0


def _generate_profile(
    plugin: type[OperationPlugin],
    operation: OperationRecord,
    tool: Tool,
    contour_factory: ContourFactory,
) -> Toolpath:
    parameters = operation.parameters
    mode, clockwise, allowance, finish_enabled = _validate_strategy(parameters, tool)
    rough_contour = contour_factory(_tool_offset(mode, tool.diameter / 2, allowance), clockwise)
    levels = depth_levels(
        float(parameters["z_start"]),
        float(parameters["z_final"]),
        float(parameters["step_down"]),
    )
    builder = plugin.builder(operation, tool)
    for level in levels:
        builder.rapid(*rough_contour[0])
        builder.plunge(level)
        builder.follow(rough_contour)
        builder.retract()

    if finish_enabled and allowance > 1e-9:
        finish_contour = contour_factory(_tool_offset(mode, tool.diameter / 2, 0.0), clockwise)
        builder.rapid(*finish_contour[0])
        builder.plunge(levels[-1])
        builder.follow(finish_contour)
        builder.retract()
    return builder.result


@registry.register
class RectangleProfileOperation(OperationPlugin):
    id = "profile_rectangle"
    label = "Profil rectangulaire"
    category = "Profils"
    description = "Contour intérieur, extérieur ou sur tracé, avec ébauche et finition."
    fields = (
        FieldSpec("center_x", "Centre X", 60.0),
        FieldSpec("center_y", "Centre Y", 40.0),
        FieldSpec("width", "Largeur", 64.0, minimum=0.1),
        FieldSpec("height", "Hauteur", 42.0, minimum=0.1),
        FieldSpec("corner_radius", "Rayon des angles", 6.0, minimum=0),
        *PROFILE_STRATEGY_FIELDS,
    )

    @classmethod
    def generate(cls, operation: OperationRecord, stock: Stock, tool: Tool) -> Toolpath:
        parameters = operation.parameters
        width, height = float(parameters["width"]), float(parameters["height"])
        requested_radius = float(parameters["corner_radius"])
        if min(width, height) <= 0:
            raise ValueError("Les dimensions du profil doivent être positives.")
        if not 0 <= requested_radius <= min(width, height) / 2:
            raise ValueError("Le rayon d’angle dépasse la moitié de la plus petite dimension.")

        def contour(offset: float, clockwise: bool) -> list[tuple[float, float]]:
            compensated_width = width + offset * 2
            compensated_height = height + offset * 2
            if min(compensated_width, compensated_height) <= 0:
                raise ValueError(
                    f"Le profil intérieur est trop petit pour l’outil Ø {tool.diameter:g} mm."
                )
            points = rounded_rectangle_points(
                float(parameters["center_x"]),
                float(parameters["center_y"]),
                compensated_width,
                compensated_height,
                max(0.0, requested_radius + offset),
            )
            return list(reversed(points)) if clockwise else points

        result = _generate_profile(cls, operation, tool, contour)
        if parameters["mode"] == "inside" and requested_radius < tool.diameter / 2:
            result.warnings.append(
                "Le rayon intérieur réel sera au minimum "
                f"{tool.diameter / 2:g} mm avec cet outil."
            )
        return result


@registry.register
class CircleProfileOperation(OperationPlugin):
    id = "profile_circle"
    label = "Profil circulaire"
    category = "Profils"
    description = "Alésage, détourage ou trajectoire circulaire avec passe de finition."
    fields = (
        FieldSpec("center_x", "Centre X", 60.0),
        FieldSpec("center_y", "Centre Y", 40.0),
        FieldSpec("diameter", "Diamètre", 46.0, minimum=0.1),
        *PROFILE_STRATEGY_FIELDS,
    )

    @classmethod
    def generate(cls, operation: OperationRecord, stock: Stock, tool: Tool) -> Toolpath:
        parameters = operation.parameters
        diameter = float(parameters["diameter"])
        if diameter <= 0:
            raise ValueError("Le diamètre du profil doit être positif.")

        def contour(offset: float, clockwise: bool) -> list[tuple[float, float]]:
            radius = diameter / 2 + offset
            if radius <= 0:
                raise ValueError(
                    f"Le profil intérieur est trop petit pour l’outil Ø {tool.diameter:g} mm."
                )
            return circle_points(
                float(parameters["center_x"]),
                float(parameters["center_y"]),
                radius,
                segments=72,
                clockwise=clockwise,
            )

        return _generate_profile(cls, operation, tool, contour)


@registry.register
class PolygonProfileOperation(OperationPlugin):
    id = "profile_polygon"
    label = "Polygone régulier"
    category = "Profils"
    description = "Profil de 3 à 24 côtés coté sur plats, intérieur ou extérieur."
    fields = (
        FieldSpec("center_x", "Centre X", 60.0),
        FieldSpec("center_y", "Centre Y", 40.0),
        FieldSpec("sides", "Nombre de côtés", 6, unit="", minimum=3, maximum=24, kind="int"),
        FieldSpec("across_flats", "Cote sur plats", 34.0, minimum=0.1),
        FieldSpec("rotation", "Orientation", 0.0, unit="°", minimum=-360, maximum=360),
        *PROFILE_STRATEGY_FIELDS,
    )

    @classmethod
    def generate(cls, operation: OperationRecord, stock: Stock, tool: Tool) -> Toolpath:
        parameters = operation.parameters
        sides = int(parameters["sides"])
        across_flats = float(parameters["across_flats"])
        if not 3 <= sides <= 24:
            raise ValueError("Le polygone doit comporter entre 3 et 24 côtés.")
        if across_flats <= 0:
            raise ValueError("La cote sur plats doit être positive.")

        def contour(offset: float, clockwise: bool) -> list[tuple[float, float]]:
            apothem = across_flats / 2 + offset
            if apothem <= 0:
                raise ValueError(
                    f"Le profil intérieur est trop petit pour l’outil Ø {tool.diameter:g} mm."
                )
            points = regular_polygon_points(
                float(parameters["center_x"]),
                float(parameters["center_y"]),
                apothem,
                sides=sides,
                rotation_degrees=float(parameters["rotation"]),
            )
            return list(reversed(points)) if clockwise else points

        result = _generate_profile(cls, operation, tool, contour)
        if parameters["mode"] == "inside":
            result.warnings.append(
                "Les angles intérieurs conserveront un rayon lié au diamètre de la fraise."
            )
        return result
