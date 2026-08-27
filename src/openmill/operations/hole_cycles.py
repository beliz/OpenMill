"""Point-based machining cycles, independently reusable on any placement pattern."""

from __future__ import annotations

from openmill.core.geometry import depth_levels
from openmill.core.models import MotionKind, OperationRecord, Stock, Tool, Toolpath
from openmill.core.registry import FieldSpec, OperationPlugin, registry
from openmill.core.toolpath import ToolpathBuilder


POSITION_FIELDS = (
    FieldSpec("center_x", "Position X", 60.0),
    FieldSpec("center_y", "Position Y", 40.0),
)

CYCLE_COMMON_FIELDS = (
    FieldSpec("z_start", "Surface de la pièce", 0.0, section="Profondeurs"),
    FieldSpec("z_final", "Profondeur finale", -10.0, section="Profondeurs"),
    FieldSpec(
        "clearance",
        "Hauteur de sécurité",
        5.0,
        section="Profondeurs",
        minimum=0.1,
    ),
    FieldSpec(
        "feed_z",
        "Avance de pénétration",
        180.0,
        section="Coupe",
        unit="mm/min",
        minimum=1,
    ),
    FieldSpec(
        "spindle_rpm",
        "Vitesse de broche",
        2500,
        section="Coupe",
        unit="tr/min",
        minimum=1,
        maximum=50_000,
        kind="int",
    ),
)


def _validate_depth(operation: OperationRecord) -> tuple[float, float]:
    start = float(operation.parameters["z_start"])
    final = float(operation.parameters["z_final"])
    if final >= start:
        raise ValueError("La profondeur finale doit être inférieure à la surface de la pièce.")
    return start, final


def _builder(operation: OperationRecord, tool: Tool) -> ToolpathBuilder:
    parameters = operation.parameters
    return ToolpathBuilder(
        operation_uid=operation.uid,
        operation_title=operation.title,
        tool=tool,
        clearance=float(parameters["clearance"]),
        feed_xy=float(parameters.get("retract_feed", parameters.get("feed_z", 180.0))),
        feed_z=float(parameters.get("feed_z", 180.0)),
        spindle_rpm=int(parameters["spindle_rpm"]),
    )


def _position_cycle(builder: ToolpathBuilder, operation: OperationRecord) -> None:
    builder.rapid(
        float(operation.parameters["center_x"]),
        float(operation.parameters["center_y"]),
    )
    start = float(operation.parameters["z_start"])
    if builder.position.z > start + 1e-9:
        builder.move(z=start, kind=MotionKind.RAPID)


@registry.register
class SimpleDrillingOperation(OperationPlugin):
    id = "drill_single"
    label = "Perçage simple"
    category = "Cycles de perçage"
    description = "Cycle de perçage direct, équivalent conversationnel du G81."
    fields = POSITION_FIELDS
    common_fields = CYCLE_COMMON_FIELDS

    @classmethod
    def generate(cls, operation: OperationRecord, stock: Stock, tool: Tool) -> Toolpath:
        _start, final = _validate_depth(operation)
        builder = _builder(operation, tool)
        _position_cycle(builder, operation)
        builder.plunge(final)
        builder.retract()
        return builder.result


@registry.register
class PeckDrillingOperation(OperationPlugin):
    id = "drill_peck"
    label = "Perçage profond"
    category = "Cycles de perçage"
    description = "Débourrage par passes avec remontée complète, équivalent du G83."
    fields = (
        *POSITION_FIELDS,
        FieldSpec(
            "peck",
            "Profondeur par débourrage",
            2.0,
            section="Profondeurs",
            minimum=0.01,
        ),
    )
    common_fields = CYCLE_COMMON_FIELDS

    @classmethod
    def generate(cls, operation: OperationRecord, stock: Stock, tool: Tool) -> Toolpath:
        start, final = _validate_depth(operation)
        peck = float(operation.parameters["peck"])
        if peck <= 0:
            raise ValueError("La profondeur de débourrage doit être supérieure à zéro.")
        builder = _builder(operation, tool)
        _position_cycle(builder, operation)
        for level in depth_levels(start, final, peck):
            builder.plunge(level)
            builder.retract()
            if level > final + 1e-9:
                builder.move(z=start, kind=MotionKind.RAPID)
        return builder.result


@registry.register
class DwellDrillingOperation(OperationPlugin):
    id = "drill_dwell"
    label = "Perçage avec pause / lamage"
    category = "Cycles de perçage"
    description = "Perçage avec temporisation au fond, équivalent du G82."
    fields = (
        *POSITION_FIELDS,
        FieldSpec(
            "dwell",
            "Temporisation au fond",
            0.5,
            section="Profondeurs",
            unit="s",
            minimum=0,
            maximum=3600,
        ),
    )
    common_fields = CYCLE_COMMON_FIELDS

    @classmethod
    def generate(cls, operation: OperationRecord, stock: Stock, tool: Tool) -> Toolpath:
        _start, final = _validate_depth(operation)
        builder = _builder(operation, tool)
        _position_cycle(builder, operation)
        builder.plunge(final)
        builder.dwell(float(operation.parameters["dwell"]))
        builder.retract()
        return builder.result


@registry.register
class ReamingOperation(OperationPlugin):
    id = "ream"
    label = "Alésage à l’alésoir"
    category = "Cycles de perçage"
    description = "Descente et remontée à avance contrôlée, équivalent du G85."
    fields = (
        *POSITION_FIELDS,
        FieldSpec(
            "retract_feed",
            "Avance de remontée",
            300.0,
            section="Coupe",
            unit="mm/min",
            minimum=1,
        ),
    )
    common_fields = CYCLE_COMMON_FIELDS

    @classmethod
    def generate(cls, operation: OperationRecord, stock: Stock, tool: Tool) -> Toolpath:
        start, final = _validate_depth(operation)
        builder = _builder(operation, tool)
        _position_cycle(builder, operation)
        builder.feed_to_z(final, float(operation.parameters["feed_z"]))
        builder.feed_to_z(start, float(operation.parameters["retract_feed"]))
        builder.retract()
        return builder.result


@registry.register
class RigidTappingOperation(OperationPlugin):
    id = "tap_rigid"
    label = "Taraudage rigide"
    category = "Cycles de perçage"
    description = "Taraudage synchronisé LinuxCNC G33.1 avec retour automatique."
    fields = (
        *POSITION_FIELDS,
        FieldSpec(
            "pitch",
            "Pas du taraud",
            1.25,
            section="Filetage",
            unit="mm/tr",
            minimum=0.05,
            maximum=20,
            decimals=3,
        ),
        FieldSpec(
            "direction",
            "Sens du taraudage",
            "right",
            section="Filetage",
            unit="",
            kind="choice",
            choices=(("right", "À droite"), ("left", "À gauche")),
        ),
    )
    common_fields = (
        CYCLE_COMMON_FIELDS[0],
        CYCLE_COMMON_FIELDS[1],
        CYCLE_COMMON_FIELDS[2],
        CYCLE_COMMON_FIELDS[4],
    )

    @classmethod
    def generate(cls, operation: OperationRecord, stock: Stock, tool: Tool) -> Toolpath:
        _start, final = _validate_depth(operation)
        builder = _builder(operation, tool)
        _position_cycle(builder, operation)
        builder.tap(
            final,
            float(operation.parameters["pitch"]),
            int(operation.parameters["spindle_rpm"]),
        )
        builder.retract()
        builder.result.spindle_direction = (
            "counterclockwise" if operation.parameters["direction"] == "left" else "clockwise"
        )
        builder.result.warnings.append(
            "Le taraudage G33.1 exige un codeur de broche avec signal d’index configuré dans LinuxCNC."
        )
        return builder.result


__all__ = [
    "DwellDrillingOperation",
    "PeckDrillingOperation",
    "ReamingOperation",
    "RigidTappingOperation",
    "SimpleDrillingOperation",
]
