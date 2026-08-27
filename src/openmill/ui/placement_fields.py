"""Declarative controls shared by the first-class repetition editor."""

from openmill.core.models import PlacementMode, RepetitionOrder
from openmill.core.registry import FieldSpec


PLACEMENT_MODE = FieldSpec(
    "mode",
    "Type de répétition",
    PlacementMode.SINGLE.value,
    unit="",
    kind="choice",
    choices=(
        (PlacementMode.SINGLE.value, "Unique"),
        (PlacementMode.LINEAR.value, "Ligne"),
        (PlacementMode.GRID.value, "Grille"),
        (PlacementMode.POLAR.value, "Cercle"),
    ),
    tip="Le motif est indépendant des opérations qu’il contient.",
)

EXECUTION_ORDER = FieldSpec(
    "execution_order",
    "Ordre d’usinage",
    RepetitionOrder.BY_POSITION.value,
    unit="",
    kind="choice",
    choices=(
        (RepetitionOrder.BY_POSITION.value, "Par position"),
        (RepetitionOrder.BY_OPERATION.value, "Par opération"),
    ),
    tip=(
        "Par position : toutes les opérations à chaque emplacement. "
        "Par opération : une opération sur tous les emplacements avant la suivante."
    ),
)

LINEAR_PLACEMENT_FIELDS = (
    FieldSpec("start_x", "Première position X", 0.0),
    FieldSpec("start_y", "Première position Y", 0.0),
    FieldSpec("count", "Nombre de positions", 2, unit="", minimum=1, maximum=9999, kind="int"),
    FieldSpec("step_x", "Incrément X", 20.0),
    FieldSpec("step_y", "Incrément Y", 0.0),
    FieldSpec(
        "rotate_geometry",
        "Orienter les opérations dans le sens de la ligne",
        "disabled",
        unit="",
        kind="choice",
        choices=(("disabled", "Non"), ("enabled", "Oui")),
    ),
)

GRID_PLACEMENT_FIELDS = (
    FieldSpec("start_x", "Première position X", 0.0),
    FieldSpec("start_y", "Première position Y", 0.0),
    FieldSpec("columns", "Colonnes", 2, unit="", minimum=1, maximum=999, kind="int"),
    FieldSpec("rows", "Rangées", 2, unit="", minimum=1, maximum=999, kind="int"),
    FieldSpec("spacing_x", "Pas entre colonnes", 20.0),
    FieldSpec("spacing_y", "Pas entre rangées", 20.0),
    FieldSpec("grid_angle", "Orientation de la grille", 0.0, unit="°", minimum=-360, maximum=360),
    FieldSpec(
        "serpentine",
        "Ordre en zigzag",
        "enabled",
        unit="",
        kind="choice",
        choices=(("enabled", "Oui"), ("disabled", "Non")),
        tip="Évite un retour rapide inutile au début de chaque rangée.",
    ),
    FieldSpec(
        "rotate_geometry",
        "Orienter aussi les opérations",
        "disabled",
        unit="",
        kind="choice",
        choices=(("disabled", "Non"), ("enabled", "Oui")),
    ),
)

POLAR_PLACEMENT_FIELDS = (
    FieldSpec("center_x", "Centre du cercle X", 0.0),
    FieldSpec("center_y", "Centre du cercle Y", 0.0),
    FieldSpec("diameter", "Diamètre de répartition", 60.0, minimum=0),
    FieldSpec("count", "Nombre de positions", 6, unit="", minimum=1, maximum=9999, kind="int"),
    FieldSpec("start_angle", "Angle de départ", 0.0, unit="°", minimum=-360, maximum=360),
    FieldSpec("sweep", "Angle de répartition", 360.0, unit="°", minimum=-360, maximum=360),
    FieldSpec(
        "rotate_geometry",
        "Tourner les opérations avec le cercle",
        "disabled",
        unit="",
        kind="choice",
        choices=(("disabled", "Non"), ("enabled", "Oui")),
        tip="Utile pour orienter une rainure ou un profil dans le sens radial.",
    ),
)


PLACEMENT_FIELDS = {
    PlacementMode.SINGLE: (),
    PlacementMode.LINEAR: LINEAR_PLACEMENT_FIELDS,
    PlacementMode.GRID: GRID_PLACEMENT_FIELDS,
    PlacementMode.POLAR: POLAR_PLACEMENT_FIELDS,
}

