"""GUI-independent orbit projection used by the compatible 3D renderer."""

from __future__ import annotations

from dataclasses import dataclass
import math

from openmill.core.models import Point, Stock


@dataclass(slots=True)
class OrbitProjection:
    """Orthographic orbit camera, intentionally independent of Qt and OpenGL."""

    center_x: float
    center_y: float
    center_z: float
    yaw: float = -38.0
    pitch: float = 29.0
    zoom: float = 1.0

    @classmethod
    def from_stock(cls, stock: Stock) -> OrbitProjection:
        return cls(stock.center_x, stock.center_y, -stock.thickness / 2)

    def project(self, point: Point) -> tuple[float, float]:
        x = point.x - self.center_x
        y = point.y - self.center_y
        z = point.z - self.center_z
        yaw = math.radians(self.yaw)
        pitch = math.radians(self.pitch)
        horizontal = math.cos(yaw) * x - math.sin(yaw) * y
        forward = math.sin(yaw) * x + math.cos(yaw) * y
        vertical = math.cos(pitch) * z - math.sin(pitch) * forward
        return horizontal, vertical

    def depth(self, point: Point) -> float:
        x = point.x - self.center_x
        y = point.y - self.center_y
        z = point.z - self.center_z
        yaw = math.radians(self.yaw)
        pitch = math.radians(self.pitch)
        forward = math.sin(yaw) * x + math.cos(yaw) * y
        return math.cos(pitch) * forward + math.sin(pitch) * z

    def orbit(self, delta_yaw: float, delta_pitch: float) -> None:
        self.yaw = (self.yaw + delta_yaw + 180) % 360 - 180
        self.pitch = max(-82.0, min(82.0, self.pitch + delta_pitch))

    def magnify(self, factor: float) -> None:
        if factor <= 0:
            raise ValueError("Le facteur de zoom doit être positif.")
        self.zoom = max(0.25, min(5.0, self.zoom * factor))


def stock_corners(stock: Stock) -> tuple[Point, ...]:
    return tuple(
        Point(x, y, z)
        for z in (stock.z_min, stock.z_max)
        for y in (stock.y_min, stock.y_max)
        for x in (stock.x_min, stock.x_max)
    )
