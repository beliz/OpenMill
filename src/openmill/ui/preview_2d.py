"""Fast vector preview projected on the XY, XZ or YZ plane."""

from __future__ import annotations

import math

from openmill.ui.qt_core import QPointF, QRectF, Qt
from openmill.ui.qt_gui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from openmill.ui.qt_widgets import QGraphicsEllipseItem, QGraphicsPathItem, QGraphicsScene, QGraphicsView

from openmill.core.engine import BuildResult
from openmill.core.models import MotionKind, Point, Project
from openmill.ui.theme import OPERATION_COLORS


class VectorPreview(QGraphicsView):
    """The scene uses millimetres; only the vertical display axis is flipped."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setMinimumSize(160, 120)
        self._plane = "XY"
        self._bounds = QRectF(-10, -10, 120, 100)

    def wheelEvent(self, event) -> None:
        self.scale(1.16 if event.angleDelta().y() > 0 else 1 / 1.16, 1.16 if event.angleDelta().y() > 0 else 1 / 1.16)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.fitInView(self._bounds, Qt.KeepAspectRatio)

    def reset_view(self) -> None:
        self.fitInView(self._bounds, Qt.KeepAspectRatio)

    def _project(self, point: Point) -> QPointF:
        first, second = (
            (point.x, point.y)
            if self._plane == "XY"
            else (point.x, point.z)
            if self._plane == "XZ"
            else (point.y, point.z)
        )
        return QPointF(first, -second)

    def _add_label(self, text: str, x: float, y: float, *, color: str = "#93a3bb") -> None:
        label = self._scene.addSimpleText(text, QFont("Segoe UI", 8))
        label.setBrush(QColor(color))
        label.setFlag(label.ItemIgnoresTransformations)
        label.setPos(x, y)
        label.setZValue(20)

    def set_content(
        self,
        project: Project,
        result: BuildResult,
        *,
        selected_uid: str | None = None,
        plane: str = "XY",
    ) -> None:
        self._plane = plane
        self._scene.clear()
        stock = project.stock
        if plane == "XY":
            low_x, high_x, low_y, high_y = stock.x_min, stock.x_max, stock.y_min, stock.y_max
        elif plane == "XZ":
            low_x, high_x, low_y, high_y = stock.x_min, stock.x_max, stock.z_min, stock.z_max
        else:
            low_x, high_x, low_y, high_y = stock.y_min, stock.y_max, stock.z_min, stock.z_max

        diameter = max(high_x - low_x, high_y - low_y, 20)
        margin = max(diameter * 0.16, 12)
        self._bounds = QRectF(low_x - margin, -high_y - margin, high_x - low_x + margin * 2, high_y - low_y + margin * 2)
        self._scene.setSceneRect(self._bounds)
        grid_step = 10 if diameter <= 180 else 20 if diameter <= 400 else 50
        first_x = math.floor(self._bounds.left() / grid_step) * grid_step
        last_x = math.ceil(self._bounds.right() / grid_step) * grid_step
        first_y = math.floor(self._bounds.top() / grid_step) * grid_step
        last_y = math.ceil(self._bounds.bottom() / grid_step) * grid_step
        grid_pen = QPen(QColor("#172133"), 0)
        for x in range(int(first_x), int(last_x) + 1, grid_step):
            line = self._scene.addLine(x, self._bounds.top(), x, self._bounds.bottom(), grid_pen)
            line.setZValue(-10)
        for y in range(int(first_y), int(last_y) + 1, grid_step):
            line = self._scene.addLine(self._bounds.left(), y, self._bounds.right(), y, grid_pen)
            line.setZValue(-10)

        rectangle = QRectF(low_x, -high_y, high_x - low_x, high_y - low_y)
        gradient = QLinearGradient(rectangle.topLeft(), rectangle.bottomRight())
        gradient.setColorAt(0, QColor(55, 78, 103, 145))
        gradient.setColorAt(1, QColor(37, 53, 72, 175))
        stock_item = self._scene.addRect(rectangle, QPen(QColor("#7890ac"), 0), QBrush(gradient))
        stock_item.setZValue(-5)

        for index, toolpath in enumerate(result.toolpaths):
            color = QColor(OPERATION_COLORS[index % len(OPERATION_COLORS)])
            active = selected_uid is None or selected_uid == toolpath.operation_uid
            for motion in toolpath.motions:
                start, end = self._project(motion.start), self._project(motion.end)
                if motion.kind is MotionKind.RAPID:
                    rapid_color = QColor("#a1b3c9")
                    rapid_color.setAlpha(115 if active else 35)
                    pen = QPen(rapid_color, 0)
                    pen.setStyle(Qt.DashLine)
                    item = self._scene.addLine(start.x(), start.y(), end.x(), end.y(), pen)
                    item.setZValue(1)
                    continue

                distance = math.hypot(end.x() - start.x(), end.y() - start.y())
                body_color = QColor(color)
                body_color.setAlpha(120 if active else 42)
                if distance <= 1e-7:
                    radius = toolpath.tool.diameter / 2
                    point = QGraphicsEllipseItem(end.x() - radius, end.y() - radius, radius * 2, radius * 2)
                    point.setBrush(body_color)
                    point.setPen(QPen(color if active else body_color, 0))
                    point.setZValue(4)
                    self._scene.addItem(point)
                    continue

                path = QPainterPath(start)
                path.lineTo(end)
                body = QGraphicsPathItem(path)
                pen = QPen(body_color, toolpath.tool.diameter)
                pen.setCapStyle(Qt.RoundCap)
                pen.setJoinStyle(Qt.RoundJoin)
                body.setPen(pen)
                body.setZValue(2)
                self._scene.addItem(body)
                centerline = QGraphicsPathItem(path)
                line_color = QColor(color)
                line_color.setAlpha(215 if active else 70)
                centerline.setPen(QPen(line_color, 0))
                centerline.setZValue(3)
                self._scene.addItem(centerline)

        axis_pen = QPen(QColor("#57d7a8"), 0)
        self._scene.addLine(-3, 0, 6, 0, axis_pen).setZValue(9)
        self._scene.addLine(0, 3, 0, -6, axis_pen).setZValue(9)
        self._add_label("0", 2, 2, color="#76efbf")
        self._add_label(f"{high_x - low_x:g} mm", (low_x + high_x) / 2 - 8, -low_y + margin * 0.32)
        self._add_label(f"{high_y - low_y:g} mm", high_x + 3, -(low_y + high_y) / 2)
        self.fitInView(self._bounds, Qt.KeepAspectRatio)
