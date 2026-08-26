"""Pure-Python domain objects shared by every frontend and adapter."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
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


@dataclass(frozen=True, slots=True)
class Motion:
    start: Point
    end: Point
    kind: MotionKind
    feed: float | None = None

    @property
    def length(self) -> float:
        return self.start.distance_to(self.end)


@dataclass(slots=True)
class OperationRecord:
    plugin_id: str
    title: str
    tool_number: int = 1
    parameters: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    uid: str = field(default_factory=lambda: uuid4().hex)

    def clone(self) -> OperationRecord:
        return OperationRecord(
            plugin_id=self.plugin_id,
            title=f"{self.title} — copie",
            tool_number=self.tool_number,
            parameters=dict(self.parameters),
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

    @property
    def cutting_length(self) -> float:
        return sum(motion.length for motion in self.motions if motion.kind is not MotionKind.RAPID)

    @property
    def rapid_length(self) -> float:
        return sum(motion.length for motion in self.motions if motion.kind is MotionKind.RAPID)

    def estimated_minutes(self, rapid_feed: float = 3_000.0) -> float:
        return sum(
            motion.length / (rapid_feed if motion.kind is MotionKind.RAPID else motion.feed or 300.0)
            for motion in self.motions
        )


@dataclass(slots=True)
class Project:
    name: str = "Nouvelle pièce"
    stock: Stock = field(default_factory=Stock)
    operations: list[OperationRecord] = field(default_factory=list)
    work_offset: str = "G54"
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["stock"]["origin"] = self.stock.origin.value
        return result

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Project:
        version = payload.get("schema_version", 1)
        if version != 1:
            raise ValueError(f"Version de projet non prise en charge : {version}.")
        return cls(
            name=payload.get("name", "Projet importé"),
            stock=Stock(**payload.get("stock", {})),
            operations=[OperationRecord(**record) for record in payload.get("operations", [])],
            work_offset=payload.get("work_offset", "G54"),
            schema_version=version,
        )

