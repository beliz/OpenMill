"""Frontend-independent orchestration and fault-tolerant project builds."""

from __future__ import annotations

from dataclasses import dataclass, field

from openmill import operations as _registered_operations
from openmill.adapters.base import MachineAdapter
from openmill.core.models import (
    MotionKind,
    PlacementMode,
    Project,
    RepetitionBlock,
    RepetitionOrder,
    Stock,
    Toolpath,
)
from openmill.core.placement import PlacementInstance, apply_placement, placement_instances
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


def _add_issue(result: BuildResult, issue: BuildIssue) -> None:
    key = (issue.operation_uid, issue.message, issue.severity)
    if all((entry.operation_uid, entry.message, entry.severity) != key for entry in result.issues):
        result.issues.append(issue)


def _append_toolpath(
    result: BuildResult,
    project: Project,
    operation,
    plugin,
    tool,
    toolpath: Toolpath,
) -> None:
    result.toolpaths.append(toolpath)
    for warning in toolpath.warnings:
        _add_issue(result, BuildIssue(operation.uid, operation.title, warning, "warning"))
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
            _add_issue(
                result,
                BuildIssue(
                    operation.uid,
                    operation.title,
                    "Le diamètre de l’outil dépasse les limites latérales du brut.",
                    "warning",
                ),
            )
    if any(motion.end.z < project.stock.z_min - 1e-6 for motion in toolpath.motions):
        _add_issue(
            result,
            BuildIssue(
                operation.uid,
                operation.title,
                "La trajectoire descend sous la face inférieure du brut.",
                "warning",
            ),
        )
    if any(motion.end.z < -tool.flute_length for motion in toolpath.motions):
        _add_issue(
            result,
            BuildIssue(
                operation.uid,
                operation.title,
                "La profondeur dépasse la longueur de coupe de l’outil.",
                "warning",
            ),
        )


def _build_operation_call(
    result: BuildResult,
    project: Project,
    adapter: MachineAdapter,
    operation,
    repetition: RepetitionBlock,
    instances: list[PlacementInstance] | None,
    position: int | None,
) -> None:
    try:
        plugin = registry.get(operation.plugin_id)
        tool = adapter.get_tool(operation.tool_number)
        path = plugin.generate(operation, project.stock, tool)
        path.repetition_uid = repetition.uid
        path.repetition_position = position
        toolpath = apply_placement(
            path,
            operation,
            project.stock,
            placement=repetition.placement,
            instances=instances,
        )
        _append_toolpath(result, project, operation, plugin, tool, toolpath)
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as error:
        _add_issue(result, BuildIssue(operation.uid, operation.title, str(error)))


def build_project(project: Project, adapter: MachineAdapter) -> BuildResult:
    result = BuildResult()
    by_uid = {operation.uid: operation for operation in project.operations}
    for repetition in project.repetitions:
        if not repetition.enabled:
            continue
        operations = [
            by_uid[uid]
            for uid in repetition.operation_uids
            if uid in by_uid and by_uid[uid].enabled
        ]
        if not operations:
            continue
        if (
            repetition.placement.mode is PlacementMode.SINGLE
            or repetition.execution_order is RepetitionOrder.BY_OPERATION
            or len(operations) == 1
        ):
            for operation in operations:
                _build_operation_call(
                    result,
                    project,
                    adapter,
                    operation,
                    repetition,
                    None,
                    None,
                )
            continue
        try:
            instances = placement_instances(operations[0], project.stock, repetition.placement)
        except (TypeError, ValueError, ZeroDivisionError) as error:
            operation = operations[0]
            _add_issue(result, BuildIssue(operation.uid, operation.title, str(error)))
            continue
        for position, instance in enumerate(instances, 1):
            for operation in operations:
                _build_operation_call(
                    result,
                    project,
                    adapter,
                    operation,
                    repetition,
                    [instance],
                    position,
                )
    return result


def create_demo_project() -> Project:
    stock = Stock(width=140, height=95, thickness=18)
    facing = registry.get("facing").create_record(stock, tool_number=4)
    facing.parameters.update(z_final=-0.4, step_down=0.4)

    pocket = registry.get("pocket_rectangle").create_record(stock, tool_number=1)
    pocket.parameters.update(width=76, height=48, corner_radius=8, z_final=-5, step_down=1.25)

    drilling = registry.get("drill_single").create_record(stock, tool_number=5)
    drilling.parameters.update(z_final=-11)
    project = Project(
        name="Démonstration · plaque aluminium",
        stock=stock,
        operations=[facing, pocket, drilling],
    )
    drilling_repetition = project.repetition_for(drilling.uid)
    assert drilling_repetition is not None
    drilling_repetition.placement.mode = PlacementMode.POLAR
    drilling_repetition.placement.center_x = stock.center_x
    drilling_repetition.placement.center_y = stock.center_y
    drilling_repetition.placement.diameter = 76
    drilling_repetition.placement.count = 8
    drilling_repetition.placement.start_angle = 22.5
    return project


__all__ = ["BuildIssue", "BuildResult", "build_project", "create_demo_project"]
