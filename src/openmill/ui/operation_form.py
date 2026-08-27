"""Declarative editor automatically generated from operation field specs."""

from __future__ import annotations

from openmill.ui.qt_core import Qt, pyqtSignal
from openmill.ui.qt_widgets import (
    QComboBox,
    QFrame,
    QLabel,
    QLineEdit,
    QScrollArea,
    QScroller,
    QVBoxLayout,
    QWidget,
)

from openmill.adapters.base import MachineAdapter
from openmill.core.models import OperationRecord, PlacementMode
from openmill.core.parameter_controls import uses_angle_dial, uses_percentage_slider
from openmill.core.registry import FieldSpec, registry
from openmill.ui.parameter_controls import AngleControl, PercentageControl, SegmentedChoice, TouchNumberControl


PLACEMENT_MODE = FieldSpec(
    "mode",
    "Mode d’appel",
    PlacementMode.SINGLE.value,
    unit="",
    kind="choice",
    choices=(
        (PlacementMode.SINGLE.value, "Unique"),
        (PlacementMode.LINEAR.value, "Ligne"),
        (PlacementMode.GRID.value, "Grille"),
        (PlacementMode.POLAR.value, "Cercle"),
    ),
    tip="Définis le cycle une fois, puis choisis où il doit être exécuté.",
)

LINEAR_PLACEMENT_FIELDS = (
    FieldSpec("start_x", "Première position X", 0.0),
    FieldSpec("start_y", "Première position Y", 0.0),
    FieldSpec("count", "Nombre de positions", 2, unit="", minimum=1, maximum=9999, kind="int"),
    FieldSpec("step_x", "Incrément X", 20.0),
    FieldSpec("step_y", "Incrément Y", 0.0),
    FieldSpec(
        "rotate_geometry",
        "Orienter le cycle dans le sens de la ligne",
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
        "Orienter aussi le cycle",
        "disabled",
        unit="",
        kind="choice",
        choices=(("disabled", "Non"), ("enabled", "Oui")),
    ),
)

POLAR_PLACEMENT_FIELDS = (
    FieldSpec("center_x", "Centre du motif X", 0.0),
    FieldSpec("center_y", "Centre du motif Y", 0.0),
    FieldSpec("diameter", "Diamètre de répartition", 60.0, minimum=0),
    FieldSpec("count", "Nombre de positions", 6, unit="", minimum=1, maximum=9999, kind="int"),
    FieldSpec("start_angle", "Angle de départ", 0.0, unit="°", minimum=-360, maximum=360),
    FieldSpec("sweep", "Angle de répartition", 360.0, unit="°", minimum=-360, maximum=360),
    FieldSpec(
        "rotate_geometry",
        "Tourner le cycle avec le motif",
        "disabled",
        unit="",
        kind="choice",
        choices=(("disabled", "Non"), ("enabled", "Oui")),
        tip="Utile pour orienter une rainure ou un profil dans le sens radial.",
    ),
)


class OperationForm(QWidget):
    operation_changed = pyqtSignal()

    def __init__(self, adapter: MachineAdapter, parent=None) -> None:
        super().__init__(parent)
        self._adapter = adapter
        self._operation: OperationRecord | None = None
        self._loading = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        self._heading = QLabel("Paramètres")
        self._heading.setObjectName("brand")
        layout.addWidget(self._heading)
        self._description = QLabel("Sélectionne une opération pour modifier ses paramètres.")
        self._description.setWordWrap(True)
        self._description.setObjectName("muted")
        layout.addWidget(self._description)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        QScroller.grabGesture(self._scroll.viewport(), QScroller.LeftMouseButtonGesture)
        self._content = QWidget()
        self._form = QVBoxLayout(self._content)
        self._form.setContentsMargins(1, 6, 4, 12)
        self._form.setSpacing(8)
        self._scroll.setWidget(self._content)
        layout.addWidget(self._scroll, 1)

    def set_operation(self, operation: OperationRecord | None) -> None:
        self._loading = True
        self._operation = operation
        while self._form.count():
            item = self._form.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

        if operation is None:
            self._heading.setText("Paramètres")
            self._description.setText("Sélectionne une opération pour modifier ses paramètres.")
            self._loading = False
            return

        plugin = registry.get(operation.plugin_id)
        self._heading.setText(plugin.label)
        self._description.setText(plugin.description)
        title = QLineEdit(operation.title)
        title.setMinimumHeight(40)
        title.textChanged.connect(self._title_changed)
        self._add_parameter("Nom de l’étape", title)
        tools = QComboBox()
        tools.setMinimumHeight(41)
        for tool in self._adapter.get_tools():
            tools.addItem(f"T{tool.number}  ·  Ø {tool.diameter:g} mm  ·  {tool.name}", tool.number)
        selected_tool = tools.findData(operation.tool_number)
        if selected_tool >= 0:
            tools.setCurrentIndex(selected_tool)
        tools.currentIndexChanged.connect(lambda _index: self._tool_changed(tools.currentData()))
        self._add_parameter("Outil", tools)

        current_section = ""
        for specification in plugin.all_fields():
            if specification.section != current_section:
                current_section = specification.section
                section = QLabel(current_section.upper())
                section.setObjectName("section")
                self._form.addWidget(section)
            self._add_parameter(specification.label, self._create_field(specification, operation), specification.tip)
        self._add_placement_editor(operation)
        self._form.addStretch()
        self._loading = False

    def focus_placement(self) -> None:
        self._scroll.verticalScrollBar().setValue(self._scroll.verticalScrollBar().maximum())

    def _add_placement_editor(self, operation: OperationRecord) -> None:
        section = QLabel("PLACEMENT / RÉPÉTITION")
        section.setObjectName("section")
        self._form.addWidget(section)
        summary = QLabel(
            "Comme sur une commande conversationnelle : le cycle reste unique, "
            "puis OpenMill l’appelle sur le motif choisi."
        )
        summary.setWordWrap(True)
        summary.setObjectName("muted")
        self._form.addWidget(summary)
        self._add_parameter(
            PLACEMENT_MODE.label,
            self._create_placement_field(PLACEMENT_MODE, operation),
            PLACEMENT_MODE.tip,
        )
        fields = {
            PlacementMode.SINGLE: (),
            PlacementMode.LINEAR: LINEAR_PLACEMENT_FIELDS,
            PlacementMode.GRID: GRID_PLACEMENT_FIELDS,
            PlacementMode.POLAR: POLAR_PLACEMENT_FIELDS,
        }[operation.placement.mode]
        for specification in fields:
            self._add_parameter(
                specification.label,
                self._create_placement_field(specification, operation),
                specification.tip,
            )

    def _add_parameter(self, label: str, control: QWidget, tip: str = "") -> None:
        card = QFrame()
        card.setObjectName("parameterCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(9, 7, 9, 8)
        layout.setSpacing(5)
        heading = QLabel(label)
        heading.setObjectName("parameterLabel")
        if tip:
            heading.setToolTip(tip)
            control.setToolTip(tip)
        layout.addWidget(heading)
        layout.addWidget(control)
        self._form.addWidget(card)

    def _create_field(self, specification: FieldSpec, operation: OperationRecord) -> QWidget:
        value = operation.parameters.get(specification.key, specification.default)
        return self._create_control(
            specification,
            value,
            lambda current, key=specification.key: self._parameter_changed(key, current),
        )

    def _create_placement_field(self, specification: FieldSpec, operation: OperationRecord) -> QWidget:
        value = getattr(operation.placement, specification.key)
        if specification.key in {"serpentine", "rotate_geometry"}:
            value = "enabled" if value else "disabled"
        if specification.key == "mode":
            value = value.value
        return self._create_control(
            specification,
            value,
            lambda current, key=specification.key: self._placement_changed(key, current),
        )

    def _create_control(self, specification: FieldSpec, value, callback) -> QWidget:
        if specification.kind == "choice":
            field = SegmentedChoice(specification, value)
        elif uses_angle_dial(specification):
            field = AngleControl(specification, float(value))
        elif uses_percentage_slider(specification):
            field = PercentageControl(specification, float(value))
        else:
            field = TouchNumberControl(specification, value)
        field.value_changed.connect(callback)
        if specification.tip:
            field.setToolTip(specification.tip)
        return field

    def _title_changed(self, title: str) -> None:
        if self._operation is not None and not self._loading:
            self._operation.title = title.strip() or "Opération"
            self.operation_changed.emit()

    def _tool_changed(self, tool_number: int | None) -> None:
        if self._operation is not None and tool_number is not None and not self._loading:
            self._operation.tool_number = tool_number
            self.operation_changed.emit()

    def _parameter_changed(self, key: str, value) -> None:
        if self._operation is not None and not self._loading:
            self._operation.parameters[key] = value
            self.operation_changed.emit()

    def _placement_changed(self, key: str, value) -> None:
        if self._operation is None or self._loading:
            return
        if key == "mode":
            self._operation.placement.mode = PlacementMode(value)
        elif key in {"serpentine", "rotate_geometry"}:
            setattr(self._operation.placement, key, value == "enabled")
        elif key in {"count", "columns", "rows"}:
            setattr(self._operation.placement, key, int(value))
        else:
            setattr(self._operation.placement, key, float(value))
        operation = self._operation
        if key == "mode":
            self.set_operation(operation)
            self.focus_placement()
        self.operation_changed.emit()
