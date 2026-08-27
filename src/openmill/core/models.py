"""Pure-Python domain objects shared by every frontend and adapter."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import Enum
import math
from typing import Any
from uuid import uuid4


class OriginMode(str, Enum):
    LOWER_LEFT = "lower_left"
    CENTER = "center"


class MotionKind(str, Enum):
    RAPID = "rapid"
    CUT = "cut"
    PLUNGE = "plunge"
    DWELL = "dwell"
    TAP = "tap"
    TAP_RETURN = "tap_return"


class PlacementMode(str, Enum):
    """How one conversational cycle is called on the workpiece."""

    SINGLE = "single"
    LINEAR = "linear"
    GRID = "grid"
    POLAR = "polar"


class RepetitionOrder(str, Enum):
    """How operations nested in one repetition block are scheduled."""

    BY_POSITION = "by_position"
    BY_OPERATION = "by_operation"


@dataclass(frozen=True, slots=True)
class Point:
    x: float
    y: float
    z: float

    def distance_to(self, other: Point) -> float:
        return math.dist((self.x, self.y, self.z), (other.x, other.y, other.z))


@dataclass(frozen=True, slots=True)
class Tool:
    number: int
    diameter: float
    name: str
    flute_length: float = 20.0

    def __post_init__(self) -> None:
        if self.number < 1:
            raise ValueError("Le numéro d’outil doit être supérieur à zéro.")
        if self.diameter <= 0:
            raise ValueError("Le diamètre d’outil doit être supérieur à zéro.")


@dataclass(slots=True)
class Stock:
    width: float = 120.0
    height: float = 80.0
    thickness: float = 20.0
    origin: OriginMode = OriginMode.LOWER_LEFT

    def __post_init__(self) -> None:
        self.origin = OriginMode(self.origin)
        if min(self.width, self.height, self.thickness) <= 0:
            raise ValueError("Toutes les dimensions du brut doivent être positives.")

    @property
    def x_min(self) -> float:
        return -self.width / 2 if self.origin is OriginMode.CENTER else 0.0

    @property
    def x_max(self) -> float:
        return self.x_min + self.width

    @property
    def y_min(self) -> float:
        return -self.height / 2 if self.origin is OriginMode.CENTER else 0.0

    @property
    def y_max(self) -> float:
        return self.y_min + self.height

    @property
    def z_min(self) -> float:
        return -self.thickness

    @property
    def z_max(self) -> float:
        return 0.0

    @property
    def center_x(self) -> float:
        return (self.x_min + self.x_max) / 2

    @property
    def center_y(self) -> float:
        return (self.y_min + self.y_max) / 2


@dataclass(slots=True)
class Placement:
    """Placement/pattern definition kept independent from machining geometry.

    The vocabulary deliberately follows conversational controls: a machining
    cycle is defined once, then called at one point or on a Cartesian/polar
    pattern.  All coordinates are absolute in the active work offset.
    """

    mode: PlacementMode = PlacementMode.SINGLE
    start_x: float = 0.0
    start_y: float = 0.0
    count: int = 2
    step_x: float = 20.0
    step_y: float = 0.0
    columns: int = 2
    rows: int = 2
    spacing_x: float = 20.0
    spacing_y: float = 20.0
    grid_angle: float = 0.0
    serpentine: bool = True
    center_x: float = 0.0
    center_y: float = 0.0
    diameter: float = 60.0
    start_angle: float = 0.0
    sweep: float = 360.0
    rotate_geometry: bool = False

    def __post_init__(self) -> None:
        self.mode = PlacementMode(self.mode)

    @property
    def instance_count(self) -> int:
        if self.mode is PlacementMode.SINGLE:
            return 1
        if self.mode in {PlacementMode.LINEAR, PlacementMode.POLAR}:
            return max(0, int(self.count))
        return max(0, int(self.columns)) * max(0, int(self.rows))

    @property
    def summary(self) -> str:
        if self.mode is PlacementMode.SINGLE:
            return "Position unique"
        if self.mode is PlacementMode.LINEAR:
            return f"Ligne · {self.count} positions"
        if self.mode is PlacementMode.GRID:
            return f"Grille · {self.columns} × {self.rows}"
        return f"Cercle · {self.count} positions"

    @property
    def label(self) -> str:
        return {
            PlacementMode.SINGLE: "Unique",
            PlacementMode.LINEAR: "Ligne",
            PlacementMode.GRID: "Grille",
            PlacementMode.POLAR: "Cercle",
        }[self.mode]


@dataclass(frozen=True, slots=True)
class Motion:
    start: Point
    end: Point
    kind: MotionKind
    feed: float | None = None
    dwell_seconds: float | None = None
    thread_pitch: float | None = None

    @property
    def length(self) -> float:
        return self.start.distance_to(self.end)


@dataclass(slots=True)
class OperationRecord:
    plugin_id: str
    title: str
    tool_number: int = 1
    parameters: dict[str, Any] = field(default_factory=dict)
    placement: Placement = field(default_factory=Placement)
    enabled: bool = True
    uid: str = field(default_factory=lambda: uuid4().hex)
    expressions: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.expressions = dict(self.expressions or {})
        if isinstance(self.placement, dict):
            self.placement = Placement(**self.placement)

    def clone(self) -> OperationRecord:
        return OperationRecord(
            plugin_id=self.plugin_id,
            title=f"{self.title} — copie",
            tool_number=self.tool_number,
            parameters=dict(self.parameters),
            expressions=dict(self.expressions),
            placement=replace(self.placement),
            enabled=self.enabled,
        )


@dataclass(slots=True)
class RepetitionBlock:
    """First-class program block applying one placement to nested operations."""

    operation_uids: list[str] = field(default_factory=list)
    placement: Placement = field(default_factory=Placement)
    execution_order: RepetitionOrder = RepetitionOrder.BY_POSITION
    enabled: bool = True
    uid: str = field(default_factory=lambda: uuid4().hex)
    expressions: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.expressions = dict(self.expressions or {})
        if isinstance(self.placement, dict):
            self.placement = Placement(**self.placement)
        self.execution_order = RepetitionOrder(self.execution_order)

    @property
    def title(self) -> str:
        return f"Répétition [{self.placement.label}]"

    def clone(self, operation_uids: list[str]) -> RepetitionBlock:
        return RepetitionBlock(
            operation_uids=operation_uids,
            placement=replace(self.placement),
            expressions=dict(self.expressions),
            execution_order=self.execution_order,
            enabled=self.enabled,
        )


@dataclass(slots=True)
class Toolpath:
    operation_uid: str
    operation_title: str
    tool: Tool
    motions: list[Motion] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    spindle_rpm: int = 12_000
    spindle_direction: str = "clockwise"
    instance_count: int = 1
    placement_summary: str = "Position unique"
    repetition_uid: str = ""
    repetition_position: int | None = None

    @property
    def cutting_length(self) -> float:
        return sum(motion.length for motion in self.motions if motion.kind is not MotionKind.RAPID)

    @property
    def rapid_length(self) -> float:
        return sum(motion.length for motion in self.motions if motion.kind is MotionKind.RAPID)

    def estimated_minutes(self, rapid_feed: float = 3_000.0) -> float:
        return sum(
            (motion.dwell_seconds or 0.0) / 60
            if motion.kind is MotionKind.DWELL
            else motion.length
            / (rapid_feed if motion.kind is MotionKind.RAPID else motion.feed or 300.0)
            for motion in self.motions
        )


@dataclass(slots=True)
class Project:
    name: str = "Nouvelle pièce"
    stock: Stock = field(default_factory=Stock)
    operations: list[OperationRecord] = field(default_factory=list)
    repetitions: list[RepetitionBlock] = field(default_factory=list)
    work_offset: str = "G54"
    schema_version: int = 2

    def __post_init__(self) -> None:
        self.repetitions = [
            block if isinstance(block, RepetitionBlock) else RepetitionBlock(**block)
            for block in self.repetitions
        ]
        known_uids = {operation.uid for operation in self.operations}
        grouped_uids: set[str] = set()
        for block in self.repetitions:
            block.operation_uids = [
                uid for uid in block.operation_uids if uid in known_uids and uid not in grouped_uids
            ]
            grouped_uids.update(block.operation_uids)
        for operation in self.operations:
            if operation.uid not in grouped_uids:
                self.repetitions.append(
                    RepetitionBlock(
                        operation_uids=[operation.uid],
                        placement=replace(operation.placement),
                    )
                )
        by_uid = {operation.uid: operation for operation in self.operations}
        for block in self.repetitions:
            for operation_uid in block.operation_uids:
                if operation_uid in by_uid:
                    # Compatibility alias for integrations written against
                    # schema 1.  The editor and JSON both use the block.
                    by_uid[operation_uid].placement = block.placement

    def repetition_for(self, operation_uid: str) -> RepetitionBlock | None:
        return next(
            (block for block in self.repetitions if operation_uid in block.operation_uids),
            None,
        )

    def to_dict(self) -> dict[str, Any]:
        stock = asdict(self.stock)
        stock["origin"] = self.stock.origin.value
        operations = []
        for record in self.operations:
            operation = asdict(record)
            # Since schema 2, placement belongs to a repetition block.  The
            # attribute remains on OperationRecord only as a source migration
            # shim for callers still constructing schema-1 style projects.
            operation.pop("placement", None)
            operations.append(operation)
        repetitions = []
        for record in self.repetitions:
            repetition = asdict(record)
            repetition["placement"]["mode"] = record.placement.mode.value
            repetition["execution_order"] = record.execution_order.value
            repetitions.append(repetition)
        return {
            "name": self.name,
            "stock": stock,
            "operations": operations,
            "repetitions": repetitions,
            "work_offset": self.work_offset,
            "schema_version": 2,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Project:
        version = payload.get("schema_version", 1)
        if version not in {1, 2}:
            raise ValueError(f"Version de projet non prise en charge : {version}.")
        operations = [OperationRecord(**record) for record in payload.get("operations", [])]
        repetitions = (
            [RepetitionBlock(**record) for record in payload.get("repetitions", [])]
            if version == 2
            else []
        )
        return cls(
            name=payload.get("name", "Projet importé"),
            stock=Stock(**payload.get("stock", {})),
            operations=operations,
            repetitions=repetitions,
            work_offset=payload.get("work_offset", "G54"),
            schema_version=2,
        )
