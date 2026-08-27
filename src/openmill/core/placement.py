"""Generic Cartesian and polar placement of conversational operations."""

from __future__ import annotations

from dataclasses import dataclass
import math

from openmill.core.models import (
    Motion,
    MotionKind,
    OperationRecord,
    PlacementMode,
    Point,
    Stock,
    Toolpath,
)


@dataclass(frozen=True, slots=True)
class PlacementInstance:
    """One call position and local orientation of an operation."""

    x: float
    y: float
    angle: float = 0.0


def operation_anchor(operation: OperationRecord, stock: Stock) -> tuple[float, float]:
    """Return the natural reference point used to relocate an operation."""

    parameters = operation.parameters
    return (
        float(parameters.get("center_x", stock.center_x)),
        float(parameters.get("center_y", stock.center_y)),
    )


def placement_instances(operation: OperationRecord, stock: Stock) -> list[PlacementInstance]:
    """Expand a placement definition into ordered absolute call positions."""

    placement = operation.placement
    anchor_x, anchor_y = operation_anchor(operation, stock)
    if placement.mode is PlacementMode.SINGLE:
        return [PlacementInstance(anchor_x, anchor_y)]

    if placement.mode is PlacementMode.LINEAR:
        if placement.count < 1:
            raise ValueError("Une répétition linéaire doit contenir au moins une position.")
        if placement.count > 1 and math.hypot(placement.step_x, placement.step_y) <= 1e-9:
            raise ValueError("L’incrément de la répétition linéaire ne peut pas être nul.")
        angle = (
            math.degrees(math.atan2(placement.step_y, placement.step_x))
            if placement.rotate_geometry and placement.count > 1
            else 0.0
        )
        return [
            PlacementInstance(
                placement.start_x + index * placement.step_x,
                placement.start_y + index * placement.step_y,
                angle,
            )
            for index in range(placement.count)
        ]

    if placement.mode is PlacementMode.GRID:
        if min(placement.columns, placement.rows) < 1:
            raise ValueError("Une grille doit contenir au moins une colonne et une rangée.")
        if placement.columns > 1 and abs(placement.spacing_x) <= 1e-9:
            raise ValueError("L’espacement X de la grille ne peut pas être nul.")
        if placement.rows > 1 and abs(placement.spacing_y) <= 1e-9:
            raise ValueError("L’espacement Y de la grille ne peut pas être nul.")
        radians = math.radians(placement.grid_angle)
        cosine, sine = math.cos(radians), math.sin(radians)
        orientation = placement.grid_angle if placement.rotate_geometry else 0.0
        instances: list[PlacementInstance] = []
        for row in range(placement.rows):
            columns = range(placement.columns)
            if placement.serpentine and row % 2:
                columns = range(placement.columns - 1, -1, -1)
            for column in columns:
                local_x = column * placement.spacing_x
                local_y = row * placement.spacing_y
                instances.append(
                    PlacementInstance(
                        placement.start_x + local_x * cosine - local_y * sine,
                        placement.start_y + local_x * sine + local_y * cosine,
                        orientation,
                    )
                )
        return instances

    if placement.count < 1:
        raise ValueError("Une répétition circulaire doit contenir au moins une position.")
    if placement.diameter < 0:
        raise ValueError("Le diamètre de répétition ne peut pas être négatif.")
    if placement.count > 1 and placement.diameter <= 1e-9:
        raise ValueError("Le diamètre de répétition doit être supérieur à zéro.")
    if not 0 < abs(placement.sweep) <= 360:
        raise ValueError("L’angle de répétition doit être compris entre -360° et 360°.")
    divisor = placement.count if math.isclose(abs(placement.sweep), 360.0) else max(placement.count - 1, 1)
    radius = placement.diameter / 2
    instances = []
    for index in range(placement.count):
        angle = placement.start_angle + placement.sweep * index / divisor
        radians = math.radians(angle)
        instances.append(
            PlacementInstance(
                placement.center_x + radius * math.cos(radians),
                placement.center_y + radius * math.sin(radians),
                angle if placement.rotate_geometry else 0.0,
            )
        )
    return instances


def _transform_point(
    point: Point,
    *,
    anchor_x: float,
    anchor_y: float,
    instance: PlacementInstance,
) -> Point:
    radians = math.radians(instance.angle)
    cosine, sine = math.cos(radians), math.sin(radians)
    local_x, local_y = point.x - anchor_x, point.y - anchor_y
    return Point(
        instance.x + local_x * cosine - local_y * sine,
        instance.y + local_x * sine + local_y * cosine,
        point.z,
    )


def _connector(start: Point, end: Point, clearance: float) -> list[Motion]:
    """Join repeated instances without ever traversing laterally below clearance."""

    motions: list[Motion] = []
    position = start
    safe_z = max(clearance, start.z, end.z)
    if position.z < safe_z - 1e-9:
        target = Point(position.x, position.y, safe_z)
        motions.append(Motion(position, target, MotionKind.RAPID))
        position = target
    if abs(position.x - end.x) > 1e-9 or abs(position.y - end.y) > 1e-9:
        target = Point(end.x, end.y, safe_z)
        motions.append(Motion(position, target, MotionKind.RAPID))
        position = target
    if abs(position.z - end.z) > 1e-9:
        motions.append(Motion(position, end, MotionKind.RAPID))
    return motions


def apply_placement(
    path: Toolpath,
    operation: OperationRecord,
    stock: Stock,
) -> Toolpath:
    """Return a path containing every call of the operation's pattern."""

    if operation.placement.mode is PlacementMode.SINGLE:
        path.instance_count = 1
        path.placement_summary = operation.placement.summary
        return path

    instances = placement_instances(operation, stock)
    anchor_x, anchor_y = operation_anchor(operation, stock)
    expanded = Toolpath(
        operation_uid=path.operation_uid,
        operation_title=path.operation_title,
        tool=path.tool,
        warnings=list(path.warnings),
        spindle_rpm=path.spindle_rpm,
        spindle_direction=path.spindle_direction,
        instance_count=len(instances),
        placement_summary=operation.placement.summary,
    )
    clearance = float(operation.parameters.get("clearance", 5.0))
    for instance in instances:
        transformed = [
            Motion(
                _transform_point(
                    motion.start,
                    anchor_x=anchor_x,
                    anchor_y=anchor_y,
                    instance=instance,
                ),
                _transform_point(
                    motion.end,
                    anchor_x=anchor_x,
                    anchor_y=anchor_y,
                    instance=instance,
                ),
                motion.kind,
                motion.feed,
                motion.dwell_seconds,
                motion.thread_pitch,
            )
            for motion in path.motions
        ]
        if not transformed:
            continue
        current = expanded.motions[-1].end if expanded.motions else path.motions[0].start
        first = transformed[0]
        if first.kind is MotionKind.RAPID:
            # Toolpath builders start at their own synthetic (0, 0) point.  A
            # repeated call must travel directly from the previous real call,
            # not visit a transformed copy of that synthetic origin.
            expanded.motions.extend(_connector(current, first.end, clearance))
            expanded.motions.extend(transformed[1:])
        else:
            expanded.motions.extend(_connector(current, first.start, clearance))
            expanded.motions.extend(transformed)
    return expanded


__all__ = ["PlacementInstance", "apply_placement", "operation_anchor", "placement_instances"]
