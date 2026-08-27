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
        feed: float | None = None,
    ) -> None:
        target = Point(
            self.position.x if x is None else float(x),
            self.position.y if y is None else float(y),
            self.position.z if z is None else float(z),
        )
        if target.distance_to(self.position) <= 1e-9:
            return
        default_feed = (
            None
            if kind in {MotionKind.RAPID, MotionKind.DWELL}
            else self.feed_z
            if kind in {MotionKind.PLUNGE, MotionKind.TAP, MotionKind.TAP_RETURN}
            else self.feed_xy
        )
        self.result.motions.append(Motion(self.position, target, kind, default_feed if feed is None else feed))
        self.position = target

    def rapid(self, x: float, y: float, z: float | None = None) -> None:
        if self.position.z < self.clearance - 1e-9:
            self.move(z=self.clearance, kind=MotionKind.RAPID)
        self.move(x=x, y=y, z=self.clearance if z is None else z, kind=MotionKind.RAPID)

    def plunge(self, z: float) -> None:
        self.move(z=z, kind=MotionKind.PLUNGE)

    def cut(self, x: float, y: float, z: float | None = None) -> None:
        self.move(x=x, y=y, z=z, kind=MotionKind.CUT)

    def feed_to_z(self, z: float, feed: float) -> None:
        if feed <= 0:
            raise ValueError("L’avance doit être supérieure à zéro.")
        self.move(z=z, kind=MotionKind.PLUNGE, feed=feed)

    def dwell(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("La temporisation ne peut pas être négative.")
        if seconds > 0:
            self.result.motions.append(
                Motion(
                    self.position,
                    self.position,
                    MotionKind.DWELL,
                    dwell_seconds=float(seconds),
                )
            )

    def tap(self, z: float, pitch: float, spindle_rpm: int) -> None:
        if pitch <= 0:
            raise ValueError("Le pas de taraudage doit être supérieur à zéro.")
        target = Point(self.position.x, self.position.y, float(z))
        start = self.position
        self.result.motions.append(
            Motion(
                start,
                target,
                MotionKind.TAP,
                feed=float(pitch) * int(spindle_rpm),
                thread_pitch=float(pitch),
            )
        )
        self.result.motions.append(
            Motion(
                target,
                start,
                MotionKind.TAP_RETURN,
                feed=float(pitch) * int(spindle_rpm),
                thread_pitch=float(pitch),
            )
        )
        self.position = start

    def follow(self, points: list[tuple[float, float]]) -> None:
        for x, y in points:
            self.cut(x, y)

    def retract(self) -> None:
        self.move(z=self.clearance, kind=MotionKind.RAPID)
