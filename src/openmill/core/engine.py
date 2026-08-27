"""Frontend-independent orchestration and fault-tolerant project builds."""

from __future__ import annotations

from dataclasses import dataclass, field

from openmill import operations as _registered_operations
from openmill.adapters.base import MachineAdapter
from openmill.core.models import MotionKind, PlacementMode, Project, Stock, Toolpath
from openmill.core.placement import apply_placement
from openmill.core.registry import registry


registry.discover_entry_points()


@dataclass(frozen=True, slots=True)
class BuildIssue:
    operation_uid: str
    operation_title: str
    message: str
    severity: str = "error"


@dataclass(slots=True)
class BuildResult:
    toolpaths: list[Toolpath] = field(default_factory=list)
    issues: list[BuildIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[BuildIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[BuildIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def estimated_minutes(self) -> float:
        return sum(toolpath.estimated_minutes() for toolpath in self.toolpaths)


def build_project(project: Project, adapter: MachineAdapter) -> BuildResult:
    result = BuildResult()
    for operation in project.operations:
        if not operation.enabled:
            continue
        try:
            plugin = registry.get(operation.plugin_id)
            tool = adapter.get_tool(operation.tool_number)
            toolpath = apply_placement(
                plugin.generate(operation, project.stock, tool),
                operation,
                project.stock,
            )
            result.toolpaths.append(toolpath)
            for warning in toolpath.warnings:
                result.issues.append(BuildIssue(operation.uid, operation.title, warning, "warning"))
            if plugin.id != "facing":
                radius = tool.diameter / 2
                outside_stock = any(
                    motion.kind is not MotionKind.RAPID
                    and (
                        motion.end.x - radius < project.stock.x_min - 1e-6
                        or motion.end.x + radius > project.stock.x_max + 1e-6
                        or motion.end.y - radius < project.stock.y_min - 1e-6
                        or motion.end.y + radius > project.stock.y_max + 1e-6
                    )
                    for motion in toolpath.motions
                )
                if outside_stock:
                    result.issues.append(
                        BuildIssue(
                            operation.uid,
                            operation.title,
                            "Le diamètre de l’outil dépasse les limites latérales du brut.",
                            "warning",
                        )
                    )
            if any(motion.end.z < project.stock.z_min - 1e-6 for motion in toolpath.motions):
                result.issues.append(
                    BuildIssue(
                        operation.uid,
                        operation.title,
                        "La trajectoire descend sous la face inférieure du brut.",
                        "warning",
                    )
                )
            if any(motion.end.z < -tool.flute_length for motion in toolpath.motions):
                result.issues.append(
                    BuildIssue(
                        operation.uid,
                        operation.title,
                        "La profondeur dépasse la longueur de coupe de l’outil.",
                        "warning",
                    )
                )
        except (KeyError, TypeError, ValueError, ZeroDivisionError) as error:
            result.issues.append(BuildIssue(operation.uid, operation.title, str(error)))
    return result


def create_demo_project() -> Project:
    stock = Stock(width=140, height=95, thickness=18)
    facing = registry.get("facing").create_record(stock, tool_number=4)
    facing.parameters.update(z_final=-0.4, step_down=0.4)

    pocket = registry.get("pocket_rectangle").create_record(stock, tool_number=1)
    pocket.parameters.update(width=76, height=48, corner_radius=8, z_final=-5, step_down=1.25)

    drilling = registry.get("drill_single").create_record(stock, tool_number=5)
    drilling.parameters.update(z_final=-11)
    drilling.placement.mode = PlacementMode.POLAR
    drilling.placement.center_x = stock.center_x
    drilling.placement.center_y = stock.center_y
    drilling.placement.diameter = 76
    drilling.placement.count = 8
    drilling.placement.start_angle = 22.5

    return Project(name="Démonstration · plaque aluminium", stock=stock, operations=[facing, pocket, drilling])


__all__ = ["BuildIssue", "BuildResult", "build_project", "create_demo_project"]
