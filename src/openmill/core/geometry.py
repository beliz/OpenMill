"""Small geometry helpers that do not require a GUI or LinuxCNC."""

from __future__ import annotations

import math


def depth_levels(start: float, final: float, step_down: float) -> list[float]:
    if final >= start:
        raise ValueError("La profondeur finale doit être inférieure au Z de départ.")
    if step_down <= 0:
        raise ValueError("La profondeur de passe doit être positive.")

    levels: list[float] = []
    current = start
    while current > final:
        current = max(final, current - step_down)
        levels.append(round(current, 6))
    return levels


def linear_positions(first: float, last: float, maximum_step: float) -> list[float]:
    if maximum_step <= 0:
        raise ValueError("Le recouvrement doit être supérieur à zéro.")
    if math.isclose(first, last, abs_tol=1e-9):
        return [first]
    count = max(1, math.ceil(abs(last - first) / maximum_step))
    return [first + (last - first) * index / count for index in range(count + 1)]


def circle_points(
    center_x: float,
    center_y: float,
    radius: float,
    *,
    segments: int = 64,
    clockwise: bool = False,
) -> list[tuple[float, float]]:
    if radius < 0:
        raise ValueError("Le rayon ne peut pas être négatif.")
    if radius <= 1e-9:
        return [(center_x, center_y)]
    direction = -1 if clockwise else 1
    return [
        (
            center_x + radius * math.cos(direction * math.tau * index / segments),
            center_y + radius * math.sin(direction * math.tau * index / segments),
        )
        for index in range(segments + 1)
    ]


def rounded_rectangle_points(
    center_x: float,
    center_y: float,
    width: float,
    height: float,
    corner_radius: float,
    *,
    segments_per_corner: int = 8,
) -> list[tuple[float, float]]:
    if width < 0 or height < 0:
        raise ValueError("Les dimensions du rectangle doivent être positives.")
    if width <= 1e-9 and height <= 1e-9:
        return [(center_x, center_y)]
    if width <= 1e-9:
        return [(center_x, center_y - height / 2), (center_x, center_y + height / 2)]
    if height <= 1e-9:
        return [(center_x - width / 2, center_y), (center_x + width / 2, center_y)]

    radius = max(0.0, min(corner_radius, width / 2, height / 2))
    if radius <= 1e-9:
        left, right = center_x - width / 2, center_x + width / 2
        bottom, top = center_y - height / 2, center_y + height / 2
        return [(right, bottom), (right, top), (left, top), (left, bottom), (right, bottom)]

    corners = [
        (center_x + width / 2 - radius, center_y - height / 2 + radius, -90),
        (center_x + width / 2 - radius, center_y + height / 2 - radius, 0),
        (center_x - width / 2 + radius, center_y + height / 2 - radius, 90),
        (center_x - width / 2 + radius, center_y - height / 2 + radius, 180),
    ]
    points: list[tuple[float, float]] = []
    for x, y, start_angle in corners:
        for index in range(segments_per_corner + 1):
            angle = math.radians(start_angle + 90 * index / segments_per_corner)
            points.append((x + radius * math.cos(angle), y + radius * math.sin(angle)))
    points.append(points[0])
    return points


def regular_polygon_points(
    center_x: float,
    center_y: float,
    apothem: float,
    *,
    sides: int = 6,
    rotation_degrees: float = 0.0,
) -> list[tuple[float, float]]:
    if sides < 3:
        raise ValueError("Un polygone doit avoir au moins trois côtés.")
    if apothem <= 1e-9:
        return [(center_x, center_y)]
    radius = apothem / math.cos(math.pi / sides)
    rotation = math.radians(rotation_degrees)
    points = [
        (
            center_x + radius * math.cos(rotation + math.tau * index / sides),
            center_y + radius * math.sin(rotation + math.tau * index / sides),
        )
        for index in range(sides)
    ]
    points.append(points[0])
    return points


def rotate_point(x: float, y: float, degrees: float) -> tuple[float, float]:
    angle = math.radians(degrees)
    return (
        x * math.cos(angle) - y * math.sin(angle),
        x * math.sin(angle) + y * math.cos(angle),
    )

