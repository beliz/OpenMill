"""Small QtWidgets compatibility surface; QAction moved in Qt 6."""

from openmill.ui.qt import QtGui, QtWidgets

QAbstractItemView = QtWidgets.QAbstractItemView
QAbstractSpinBox = QtWidgets.QAbstractSpinBox
QAction = getattr(QtWidgets, "QAction", None) or QtGui.QAction
QApplication = QtWidgets.QApplication
QButtonGroup = QtWidgets.QButtonGroup
QComboBox = QtWidgets.QComboBox
QDialog = QtWidgets.QDialog
QDoubleSpinBox = QtWidgets.QDoubleSpinBox
QFileDialog = QtWidgets.QFileDialog
QFrame = QtWidgets.QFrame
QGraphicsEllipseItem = QtWidgets.QGraphicsEllipseItem
QGraphicsPathItem = QtWidgets.QGraphicsPathItem
QGraphicsScene = QtWidgets.QGraphicsScene
QGraphicsView = QtWidgets.QGraphicsView
QGridLayout = QtWidgets.QGridLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QLabel = QtWidgets.QLabel
QLineEdit = QtWidgets.QLineEdit
QListWidget = QtWidgets.QListWidget
QListWidgetItem = QtWidgets.QListWidgetItem
QMainWindow = QtWidgets.QMainWindow
QMessageBox = QtWidgets.QMessageBox
QPlainTextEdit = QtWidgets.QPlainTextEdit
QPushButton = QtWidgets.QPushButton
QScrollArea = QtWidgets.QScrollArea
QScroller = QtWidgets.QScroller
QSizePolicy = QtWidgets.QSizePolicy
QSlider = QtWidgets.QSlider
QSpinBox = QtWidgets.QSpinBox
QSplitter = QtWidgets.QSplitter
QStackedWidget = QtWidgets.QStackedWidget
QTabWidget = QtWidgets.QTabWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QWidget = QtWidgets.QWidget

