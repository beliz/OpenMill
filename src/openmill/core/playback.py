"""Renderer-independent playback timeline reusable by conversational and G-code views."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass

from openmill.core.engine import BuildResult
from openmill.core.models import Motion, MotionKind, Point, Tool, Toolpath


@dataclass(frozen=True, slots=True)
class PlaybackFrame:
    result: BuildResult
    progress: float
    tool_position: Point | None
    active_tool: Tool | None
    active_operation_uid: str | None
    motion_count: int
    total_motion_count: int


class ToolpathPlayback:
    """Produce partially traced toolpaths without depending on Qt, VTK or G-code."""

    def __init__(self, result: BuildResult) -> None:
        self._result = result
        self._segments: list[tuple[Toolpath, Motion]] = []
        self._cumulative: list[float] = []
        cumulative = 0.0
        for toolpath in result.toolpaths:
            for motion in toolpath.motions:
                self._segments.append((toolpath, motion))
                weight = max(motion.length, 0.03)
                if motion.kind is MotionKind.RAPID:
                    weight *= 0.22
                cumulative += weight
                self._cumulative.append(cumulative)
        self.total_distance = cumulative

    @property
    def motion_count(self) -> int:
        return len(self._segments)

    def progress_for_motion_count(self, motion_count: int) -> float:
        """Return the timeline position just after a given parsed movement."""
        if not self._segments or motion_count <= 0 or self.total_distance <= 0:
            return 0.0
        if motion_count >= len(self._segments):
            return 1.0
        return self._cumulative[motion_count - 1] / self.total_distance

    @property
    def depths(self) -> tuple[float, ...]:
        return tuple(
            sorted(
                {
                    round(motion.end.z, 5)
                    for _toolpath, motion in self._segments
                    if motion.kind is not MotionKind.RAPID and motion.end.z < 0
                },
                reverse=True,
            )
        )

    def frame(self, progress: float, *, deepest_visible_z: float | None = None) -> PlaybackFrame:
        bounded = max(0.0, min(1.0, progress))
        if not self._segments or bounded <= 0:
            start = self._segments[0][1].start if self._segments else None
            tool = self._segments[0][0].tool if self._segments else None
            return PlaybackFrame(BuildResult(), bounded, start, tool, None, 0, len(self._segments))

        target = self.total_distance * bounded
        completed = min(bisect_right(self._cumulative, target), len(self._segments))
        groups: dict[str, Toolpath] = {}
        displayed = 0
        last_position: Point | None = None
        last_tool: Tool | None = None
        last_uid: str | None = None

        def add(source: Toolpath, movement: Motion) -> None:
            nonlocal displayed, last_position, last_tool, last_uid
            if (
                deepest_visible_z is not None
                and movement.kind is not MotionKind.RAPID
                and movement.end.z < deepest_visible_z - 1e-7
            ):
                return
            path = groups.get(source.operation_uid)
            if path is None:
                path = Toolpath(
                    operation_uid=source.operation_uid,
                    operation_title=source.operation_title,
                    tool=source.tool,
                    spindle_rpm=source.spindle_rpm,
                )
                groups[source.operation_uid] = path
            path.motions.append(movement)
            displayed += 1
            last_position = movement.end
            last_tool = source.tool
            last_uid = source.operation_uid

        for source, movement in self._segments[:completed]:
            add(source, movement)

        if completed < len(self._segments):
            previous = self._cumulative[completed - 1] if completed else 0.0
            current = self._cumulative[completed]
            ratio = max(0.0, min(1.0, (target - previous) / (current - previous)))
            if ratio > 1e-8:
                source, movement = self._segments[completed]
                end = Point(
                    movement.start.x + (movement.end.x - movement.start.x) * ratio,
                    movement.start.y + (movement.end.y - movement.start.y) * ratio,
                    movement.start.z + (movement.end.z - movement.start.z) * ratio,
                )
                add(source, Motion(movement.start, end, movement.kind, movement.feed))

        return PlaybackFrame(
            BuildResult(toolpaths=list(groups.values()), issues=list(self._result.issues)),
            bounded,
            last_position,
            last_tool,
            last_uid,
            displayed,
            len(self._segments),
        )
