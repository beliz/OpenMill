"""Declarative editor automatically generated from operation field specs."""

from __future__ import annotations

from openmill.ui.qt_core import Qt, pyqtSignal
from openmill.ui.qt_widgets import (
    QComboBox,
    QFrame,
    QGridLayout,
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
from openmill.ui.parameter_controls import (
    AngleControl,
    PercentageControl,
    SegmentedChoice,
    TouchNumberControl,
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
        calculation_hint = QLabel(
            "Astuce · calculs acceptés : 120/2, 40+5, 12*3 et parenthèses."
        )
        calculation_hint.setObjectName("muted")
        layout.addWidget(calculation_hint)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        QScroller.grabGesture(self._scroll.viewport(), QScroller.LeftMouseButtonGesture)
        self._content = QWidget()
        self._form = QGridLayout(self._content)
        self._form.setContentsMargins(1, 8, 5, 14)
        self._form.setHorizontalSpacing(10)
        self._form.setVerticalSpacing(10)
        self._form.setColumnStretch(0, 1)
        self._form.setColumnStretch(1, 1)
        self._scroll.setWidget(self._content)
        layout.addWidget(self._scroll, 1)

    def set_operation(self, operation: OperationRecord | None) -> None:
        self._loading = True
        self._operation = operation
        self._grid_row = 0
        self._grid_column = 0
        for row in range(self._form.rowCount()):
            self._form.setRowStretch(row, 0)
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
            tools.addItem(
                f"T{tool.number}  ·  Ø {tool.diameter:g} mm  ·  {tool.name}",
                tool.number,
            )
        selected_tool = tools.findData(operation.tool_number)
        if selected_tool >= 0:
            tools.setCurrentIndex(selected_tool)
        tools.currentIndexChanged.connect(lambda _index: self._tool_changed(tools.currentData()))
        self._add_parameter("Outil", tools)

        current_section = ""
        for specification in plugin.all_fields():
            if specification.section != current_section:
                current_section = specification.section
                self._add_section(current_section.upper())
            wide = (
                specification.kind == "choice" and len(specification.choices) >= 3
            ) or uses_angle_dial(specification)
            placement_driven = (
                specification.key in {"center_x", "center_y"}
                and operation.placement.mode is not PlacementMode.SINGLE
            )
            control = self._create_field(specification, operation)
            if placement_driven:
                control.setEnabled(False)
            self._add_parameter(
                specification.label,
                control,
                (
                    f"Piloté par le bloc {operation.placement.label}. "
                    "La coordonnée de l’opération n’est pas utilisée."
                    if placement_driven
                    else specification.tip
                ),
                wide=wide,
                disabled=placement_driven,
            )
        self._finish_grid_row()
        self._form.setRowStretch(self._grid_row, 1)
        self._loading = False

    def _add_section(self, title: str) -> None:
        self._finish_grid_row()
        section = QLabel(title)
        section.setObjectName("section")
        self._form.addWidget(section, self._grid_row, 0, 1, 2)
        self._grid_row += 1

    def _add_parameter(
        self,
        label: str,
        control: QWidget,
        tip: str = "",
        *,
        wide: bool = False,
        disabled: bool = False,
    ) -> None:
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
        if disabled:
            card.setProperty("placementDriven", True)
            card.setToolTip(tip)
        if wide:
            self._finish_grid_row()
            self._form.addWidget(card, self._grid_row, 0, 1, 2)
            self._grid_row += 1
            return
        self._form.addWidget(card, self._grid_row, self._grid_column)
        self._grid_column += 1
        if self._grid_column == 2:
            self._grid_column = 0
            self._grid_row += 1

    def _finish_grid_row(self) -> None:
        if self._grid_column:
            self._grid_column = 0
            self._grid_row += 1

    def _create_field(self, specification: FieldSpec, operation: OperationRecord) -> QWidget:
        value = operation.parameters.get(specification.key, specification.default)
        return self._create_control(
            specification,
            value,
            lambda current, key=specification.key: self._parameter_changed(key, current),
            expression=operation.expressions.get(specification.key, ""),
            expression_callback=lambda current, key=specification.key: self._expression_changed(
                key, current
            ),
        )

    def _create_control(
        self,
        specification: FieldSpec,
        value,
        callback,
        *,
        expression: str = "",
        expression_callback=None,
    ) -> QWidget:
        if specification.kind == "choice":
            field = SegmentedChoice(specification, value)
        elif uses_angle_dial(specification):
            field = AngleControl(specification, float(value), expression=expression)
        elif uses_percentage_slider(specification):
            field = PercentageControl(specification, float(value), expression=expression)
        else:
            field = TouchNumberControl(specification, value, expression=expression)
        field.value_changed.connect(callback)
        if expression_callback is not None and hasattr(field, "expression_changed"):
            field.expression_changed.connect(expression_callback)
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

    def _expression_changed(self, key: str, expression: str) -> None:
        if self._operation is None or self._loading:
            return
        if expression:
            self._operation.expressions[key] = expression
        else:
            self._operation.expressions.pop(key, None)
        self.operation_changed.emit()
