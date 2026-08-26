"""Helpers for assembling safe, explicit tool-center motions."""

from __future__ import annotations

from openmill.core.models import Motion, MotionKind, Point, Tool, Toolpath


class ToolpathBuilder:
    def __init__(
        self,
        *,
        operation_uid: str,
        operation_title: str,
        tool: Tool,
        clearance: float,
        feed_xy: float,
        feed_z: float,
        spindle_rpm: int,
    ) -> None:
        if clearance <= 0:
            raise ValueError("La hauteur de sécurité doit être supérieure à zéro.")
        if min(feed_xy, feed_z) <= 0:
            raise ValueError("Les avances doivent être positives.")
        self.position = Point(0.0, 0.0, clearance)
        self.clearance = clearance
        self.feed_xy = feed_xy
        self.feed_z = feed_z
        self.result = Toolpath(
            operation_uid=operation_uid,
            operation_title=operation_title,
            tool=tool,
            spindle_rpm=spindle_rpm,
        )

    def move(
        self,
        *,
        x: float | None = None,
        y: float | None = None,
        z: float | None = None,
        kind: MotionKind,
    ) -> None:
        target = Point(
            self.position.x if x is None else float(x),
            self.position.y if y is None else float(y),
            self.position.z if z is None else float(z),
        )
        if target.distance_to(self.position) <= 1e-9:
            return
        feed = None if kind is MotionKind.RAPID else self.feed_z if kind is MotionKind.PLUNGE else self.feed_xy
        self.result.motions.append(Motion(self.position, target, kind, feed))
        self.position = target

    def rapid(self, x: float, y: float, z: float | None = None) -> None:
        if self.position.z < self.clearance - 1e-9:
            self.move(z=self.clearance, kind=MotionKind.RAPID)
        self.move(x=x, y=y, z=self.clearance if z is None else z, kind=MotionKind.RAPID)

    def plunge(self, z: float) -> None:
        self.move(z=z, kind=MotionKind.PLUNGE)

    def cut(self, x: float, y: float, z: float | None = None) -> None:
        self.move(x=x, y=y, z=z, kind=MotionKind.CUT)

    def follow(self, points: list[tuple[float, float]]) -> None:
        for x, y in points:
            self.cut(x, y)

    def retract(self) -> None:
        self.move(z=self.clearance, kind=MotionKind.RAPID)

