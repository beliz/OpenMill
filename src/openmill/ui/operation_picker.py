"""Touch-oriented operation gallery with crisp procedural machining diagrams."""

from __future__ import annotations

import math

from openmill.ui.qt_core import QPointF, QRectF, QSize, Qt, QTimer
from openmill.ui.qt_gui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF
from openmill.ui.qt_widgets import (
    QApplication,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QScroller,
    QVBoxLayout,
    QWidget,
)

from openmill.core.registry import OperationPlugin, registry


CATEGORY_COLORS = {
    "Préparation": "#57d7a8",
    "Poches": "#62c6ff",
    "Profils": "#b69cff",
    "Rainures": "#ff8fa3",
    "Perçage": "#ffbf69",
}


def _line(painter: QPainter, color: QColor, width: float = 2.0, dashed: bool = False) -> None:
    painter.setPen(QPen(color, width, Qt.DashLine if dashed else Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))


def draw_operation_diagram(painter: QPainter, bounds: QRectF, plugin_id: str, accent: QColor) -> None:
    """Draw a recognizable operation schema without bitmap assets or SVG dependencies."""
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    plate = bounds.adjusted(bounds.width() * 0.12, 9, -bounds.width() * 0.12, -9)
    plate.setWidth(max(plate.width(), 1))
    plate.setHeight(max(plate.height(), 1))
    background = QLinearGradient(plate.topLeft(), plate.bottomRight())
    background.setColorAt(0, QColor("#243346"))
    background.setColorAt(1, QColor("#131d2b"))
    painter.setBrush(QBrush(background))
    painter.setPen(QPen(QColor("#466078"), 1.2))
    painter.drawRoundedRect(plate, 8, 8)

    bright = QColor(accent)
    muted = QColor(accent)
    muted.setAlpha(105)
    center = plate.center()

    if plugin_id == "facing":
        path = QPainterPath()
        left, right = plate.left() + 12, plate.right() - 12
        for row in range(5):
            y = plate.top() + 11 + row * (plate.height() - 22) / 4
            if row == 0:
                path.moveTo(left, y)
            else:
                path.lineTo(left if row % 2 == 0 else right, y)
            path.lineTo(right if row % 2 == 0 else left, y)
        _line(painter, muted, 8)
        painter.drawPath(path)
        _line(painter, bright, 1.8)
        painter.drawPath(path)
        painter.setBrush(bright)
        painter.drawEllipse(QPointF(right, plate.top() + 11), 4.5, 4.5)

    elif plugin_id in {"pocket_rectangle", "profile_rectangle"}:
        for index in range(4):
            inset = 11 + index * min(plate.width(), plate.height()) * 0.085
            ring = plate.adjusted(inset, inset * 0.72, -inset, -inset * 0.72)
            if ring.width() <= 2 or ring.height() <= 2:
                break
            _line(painter, bright if index == 0 else muted, 2 if index == 0 else 1.4)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(ring, max(2, 9 - index * 2), max(2, 9 - index * 2))

    elif plugin_id in {"pocket_circle", "profile_circle"}:
        radius = min(plate.width(), plate.height()) * 0.35
        for index in range(5):
            ring = radius * (1 - index * 0.19)
            _line(painter, bright if index == 0 else muted, 2 if index == 0 else 1.4)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(center, ring, ring)

    elif plugin_id in {"hexagon", "profile_polygon"}:
        radius = min(plate.width(), plate.height()) * 0.36
        sides = 5 if plugin_id == "profile_polygon" else 6
        for index in range(3):
            size = radius * (1 - index * 0.23)
            polygon = QPolygonF(
                [
                    QPointF(
                        center.x() + size * math.cos(math.radians(30 + vertex * 360 / sides)),
                        center.y() + size * math.sin(math.radians(30 + vertex * 360 / sides)),
                    )
                    for vertex in range(sides)
                ]
            )
            _line(painter, bright if index == 0 else muted, 2 if index == 0 else 1.3)
            painter.setBrush(Qt.NoBrush)
            painter.drawPolygon(polygon)

    elif plugin_id == "slot_straight":
        slot = plate.adjusted(16, plate.height() * 0.27, -16, -plate.height() * 0.27)
        radius = slot.height() / 2
        for index in range(3):
            inset = index * radius * 0.28
            current = slot.adjusted(inset, inset, -inset, -inset)
            if current.height() <= 1:
                break
            _line(painter, bright if index == 0 else muted, 2 if index == 0 else 1.3)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(current, current.height() / 2, current.height() / 2)

    elif plugin_id == "drill_circle":
        radius = min(plate.width(), plate.height()) * 0.31
        _line(painter, muted, 1.1, dashed=True)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(center, radius, radius)
        for index in range(8):
            angle = math.tau * index / 8
            position = QPointF(center.x() + radius * math.cos(angle), center.y() + radius * math.sin(angle))
            painter.setPen(QPen(bright, 1.2))
            painter.setBrush(QColor(11, 16, 26, 235))
            painter.drawEllipse(position, 4, 4)
            painter.setBrush(bright)
            painter.drawEllipse(position, 1.2, 1.2)

    elif plugin_id == "drill_grid":
        for row in range(3):
            for column in range(4):
                x = plate.left() + plate.width() * (0.20 + column * 0.20)
                y = plate.top() + plate.height() * (0.24 + row * 0.26)
                position = QPointF(x, y)
                painter.setPen(QPen(bright, 1.2))
                painter.setBrush(QColor(11, 16, 26, 235))
                painter.drawEllipse(position, 4, 4)
                painter.setBrush(bright)
                painter.drawEllipse(position, 1.2, 1.2)

    else:
        _line(painter, muted, 7)
        painter.drawLine(
            QPointF(plate.left() + 16, plate.bottom() - 15),
            QPointF(plate.right() - 16, plate.top() + 15),
        )
        _line(painter, bright, 2)
        painter.drawLine(
            QPointF(plate.left() + 16, plate.bottom() - 15),
            QPointF(plate.right() - 16, plate.top() + 15),
        )
        painter.setBrush(bright)
        painter.drawEllipse(QPointF(plate.right() - 16, plate.top() + 15), 5, 5)

    painter.restore()


class OperationTile(QPushButton):
    """Large keyboard- and touch-accessible card painted as one click target."""

    def __init__(self, plugin: type[OperationPlugin], parent=None) -> None:
        super().__init__(parent)
        self.plugin = plugin
        self._accent = QColor(CATEGORY_COLORS.get(plugin.category, "#57d7a8"))
        self.setMinimumSize(215, 195)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName(plugin.label)
        self.setAccessibleDescription(plugin.description)
        self.setToolTip(plugin.description)
        self.setMouseTracking(True)

    def sizeHint(self) -> QSize:
        return QSize(255, 205)

    def enterEvent(self, event) -> None:
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        bounds = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        hovering = self.underMouse() or self.hasFocus()
        background = QColor("#172333" if hovering else "#111b29")
        if self.isDown():
            background = QColor("#19362f")
        border = QColor(self._accent if hovering or self.isDown() else QColor("#29394e"))
        painter.setBrush(background)
        painter.setPen(QPen(border, 1.7 if hovering or self.isDown() else 1.0))
        painter.drawRoundedRect(bounds, 12, 12)

        artwork = QRectF(12, 10, self.width() - 24, min(110, self.height() * 0.54))
        draw_operation_diagram(painter, artwork, self.plugin.id, self._accent)

        title_font = QFont("Segoe UI", 10)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(QColor("#f0f5fc"))
        title_top = artwork.bottom() + 7
        painter.drawText(
            QRectF(14, title_top, self.width() - 28, 38),
            Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap,
            self.plugin.label,
        )

        description_font = QFont("Segoe UI", 8)
        painter.setFont(description_font)
        painter.setPen(QColor("#96a7bc"))
        painter.drawText(
            QRectF(14, title_top + 39, self.width() - 28, max(self.height() - title_top - 44, 19)),
            Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap,
            self.plugin.description,
        )


class OperationPickerDialog(QDialog):
    """Searchable categorized visual catalog tailored for CNC touchscreens."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("operationPicker")
        self.setWindowTitle("Ajouter une étape d’usinage")
        self.setModal(True)
        self.setMinimumSize(650, 510)
        self.resize(1000, 780)
        self.selected_plugin_id: str | None = None
        self._last_columns = 0

        if parent is not None:
            screen = QApplication.screenAt(parent.mapToGlobal(parent.rect().center()))
            if screen is not None:
                available = screen.availableGeometry()
                self.resize(min(1030, int(available.width() * 0.87)), min(830, int(available.height() * 0.86)))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(23, 19, 23, 19)
        outer.setSpacing(13)
        heading = QHBoxLayout()
        labels = QVBoxLayout()
        title = QLabel("Ajouter une étape")
        title.setObjectName("dialogTitle")
        labels.addWidget(title)
        subtitle = QLabel("Choisis la géométrie que tu souhaites usiner.")
        subtitle.setObjectName("muted")
        labels.addWidget(subtitle)
        heading.addLayout(labels, 1)
        close = QPushButton("✕")
        close.setFixedSize(46, 46)
        close.setAccessibleName("Fermer")
        close.clicked.connect(self.reject)
        heading.addWidget(close)
        outer.addLayout(heading)

        self._search = QLineEdit()
        self._search.setObjectName("operationSearch")
        self._search.setPlaceholderText("Rechercher : poche, hexagone, perçage…")
        self._search.setClearButtonEnabled(True)
        self._search.setMinimumHeight(47)
        self._search.textChanged.connect(self._rebuild_sections)
        outer.addWidget(self._search)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        QScroller.grabGesture(self._scroll.viewport(), QScroller.LeftMouseButtonGesture)
        self._content = QWidget()
        self._sections = QVBoxLayout(self._content)
        self._sections.setContentsMargins(1, 3, 7, 12)
        self._sections.setSpacing(16)
        self._scroll.setWidget(self._content)
        outer.addWidget(self._scroll, 1)
        self._rebuild_sections()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "_scroll"):
            QTimer.singleShot(0, self._refresh_columns)

    def _column_count(self) -> int:
        available = max(self._scroll.viewport().width() - 20, 220)
        return min(4, max(1, available // 240))

    def _refresh_columns(self) -> None:
        if self._last_columns != self._column_count():
            self._rebuild_sections()

    def _rebuild_sections(self, _text: str | None = None) -> None:
        while self._sections.count():
            item = self._sections.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

        search = self._search.text().strip().casefold()
        columns = self._column_count()
        self._last_columns = columns
        visible_count = 0
        for category, plugins in registry.grouped().items():
            matching = [
                plugin
                for plugin in plugins
                if not search
                or search in plugin.label.casefold()
                or search in plugin.description.casefold()
                or search in category.casefold()
            ]
            if not matching:
                continue

            section = QFrame()
            layout = QVBoxLayout(section)
            layout.setContentsMargins(1, 0, 1, 0)
            layout.setSpacing(9)
            title = QLabel(f"{category.upper()}  ·  {len(matching)}")
            title.setObjectName("pickerCategory")
            layout.addWidget(title)
            cards = QGridLayout()
            cards.setHorizontalSpacing(11)
            cards.setVerticalSpacing(11)
            for index, plugin in enumerate(matching):
                tile = OperationTile(plugin)
                tile.clicked.connect(lambda _checked=False, plugin_id=plugin.id: self._choose(plugin_id))
                cards.addWidget(tile, index // columns, index % columns)
                visible_count += 1
            for column in range(columns):
                cards.setColumnStretch(column, 1)
            layout.addLayout(cards)
            self._sections.addWidget(section)

        if not visible_count:
            empty = QLabel("Aucune opération ne correspond à cette recherche.")
            empty.setAlignment(Qt.AlignCenter)
            empty.setObjectName("muted")
            empty.setMinimumHeight(140)
            self._sections.addWidget(empty)
        self._sections.addStretch()

    def _choose(self, plugin_id: str) -> None:
        self.selected_plugin_id = plugin_id
        self.accept()
