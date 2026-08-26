"""Small QtCore compatibility surface shared by Qt 5 and Qt 6."""

from openmill.ui.qt import QtCore, Signal

QEvent = QtCore.QEvent
QLocale = QtCore.QLocale
QPoint = QtCore.QPoint
QPointF = QtCore.QPointF
QRectF = QtCore.QRectF
QSize = QtCore.QSize
Qt = QtCore.Qt
QTimer = QtCore.QTimer
pyqtSignal = Signal

