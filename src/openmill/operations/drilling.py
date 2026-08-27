"""Circular and rectangular drilling arrays."""

from __future__ import annotations

import math

from openmill.core.geometry import depth_levels, rotate_point
from openmill.core.models import OperationRecord, Stock, Tool, Toolpath
from openmill.core.registry import FieldSpec, OperationPlugin, registry


def _drill_points(
    plugin: type[OperationPlugin],
    operation: OperationRecord,
    tool: Tool,
    positions: list[tuple[float, float]],
) -> Toolpath:
    params = operation.parameters
    start, final = float(params["z_start"]), float(params["z_final"])
    if final >= start:
        raise ValueError("La profondeur finale doit être inférieure au Z de départ.")
    peck = float(params["peck"])
    if peck < 0:
        raise ValueError("Le débourrage ne peut pas être négatif.")
    levels = depth_levels(start, final, peck) if peck > 0 else [final]
    builder = plugin.builder(operation, tool)

    for x, y in positions:
        for level in levels:
            builder.rapid(x, y)
            builder.plunge(level)
            builder.retract()
    return builder.result


@registry.register
class CircularDrillPatternOperation(OperationPlugin):
    id = "drill_circle"
    label = "Perçages sur cercle"
    category = "Perçage"
    description = "Répartition angulaire régulière sur un cercle primitif."
    picker_visible = False
    fields = (
        FieldSpec("center_x", "Centre X", 60.0),
        FieldSpec("center_y", "Centre Y", 40.0),
        FieldSpec("diameter", "Diamètre de répartition", 60.0, minimum=0),
        FieldSpec("hole_count", "Nombre de perçages", 6, unit="", minimum=1, maximum=200, kind="int"),
        FieldSpec("start_angle", "Angle de départ", 0.0, unit="°", minimum=-360, maximum=360),
        FieldSpec("sweep", "Angle de répartition", 360.0, unit="°", minimum=0.1, maximum=360),
        FieldSpec("peck", "Débourrage · 0 = aucun", 0.0, section="Profondeurs", minimum=0),
    )

    @classmethod
    def generate(cls, operation: OperationRecord, stock: Stock, tool: Tool) -> Toolpath:
        params = operation.parameters
        count = int(params["hole_count"])
        if count < 1:
            raise ValueError("Le réseau doit comporter au moins un perçage.")
        diameter = float(params["diameter"])
        if diameter < 0:
            raise ValueError("Le diamètre de répartition ne peut pas être négatif.")
        sweep = float(params["sweep"])
        if not 0 < sweep <= 360:
            raise ValueError("L’angle de répartition doit être compris entre 0 et 360°.")
        divisor = count if math.isclose(sweep, 360.0) else max(count - 1, 1)
        center_x, center_y = float(params["center_x"]), float(params["center_y"])
        radius = diameter / 2
        positions = []
        for index in range(count):
            angle = math.radians(float(params["start_angle"]) + sweep * index / divisor)
            positions.append((center_x + radius * math.cos(angle), center_y + radius * math.sin(angle)))
        return _drill_points(cls, operation, tool, positions)


@registry.register
class RectangularDrillPatternOperation(OperationPlugin):
    id = "drill_grid"
    label = "Perçages en grille"
    category = "Perçage"
    description = "Réseau rectangulaire centré, orientable et en zigzag."
    picker_visible = False
    fields = (
        FieldSpec("center_x", "Centre X", 60.0),
        FieldSpec("center_y", "Centre Y", 40.0),
        FieldSpec("columns", "Colonnes", 4, unit="", minimum=1, maximum=100, kind="int"),
        FieldSpec("rows", "Rangées", 3, unit="", minimum=1, maximum=100, kind="int"),
        FieldSpec("spacing_x", "Espacement X", 20.0, minimum=0),
        FieldSpec("spacing_y", "Espacement Y", 18.0, minimum=0),
        FieldSpec("rotation", "Orientation", 0.0, unit="°", minimum=-360, maximum=360),
        FieldSpec("peck", "Débourrage · 0 = aucun", 0.0, section="Profondeurs", minimum=0),
    )

    @classmethod
    def generate(cls, operation: OperationRecord, stock: Stock, tool: Tool) -> Toolpath:
        params = operation.parameters
        columns, rows = int(params["columns"]), int(params["rows"])
        if min(columns, rows) < 1:
            raise ValueError("La grille doit comporter au moins une colonne et une rangée.")
        if min(float(params["spacing_x"]), float(params["spacing_y"])) < 0:
            raise ValueError("L’espacement entre les perçages ne peut pas être négatif.")
        center_x, center_y = float(params["center_x"]), float(params["center_y"])
        positions: list[tuple[float, float]] = []
        for row in range(rows):
            indexes = range(columns) if row % 2 == 0 else range(columns - 1, -1, -1)
            for column in indexes:
                x = (column - (columns - 1) / 2) * float(params["spacing_x"])
                y = (row - (rows - 1) / 2) * float(params["spacing_y"])
                rotated_x, rotated_y = rotate_point(x, y, float(params["rotation"]))
                positions.append((center_x + rotated_x, center_y + rotated_y))
        return _drill_points(cls, operation, tool, positions)
