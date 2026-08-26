"""Straight capsule slot pocket with roughing and a dedicated finish pass."""

from __future__ import annotations

from openmill.core.geometry import capsule_points, depth_levels, linear_positions
from openmill.core.models import OperationRecord, Stock, Tool, Toolpath
from openmill.core.registry import FieldSpec, OperationPlugin, registry


@registry.register
class StraightSlotOperation(OperationPlugin):
    id = "slot_straight"
    label = "Rainure droite"
    category = "Rainures"
    description = "Rainure oblongue orientable avec ébauche et finition des parois."
    fields = (
        FieldSpec("center_x", "Centre X", 60.0),
        FieldSpec("center_y", "Centre Y", 40.0),
        FieldSpec("length", "Longueur totale", 50.0, minimum=0.1),
        FieldSpec("width", "Largeur", 12.0, minimum=0.1),
        FieldSpec("rotation", "Orientation", 0.0, unit="°", minimum=-360, maximum=360),
        FieldSpec("step_over", "Engagement latéral", 45.0, unit="%", minimum=1, maximum=95),
        FieldSpec(
            "milling_direction",
            "Sens de fraisage",
            "climb",
            unit="",
            kind="choice",
            choices=(("climb", "Avalant"), ("conventional", "Opposition")),
            section="Stratégie",
        ),
        FieldSpec(
            "finish_pass",
            "Passe de finition",
            "enabled",
            unit="",
            kind="choice",
            choices=(("enabled", "Activée"), ("disabled", "Désactivée")),
            section="Finition",
        ),
        FieldSpec(
            "side_allowance",
            "Surépaisseur latérale",
            0.2,
            section="Finition",
            minimum=0,
        ),
    )

    @classmethod
    def generate(cls, operation: OperationRecord, stock: Stock, tool: Tool) -> Toolpath:
        parameters = operation.parameters
        length, width = float(parameters["length"]), float(parameters["width"])
        step_over = float(parameters["step_over"])
        allowance = float(parameters["side_allowance"])
        direction = str(parameters["milling_direction"])
        finish_mode = str(parameters["finish_pass"])
        if length < width:
            raise ValueError(
                "La longueur totale de la rainure doit être supérieure à sa largeur."
            )
        if width < tool.diameter:
            raise ValueError(
                f"La rainure est trop étroite pour l’outil Ø {tool.diameter:g} mm."
            )
        if not 0 < step_over <= 100:
            raise ValueError("L’engagement latéral doit être compris entre 0 et 100 %.")
        if allowance < 0:
            raise ValueError("La surépaisseur latérale ne peut pas être négative.")
        if direction not in {"climb", "conventional"}:
            raise ValueError("Le sens de fraisage est inconnu.")
        if finish_mode not in {"enabled", "disabled"}:
            raise ValueError("Le mode de finition est inconnu.")

        final_radius = (width - tool.diameter) / 2
        rough_radius = final_radius - allowance
        if rough_radius < 0:
            raise ValueError("La surépaisseur ne laisse aucune largeur usinable avec cet outil.")
        radii = linear_positions(rough_radius, 0.0, tool.diameter * step_over / 100)
        straight_length = length - width
        clockwise = direction == "conventional"  # Internal climb contours are counter-clockwise.
        center_x, center_y = float(parameters["center_x"]), float(parameters["center_y"])
        rotation = float(parameters["rotation"])
        levels = depth_levels(
            float(parameters["z_start"]),
            float(parameters["z_final"]),
            float(parameters["step_down"]),
        )
        builder = cls.builder(operation, tool)

        for level in levels:
            first = capsule_points(
                center_x,
                center_y,
                straight_length,
                radii[0],
                rotation_degrees=rotation,
                clockwise=clockwise,
            )
            builder.rapid(*first[0])
            builder.plunge(level)
            for radius in radii:
                builder.follow(
                    capsule_points(
                        center_x,
                        center_y,
                        straight_length,
                        radius,
                        rotation_degrees=rotation,
                        clockwise=clockwise,
                    )
                )
            builder.retract()

        if finish_mode == "enabled" and allowance > 1e-9:
            finish = capsule_points(
                center_x,
                center_y,
                straight_length,
                final_radius,
                rotation_degrees=rotation,
                clockwise=clockwise,
            )
            builder.rapid(*finish[0])
            builder.plunge(levels[-1])
            builder.follow(finish)
            builder.retract()
        return builder.result
