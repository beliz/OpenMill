"""Operation registration and declarative parameter descriptions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from importlib.metadata import entry_points
from typing import Any, ClassVar

from openmill.core.models import OperationRecord, Placement, Stock, Tool, Toolpath
from openmill.core.toolpath import ToolpathBuilder


@dataclass(frozen=True, slots=True)
class FieldSpec:
    key: str
    label: str
    default: Any
    section: str = "Géométrie"
    unit: str = "mm"
    minimum: float = -10_000.0
    maximum: float = 10_000.0
    decimals: int = 2
    kind: str = "float"
    choices: tuple[tuple[str, str], ...] = ()
    tip: str = ""


COMMON_FIELDS = (
    FieldSpec("z_start", "Z départ", 0.0, section="Profondeurs"),
    FieldSpec("z_final", "Z final", -3.0, section="Profondeurs"),
    FieldSpec("step_down", "Profondeur de passe", 1.0, section="Profondeurs", minimum=0.01),
    FieldSpec("clearance", "Hauteur de sécurité", 5.0, section="Profondeurs", minimum=0.1),
    FieldSpec("feed_xy", "Avance XY", 600.0, section="Coupe", unit="mm/min", minimum=1),
    FieldSpec("feed_z", "Avance plongée", 180.0, section="Coupe", unit="mm/min", minimum=1),
    FieldSpec("spindle_rpm", "Vitesse de broche", 12_000, section="Coupe", unit="tr/min", minimum=1, maximum=50_000, kind="int"),
)


class OperationPlugin(ABC):
    id: ClassVar[str]
    label: ClassVar[str]
    category: ClassVar[str]
    description: ClassVar[str]
    picker_visible: ClassVar[bool] = True
    fields: ClassVar[tuple[FieldSpec, ...]] = ()
    common_fields: ClassVar[tuple[FieldSpec, ...]] = COMMON_FIELDS

    @classmethod
    def all_fields(cls) -> tuple[FieldSpec, ...]:
        return (*cls.fields, *cls.common_fields)

    @classmethod
    def defaults(cls, stock: Stock | None = None) -> dict[str, Any]:
        values = {spec.key: spec.default for spec in cls.all_fields()}
        if stock is not None:
            if "center_x" in values:
                values["center_x"] = stock.center_x
            if "center_y" in values:
                values["center_y"] = stock.center_y
        return values

    @classmethod
    def create_record(cls, stock: Stock, tool_number: int = 1) -> OperationRecord:
        parameters = cls.defaults(stock)
        anchor_x = float(parameters.get("center_x", stock.center_x))
        anchor_y = float(parameters.get("center_y", stock.center_y))
        return OperationRecord(
            plugin_id=cls.id,
            title=cls.label,
            tool_number=tool_number,
            parameters=parameters,
            placement=Placement(
                start_x=anchor_x,
                start_y=anchor_y,
                center_x=stock.center_x,
                center_y=stock.center_y,
            ),
        )

    @classmethod
    def builder(cls, operation: OperationRecord, tool: Tool) -> ToolpathBuilder:
        parameters = operation.parameters
        return ToolpathBuilder(
            operation_uid=operation.uid,
            operation_title=operation.title,
            tool=tool,
            clearance=float(parameters["clearance"]),
            feed_xy=float(parameters["feed_xy"]),
            feed_z=float(parameters["feed_z"]),
            spindle_rpm=int(parameters["spindle_rpm"]),
        )

    @classmethod
    @abstractmethod
    def generate(cls, operation: OperationRecord, stock: Stock, tool: Tool) -> Toolpath:
        raise NotImplementedError


class OperationRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, type[OperationPlugin]] = {}
        self._entry_points_loaded = False

    def register(self, plugin: type[OperationPlugin]) -> type[OperationPlugin]:
        if plugin.id in self._plugins:
            raise ValueError(f"Opération déjà enregistrée : {plugin.id}.")
        self._plugins[plugin.id] = plugin
        return plugin

    def get(self, plugin_id: str) -> type[OperationPlugin]:
        try:
            return self._plugins[plugin_id]
        except KeyError as error:
            raise ValueError(f"Opération inconnue : {plugin_id}.") from error

    def all(self) -> tuple[type[OperationPlugin], ...]:
        return tuple(self._plugins.values())

    def grouped(self) -> dict[str, list[type[OperationPlugin]]]:
        groups: dict[str, list[type[OperationPlugin]]] = {}
        for plugin in self._plugins.values():
            groups.setdefault(plugin.category, []).append(plugin)
        return groups

    def discover_entry_points(self) -> None:
        """Load separately installed operations without coupling them to the UI."""
        if self._entry_points_loaded:
            return
        self._entry_points_loaded = True
        for entry_point in entry_points(group="openmill.operations"):
            plugin = entry_point.load()
            if not isinstance(plugin, type) or not issubclass(plugin, OperationPlugin):
                raise TypeError(
                    f"L’extension {entry_point.name} doit référencer une classe OperationPlugin."
                )
            existing = self._plugins.get(plugin.id)
            if existing is None:
                self.register(plugin)
            elif existing is not plugin:
                raise ValueError(f"Une extension utilise un identifiant d’opération existant : {plugin.id}.")


registry = OperationRegistry()
