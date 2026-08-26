"""Rectangular and circular pocket strategies."""

from __future__ import annotations

from openmill.core.geometry import circle_points, depth_levels, linear_positions, rounded_rectangle_points
from openmill.core.models import OperationRecord, Stock, Tool, Toolpath
from openmill.core.registry import FieldSpec, OperationPlugin, registry


@registry.register
class RectanglePocketOperation(OperationPlugin):
    id = "pocket_rectangle"
    label = "Poche rectangulaire"
    category = "Poches"
    description = "Contours concentriques compensés du rayon de l’outil."
    fields = (
        FieldSpec("center_x", "Centre X", 60.0),
        FieldSpec("center_y", "Centre Y", 40.0),
        FieldSpec("width", "Largeur", 64.0, minimum=0.1),
        FieldSpec("height", "Hauteur", 42.0, minimum=0.1),
        FieldSpec("corner_radius", "Rayon des angles", 6.0, minimum=0),
        FieldSpec("step_over", "Engagement latéral", 45.0, unit="%", minimum=1, maximum=95),
    )

    @classmethod
    def generate(cls, operation: OperationRecord, stock: Stock, tool: Tool) -> Toolpath:
        params = operation.parameters
        width, height = float(params["width"]), float(params["height"])
        if min(width, height) < tool.diameter:
            raise ValueError(f"La poche est trop étroite pour l’outil Ø {tool.diameter:g} mm.")
        requested_radius = float(params["corner_radius"])
        if requested_radius > min(width, height) / 2:
            raise ValueError("Le rayon d’angle dépasse la moitié de la plus petite dimension.")
        if not 0 < float(params["step_over"]) <= 100:
            raise ValueError("L’engagement latéral doit être compris entre 0 et 100 %.")

        center_x, center_y = float(params["center_x"]), float(params["center_y"])
        center_width, center_height = width - tool.diameter, height - tool.diameter
        center_radius = max(requested_radius - tool.diameter / 2, 0.0)
        maximum_inset = min(center_width, center_height) / 2
        insets = linear_positions(0.0, maximum_inset, tool.diameter * float(params["step_over"]) / 100)
        levels = depth_levels(float(params["z_start"]), float(params["z_final"]), float(params["step_down"]))
        contours = [
            rounded_rectangle_points(
                center_x,
                center_y,
                max(center_width - inset * 2, 0.0),
                max(center_height - inset * 2, 0.0),
                max(center_radius - inset, 0.0),
            )
            for inset in insets
        ]
        builder = cls.builder(operation, tool)
        if requested_radius < tool.diameter / 2:
            builder.result.warnings.append(
                f"Le rayon d’angle réel sera au minimum {tool.diameter / 2:g} mm avec cet outil."
            )

        for level in levels:
            builder.rapid(*contours[0][0])
            builder.plunge(level)
            for contour in contours:
                builder.follow(contour)
            builder.retract()
        return builder.result


@registry.register
class CirclePocketOperation(OperationPlugin):
    id = "pocket_circle"
    label = "Poche circulaire"
    category = "Poches"
    description = "Cercles concentriques jusqu’au centre de la poche."
    fields = (
        FieldSpec("center_x", "Centre X", 60.0),
        FieldSpec("center_y", "Centre Y", 40.0),
        FieldSpec("diameter", "Diamètre de poche", 46.0, minimum=0.1),
        FieldSpec("step_over", "Engagement latéral", 45.0, unit="%", minimum=1, maximum=95),
    )

    @classmethod
    def generate(cls, operation: OperationRecord, stock: Stock, tool: Tool) -> Toolpath:
        params = operation.parameters
        diameter = float(params["diameter"])
        if diameter < tool.diameter:
            raise ValueError(f"Le diamètre de poche doit être au moins égal à Ø {tool.diameter:g} mm.")
        if not 0 < float(params["step_over"]) <= 100:
            raise ValueError("L’engagement latéral doit être compris entre 0 et 100 %.")

        center_x, center_y = float(params["center_x"]), float(params["center_y"])
        outer_radius = (diameter - tool.diameter) / 2
        radii = linear_positions(outer_radius, 0.0, tool.diameter * float(params["step_over"]) / 100)
        levels = depth_levels(float(params["z_start"]), float(params["z_final"]), float(params["step_down"]))
        builder = cls.builder(operation, tool)

        for level in levels:
            first = circle_points(center_x, center_y, radii[0], segments=48)
            builder.rapid(*first[0])
            builder.plunge(level)
            for radius in radii:
                builder.follow(circle_points(center_x, center_y, radius, segments=48))
            builder.retract()
        return builder.result
