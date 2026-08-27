"""Small, deterministic RS274 preview parser for external LinuxCNC programs."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
from pathlib import Path
import re
from typing import Callable

from openmill.core.engine import BuildResult, BuildIssue
from openmill.core.models import Motion, MotionKind, OriginMode, Point, Project, Stock, Tool, Toolpath


_WORD = re.compile(r"([A-Za-z])\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))")
_PAREN_COMMENT = re.compile(r"\([^)]*\)")
_STOCK = re.compile(r"\(OPENMILL_STOCK\s+({.*?})\)", re.IGNORECASE)


@dataclass(slots=True)
class ParsedGcode:
    project: Project
    result: BuildResult
    warnings: list[str] = field(default_factory=list)
    line_motion_counts: dict[int, int] = field(default_factory=dict)


def _default_tool(number: int) -> Tool:
    return Tool(max(1, number), 6.0, f"Outil T{max(1, number)} · diamètre inconnu")


def _point(values: dict[str, float]) -> Point:
    return Point(values["X"], values["Y"], values["Z"])


def _arc_points(
    start: Point,
    end: Point,
    words: dict[str, float],
    *,
    plane: str,
    clockwise: bool,
) -> list[Point]:
    axes, centers = {
        "G17": (("X", "Y", "Z"), ("I", "J")),
        "G18": (("X", "Z", "Y"), ("I", "K")),
        "G19": (("Y", "Z", "X"), ("J", "K")),
    }[plane]
    first, second, linear = axes
    offset_first, offset_second = centers
    start_values = {"X": start.x, "Y": start.y, "Z": start.z}
    end_values = {"X": end.x, "Y": end.y, "Z": end.z}
    if "R" in words and offset_first not in words and offset_second not in words:
        delta_first = end_values[first] - start_values[first]
        delta_second = end_values[second] - start_values[second]
        chord = math.hypot(delta_first, delta_second)
        requested_radius = words["R"]
        radius = abs(requested_radius)
        if chord <= 1e-9 or chord > 2 * radius + 1e-7:
            raise ValueError("rayon R impossible")
        midpoint_first = (start_values[first] + end_values[first]) / 2
        midpoint_second = (start_values[second] + end_values[second]) / 2
        height = math.sqrt(max(radius * radius - (chord / 2) ** 2, 0.0))
        perpendicular = (-delta_second / chord, delta_first / chord)
        candidates = (
            (midpoint_first + perpendicular[0] * height, midpoint_second + perpendicular[1] * height),
            (midpoint_first - perpendicular[0] * height, midpoint_second - perpendicular[1] * height),
        )

        def candidate_sweep(center: tuple[float, float]) -> float:
            start_angle = math.atan2(start_values[second] - center[1], start_values[first] - center[0])
            end_angle = math.atan2(end_values[second] - center[1], end_values[first] - center[0])
            value = end_angle - start_angle
            if clockwise and value >= 0:
                value -= 2 * math.pi
            elif not clockwise and value <= 0:
                value += 2 * math.pi
            return value

        wanted_major = requested_radius < 0
        center_first, center_second = next(
            (
                candidate
                for candidate in candidates
                if (abs(candidate_sweep(candidate)) > math.pi + 1e-7) == wanted_major
            ),
            candidates[0],
        )
    else:
        center_first = start_values[first] + words.get(offset_first, 0.0)
        center_second = start_values[second] + words.get(offset_second, 0.0)
    radius = math.hypot(start_values[first] - center_first, start_values[second] - center_second)
    if radius <= 1e-9:
        return [end]
    start_angle = math.atan2(start_values[second] - center_second, start_values[first] - center_first)
    end_angle = math.atan2(end_values[second] - center_second, end_values[first] - center_first)
    sweep = end_angle - start_angle
    if clockwise and sweep >= 0:
        sweep -= 2 * math.pi
    elif not clockwise and sweep <= 0:
        sweep += 2 * math.pi
    segments = max(8, min(720, math.ceil(abs(sweep) * radius / 0.75)))
    points: list[Point] = []
    for index in range(1, segments + 1):
        ratio = index / segments
        angle = start_angle + sweep * ratio
        values = dict(start_values)
        values[first] = center_first + math.cos(angle) * radius
        values[second] = center_second + math.sin(angle) * radius
        values[linear] = start_values[linear] + (end_values[linear] - start_values[linear]) * ratio
        if index == segments:
            values.update(end_values)
        points.append(_point(values))
    return points


def _stock_from_metadata(text: str) -> Stock | None:
    match = _STOCK.search(text)
    if match is None:
        return None
    try:
        payload = json.loads(match.group(1))
        return Stock(
            width=float(payload["width"]),
            height=float(payload["height"]),
            thickness=float(payload["thickness"]),
            origin=OriginMode(payload.get("origin", OriginMode.LOWER_LEFT.value)),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _inferred_stock(toolpaths: list[Toolpath]) -> Stock:
    points = [point for path in toolpaths for motion in path.motions for point in (motion.start, motion.end)]
    if not points:
        return Stock()
    min_x, max_x = min(point.x for point in points), max(point.x for point in points)
    min_y, max_y = min(point.y for point in points), max(point.y for point in points)
    min_z = min(point.z for point in points)
    margin = max(max_x - min_x, max_y - min_y, 10.0) * 0.06
    if min_x >= -1e-6 and min_y >= -1e-6:
        return Stock(max(max_x + margin, 1.0), max(max_y + margin, 1.0), max(-min_z, 1.0))
    return Stock(
        max(2 * max(abs(min_x), abs(max_x)) + 2 * margin, 1.0),
        max(2 * max(abs(min_y), abs(max_y)) + 2 * margin, 1.0),
        max(-min_z, 1.0),
        OriginMode.CENTER,
    )


def parse_gcode(
    text: str,
    *,
    name: str = "Programme G-code",
    tool_lookup: Callable[[int], Tool] | None = None,
) -> ParsedGcode:
    """Convert the previewable RS274 subset to OpenMill toolpaths.

    Unsupported commands are ignored for display only; LinuxCNC remains the
    authority that validates and executes the original program.
    """
    lookup = tool_lookup or _default_tool
    position = Point(0.0, 0.0, 0.0)
    absolute = True
    factor = 1.0
    plane = "G17"
    motion_mode = "G0"
    feed: float | None = None
    spindle = 0
    tool_number = 1
    sequence = 0
    active: Toolpath | None = None
    toolpaths: list[Toolpath] = []
    warnings: list[str] = []
    line_motion_counts: dict[int, int] = {}
    motion_count = 0

    def path_for_tool() -> Toolpath:
        nonlocal active, sequence
        if active is not None and active.tool.number == max(1, tool_number):
            return active
        sequence += 1
        number = max(1, tool_number)
        try:
            tool = lookup(number)
        except (KeyError, TypeError, ValueError):
            tool = _default_tool(number)
            warnings.append(f"Diamètre de T{number} inconnu : aperçu avec Ø 6 mm.")
        active = Toolpath(f"gcode-{sequence}", f"T{number} · G-code importé", tool, spindle_rpm=spindle)
        toolpaths.append(active)
        return active

    for line_number, source_line in enumerate(text.splitlines(), 1):
        line = _PAREN_COMMENT.sub(" ", source_line.split(";", 1)[0]).upper()
        tokens = [(letter.upper(), float(value)) for letter, value in _WORD.findall(line)]
        if not tokens:
            line_motion_counts[line_number] = motion_count
            continue
        g_codes = [value for letter, value in tokens if letter == "G"]
        rigid_tapping = any(math.isclose(code, 33.1, abs_tol=1e-9) for code in g_codes)
        for code in g_codes:
            normalized = f"G{code:g}"
            if normalized in {"G0", "G1", "G2", "G3"}:
                motion_mode = normalized
            elif normalized in {"G17", "G18", "G19"}:
                plane = normalized
            elif normalized == "G20":
                factor = 25.4
            elif normalized == "G21":
                factor = 1.0
            elif normalized == "G90":
                absolute = True
            elif normalized == "G91":
                absolute = False
        for letter, value in tokens:
            if letter == "T":
                tool_number = max(1, int(value))
                active = None
            elif letter == "F":
                feed = value * factor
            elif letter == "S":
                spindle = max(0, int(value))

        coordinates = {letter: value * factor for letter, value in tokens if letter in "XYZIJKR"}
        if not any(axis in coordinates for axis in "XYZ"):
            line_motion_counts[line_number] = motion_count
            continue
        current = {"X": position.x, "Y": position.y, "Z": position.z}
        target_values = dict(current)
        for axis in "XYZ":
            if axis in coordinates:
                target_values[axis] = coordinates[axis] if absolute else current[axis] + coordinates[axis]
        target = _point(target_values)
        path = path_for_tool()
        if rigid_tapping:
            pitch = coordinates.get("K")
            if pitch is None or pitch <= 0:
                warnings.append(
                    f"Ligne {line_number} : taraudage G33.1 sans pas K positif."
                )
                pitch = 1.0
            tapping_feed = spindle * pitch if spindle > 0 else feed
            path.motions.append(
                Motion(
                    position,
                    target,
                    MotionKind.TAP,
                    tapping_feed,
                    thread_pitch=pitch,
                )
            )
            path.motions.append(
                Motion(
                    target,
                    position,
                    MotionKind.TAP_RETURN,
                    tapping_feed,
                    thread_pitch=pitch,
                )
            )
            motion_count += 2
        elif motion_mode in {"G2", "G3"}:
            try:
                points = _arc_points(position, target, coordinates, plane=plane, clockwise=motion_mode == "G2")
            except ValueError as error:
                warnings.append(f"Ligne {line_number} : {error}, arc affiché comme un segment.")
                points = [target]
            for arc_end in points:
                path.motions.append(Motion(position, arc_end, MotionKind.CUT, feed))
                motion_count += 1
                position = arc_end
        else:
            kind = MotionKind.RAPID if motion_mode == "G0" else MotionKind.CUT
            if kind is MotionKind.CUT and abs(target.z - position.z) > 1e-9 and abs(target.x - position.x) < 1e-9 and abs(target.y - position.y) < 1e-9:
                kind = MotionKind.PLUNGE
            path.motions.append(Motion(position, target, kind, feed))
            motion_count += 1
            position = target
        line_motion_counts[line_number] = motion_count

    stock = _stock_from_metadata(text) or _inferred_stock(toolpaths)
    project = Project(name=name, stock=stock)
    issues = [BuildIssue("gcode", name, warning, "warning") for warning in dict.fromkeys(warnings)]
    return ParsedGcode(
        project,
        BuildResult(toolpaths, issues),
        list(dict.fromkeys(warnings)),
        line_motion_counts,
    )


def parse_gcode_file(path: str | Path, *, tool_lookup: Callable[[int], Tool] | None = None) -> ParsedGcode:
    filename = Path(path)
    raw = filename.read_bytes()
    for encoding in ("ascii", "utf-8-sig", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    return parse_gcode(text, name=filename.stem, tool_lookup=tool_lookup)
