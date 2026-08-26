"""Internal pocket and external contour for a regular hexagon."""

from __future__ import annotations

from openmill.core.geometry import depth_levels, linear_positions, regular_polygon_points
from openmill.core.models import OperationRecord, Stock, Tool, Toolpath
from openmill.core.registry import FieldSpec, OperationPlugin, registry


@registry.register
class HexagonOperation(OperationPlugin):
    id = "hexagon"
    label = "Hexagone intérieur / extérieur"
    category = "Profils"
    description = "Cote sur plats, rotation et compensation du diamètre d’outil."
    fields = (
        FieldSpec(
            "mode",
            "Type d’usinage",
            "interior",
            unit="",
            kind="choice",
            choices=(("interior", "Intérieur · poche"), ("exterior", "Extérieur · contour")),
        ),
        FieldSpec("center_x", "Centre X", 60.0),
        FieldSpec("center_y", "Centre Y", 40.0),
        FieldSpec("across_flats", "Cote sur plats", 34.0, minimum=0.1),
        FieldSpec("rotation", "Orientation", 0.0, unit="°", minimum=-360, maximum=360),
        FieldSpec("step_over", "Engagement latéral", 45.0, unit="%", minimum=1, maximum=95),
    )

    @classmethod
    def generate(cls, operation: OperationRecord, stock: Stock, tool: Tool) -> Toolpath:
        params = operation.parameters
        mode = params["mode"]
        if mode not in {"interior", "exterior"}:
            raise ValueError("Le mode d’usinage hexagonal est inconnu.")
        if not 0 < float(params["step_over"]) <= 100:
            raise ValueError("L’engagement latéral doit être compris entre 0 et 100 %.")
        requested_apothem = float(params["across_flats"]) / 2
        if requested_apothem <= 0:
            raise ValueError("La cote sur plats doit être positive.")
        tool_radius = tool.diameter / 2
        center_apothem = requested_apothem - tool_radius if mode == "interior" else requested_apothem + tool_radius
        if center_apothem < 0:
            raise ValueError(f"L’hexagone intérieur est trop petit pour l’outil Ø {tool.diameter:g} mm.")

        apothems = (
            linear_positions(center_apothem, 0.0, tool.diameter * float(params["step_over"]) / 100)
            if mode == "interior"
            else [center_apothem]
        )
        center_x, center_y = float(params["center_x"]), float(params["center_y"])
        contours = [
            regular_polygon_points(
                center_x,
                center_y,
                apothem,
                sides=6,
                rotation_degrees=float(params["rotation"]),
            )
            for apothem in apothems
        ]
        levels = depth_levels(float(params["z_start"]), float(params["z_final"]), float(params["step_down"]))
        builder = cls.builder(operation, tool)
        if mode == "interior":
            builder.result.warnings.append(
                "Les angles intérieurs conserveront un rayon lié au diamètre de la fraise."
            )

        for level in levels:
            builder.rapid(*contours[0][0])
            builder.plunge(level)
            for contour in contours:
                builder.follow(contour)
            builder.retract()
        return builder.result
