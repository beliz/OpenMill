"""Wide editor for a first-class repetition block."""

from __future__ import annotations

from openmill.core.models import PlacementMode, RepetitionBlock, RepetitionOrder
from openmill.core.parameter_controls import uses_angle_dial, uses_percentage_slider
from openmill.core.registry import FieldSpec
from openmill.ui.parameter_controls import (
    AngleControl,
    PercentageControl,
    SegmentedChoice,
    TouchNumberControl,
)
from openmill.ui.placement_fields import EXECUTION_ORDER, PLACEMENT_FIELDS, PLACEMENT_MODE
from openmill.ui.qt_core import Qt, pyqtSignal
from openmill.ui.qt_widgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QScrollArea,
    QScroller,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class RepetitionForm(QWidget):
    repetition_changed = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._repetition: RepetitionBlock | None = None
        self._loading = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        self._heading = QLabel("Répétition")
        self._heading.setObjectName("brand")
        layout.addWidget(self._heading)
        self._description = QLabel(
            "Définis où et dans quel ordre les opérations imbriquées seront exécutées."
        )
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
        self._form.setContentsMargins(1, 10, 5, 14)
        self._form.setHorizontalSpacing(10)
        self._form.setVerticalSpacing(10)
        self._form.setColumnStretch(0, 1)
        self._form.setColumnStretch(1, 1)
        self._scroll.setWidget(self._content)
        layout.addWidget(self._scroll, 1)

    def set_repetition(self, repetition: RepetitionBlock | None) -> None:
        self._loading = True
        self._repetition = repetition
        for row in range(self._form.rowCount()):
            self._form.setRowStretch(row, 0)
        while self._form.count():
            item = self._form.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        if repetition is None:
            self._heading.setText("Répétition")
            self._loading = False
            return
        self._heading.setText(repetition.title)
        row = 0
        self._form.addWidget(
            self._card(PLACEMENT_MODE, self._placement_control(PLACEMENT_MODE, repetition)),
            row,
            0,
            1,
            2,
        )
        row += 1
        self._form.addWidget(
            self._card(EXECUTION_ORDER, self._order_control(repetition)),
            row,
            0,
            1,
            2,
        )
        row += 1
        for index, specification in enumerate(PLACEMENT_FIELDS[repetition.placement.mode]):
            self._form.addWidget(
                self._card(specification, self._placement_control(specification, repetition)),
                row + index // 2,
                index % 2,
            )
        stretch_row = row + (len(PLACEMENT_FIELDS[repetition.placement.mode]) + 1) // 2
        self._form.setRowStretch(stretch_row, 1)
        self._loading = False

    def _card(self, specification: FieldSpec, control: QWidget) -> QFrame:
        card = QFrame()
        card.setObjectName("parameterCard")
        card.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        control.setSizePolicy(QSizePolicy.Ignored, control.sizePolicy().verticalPolicy())
        layout = QVBoxLayout(card)
        layout.setContentsMargins(11, 9, 11, 10)
        layout.setSpacing(6)
        heading = QLabel(specification.label)
        heading.setObjectName("parameterLabel")
        if specification.tip:
            heading.setToolTip(specification.tip)
            control.setToolTip(specification.tip)
        layout.addWidget(heading)
        layout.addWidget(control)
        return card

    def _control(
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
        return field

    def _placement_control(self, specification: FieldSpec, repetition: RepetitionBlock) -> QWidget:
        value = getattr(repetition.placement, specification.key)
        if specification.key in {"serpentine", "rotate_geometry"}:
            value = "enabled" if value else "disabled"
        elif specification.key == "mode":
            value = value.value
        return self._control(
            specification,
            value,
            lambda current, key=specification.key: self._placement_changed(key, current),
            expression=repetition.expressions.get(specification.key, ""),
            expression_callback=lambda current, key=specification.key: self._expression_changed(
                key, current
            ),
        )

    def _order_control(self, repetition: RepetitionBlock) -> QWidget:
        return self._control(
            EXECUTION_ORDER,
            repetition.execution_order.value,
            self._order_changed,
        )

    def _order_changed(self, value: str) -> None:
        if self._repetition is not None and not self._loading:
            self._repetition.execution_order = RepetitionOrder(value)
            self.repetition_changed.emit()

    def _placement_changed(self, key: str, value) -> None:
        if self._repetition is None or self._loading:
            return
        if key == "mode":
            self._repetition.placement.mode = PlacementMode(value)
        elif key in {"serpentine", "rotate_geometry"}:
            setattr(self._repetition.placement, key, value == "enabled")
        elif key in {"count", "columns", "rows"}:
            setattr(self._repetition.placement, key, int(value))
        else:
            setattr(self._repetition.placement, key, float(value))
        repetition = self._repetition
        if key == "mode":
            self.set_repetition(repetition)
        self.repetition_changed.emit()

    def _expression_changed(self, key: str, expression: str) -> None:
        if self._repetition is None or self._loading:
            return
        if expression:
            self._repetition.expressions[key] = expression
        else:
            self._repetition.expressions.pop(key, None)
        self.repetition_changed.emit()
