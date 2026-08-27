"""Readable, explicit LinuxCNC-flavoured G-code generation."""

from __future__ import annotations

import json
import re
import unicodedata

from openmill.core.models import MotionKind, Project, Toolpath


def _number(value: float) -> str:
    cleaned = 0.0 if abs(value) < 0.00005 else value
    return f"{cleaned:.4f}"


def _comment(value: str) -> str:
    safe = value.replace("(", "[").replace(")", "]").replace("\n", " ").replace("\r", " ")
    return unicodedata.normalize("NFKD", safe).encode("ascii", "ignore").decode("ascii")


def generate_gcode(project: Project, paths: list[Toolpath]) -> str:
    if not re.fullmatch(r"(?:G5[4-9]|G59\.[123])", project.work_offset):
        raise ValueError("Le décalage d’origine doit être compris entre G54 et G59.3.")
    stock_metadata = json.dumps(
        {
            "width": project.stock.width,
            "height": project.stock.height,
            "thickness": project.stock.thickness,
            "origin": project.stock.origin.value,
        },
        ensure_ascii=True,
        separators=(",", ":"),
    )
    lines = [
        "%",
        f"(OPENMILL - {_comment(project.name)})",
        f"(OPENMILL_STOCK {stock_metadata})",
        "(Unites : millimetres | Origine Z : face superieure)",
        "G90 G21 G17 G40 G49 G80",
        project.work_offset,
    ]

    current_tool: int | None = None
    current_feed: float | None = None
    for index, path in enumerate(paths, 1):
        lines.extend(("", f"(OPERATION {index} - {_comment(path.operation_title)})"))
        if path.instance_count > 1:
            placement = path.placement_summary.replace("·", "-").replace("×", "x")
            lines.append(
                f"(MOTIF - {_comment(placement)} - {path.instance_count} appels)"
            )
        if current_tool != path.tool.number:
            lines.extend((f"T{path.tool.number} M6", f"G43 H{path.tool.number}"))
            current_tool = path.tool.number
            current_feed = None
        spindle_command = "M4" if path.spindle_direction == "counterclockwise" else "M3"
        lines.append(f"S{path.spindle_rpm} {spindle_command}")

        if path.motions:
            lines.append(f"G0 Z{_number(path.motions[0].start.z)}")
            if path.motions[0].kind is not MotionKind.RAPID:
                lines.append(
                    f"G0 X{_number(path.motions[0].start.x)} Y{_number(path.motions[0].start.y)}"
                )
        for motion_index, motion in enumerate(path.motions):
            if motion.kind is MotionKind.DWELL:
                lines.append(f"G4 P{_number(motion.dwell_seconds or 0.0)}")
                continue
            if motion.kind is MotionKind.TAP:
                if motion.thread_pitch is None or motion.thread_pitch <= 0:
                    raise ValueError("Un taraudage rigide nécessite un pas positif.")
                lines.append(
                    f"G33.1 Z{_number(motion.end.z)} K{_number(motion.thread_pitch)}"
                )
                current_feed = None
                continue
            if motion.kind is MotionKind.TAP_RETURN:
                # LinuxCNC G33.1 already includes the synchronized return move.
                continue
            command = "G0" if motion.kind is MotionKind.RAPID else "G1"
            components = [command]
            if motion_index == 0 or abs(motion.end.x - motion.start.x) > 1e-9:
                components.append(f"X{_number(motion.end.x)}")
            if motion_index == 0 or abs(motion.end.y - motion.start.y) > 1e-9:
                components.append(f"Y{_number(motion.end.y)}")
            if abs(motion.end.z - motion.start.z) > 1e-9:
                components.append(f"Z{_number(motion.end.z)}")
            if motion.feed is not None and motion.feed != current_feed:
                components.append(f"F{_number(motion.feed)}")
                current_feed = motion.feed
            lines.append(" ".join(components))

    lines.extend(("", "M5", "M9", "M30", "%", ""))
    output = "\n".join(lines)
    output.encode("ascii")
    return output
