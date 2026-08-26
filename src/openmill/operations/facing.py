"""Boustrophedon facing with configurable engagement."""

from __future__ import annotations

from typing import Any

from openmill.core.geometry import depth_levels, linear_positions
from openmill.core.models import OperationRecord, Stock, Tool, Toolpath
from openmill.core.registry import FieldSpec, OperationPlugin, registry


@registry.register
class FacingOperation(OperationPlugin):
    id = "facing"
    label = "Surfaçage"
    category = "Préparation"
    description = "Balayage alterné avec dépassement adapté au diamètre d’outil."
    fields = (
        FieldSpec("center_x", "Centre X", 60.0),
        FieldSpec("center_y", "Centre Y", 40.0),
        FieldSpec("width", "Largeur à surfacer", 120.0, minimum=0.1),
        FieldSpec("height", "Hauteur à surfacer", 80.0, minimum=0.1),
        FieldSpec("step_over", "Engagement latéral", 65.0, unit="%", minimum=1, maximum=95),
    )

    @classmethod
    def defaults(cls, stock: Stock | None = None) -> dict[str, Any]:
        values = super().defaults(stock)
        if stock is not None:
            values.update(width=stock.width, height=stock.height, z_final=-0.5, step_down=0.5)
        return values

    @classmethod
    def generate(cls, operation: OperationRecord, stock: Stock, tool: Tool) -> Toolpath:
        params = operation.parameters
        width, height = float(params["width"]), float(params["height"])
        if min(width, height) <= 0:
            raise ValueError("Les dimensions à surfacer doivent être positives.")
        if not 0 < float(params["step_over"]) <= 100:
            raise ValueError("L’engagement latéral doit être compris entre 0 et 100 %.")

        center_x, center_y = float(params["center_x"]), float(params["center_y"])
        radius = tool.diameter / 2
        left = center_x - width / 2 - radius
        right = center_x + width / 2 + radius
        bottom = center_y - height / 2 + min(radius, height / 2)
        top = center_y + height / 2 - min(radius, height / 2)
        rows = linear_positions(bottom, top, tool.diameter * float(params["step_over"]) / 100)
        levels = depth_levels(float(params["z_start"]), float(params["z_final"]), float(params["step_down"]))
        builder = cls.builder(operation, tool)

        for level in levels:
            builder.rapid(left, rows[0])
            builder.plunge(level)
            for index, row in enumerate(rows):
                start_x, end_x = (left, right) if index % 2 == 0 else (right, left)
                builder.cut(start_x, row)
                builder.cut(end_x, row)
            builder.retract()
        return builder.result
