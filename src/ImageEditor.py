import math

from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from PySide6.QtCore import Signal as pyqtSignal

try:
    from OpenNumismat import IMAGE_PATH
    from OpenNumismat.Tools import TemporaryDir
    from OpenNumismat.Tools.DialogDecorators import storeDlgSizeDecorator, storeDlgPositionDecorator
    from OpenNumismat.Tools.Gui import getSaveFileName
    from .UndoStack import UndoStack
    from .image_tools import *
except ModuleNotFoundError:
    from Tools import TemporaryDir
    from Tools.DialogDecorators import storeDlgSizeDecorator, storeDlgPositionDecorator
    from Tools.Gui import getSaveFileName
    from UndoStack import UndoStack
    from image_tools import *

    IMAGE_PATH = QStandardPaths.standardLocations(QStandardPaths.PicturesLocation)[0]


UNDO_STACK_SIZE = 5
ZOOM_LIST = (600, 480, 385, 310, 250, 200, 158, 125,
             100, 80, 64, 50, 40, 32, 26, 20, 16,)
ZOOM_MAX = ZOOM_LIST[0]
ZOOM_MIN = ZOOM_LIST[-1]


@storeDlgPositionDecorator
class CropDialog(QDialog):
    currentToolChanged = pyqtSignal(int)
    cropChanged = pyqtSignal(int)

    def __init__(self, width, height, auto_rect, parent):
        super().__init__(parent, Qt.WindowCloseButtonHint)
        self.setWindowTitle(self.tr("Crop"))
        
        self.auto_rect = auto_rect
        
        self.rectAutoButton = QPushButton(self.tr("Auto"))
        self.rectAutoButton.clicked.connect(self.setAutoBorders)
        self.xSpin = QSpinBox()
        self.xSpin.setMaximum(width)
        self.xSpin.valueChanged.connect(self.cropChanged.emit)
        self.ySpin = QSpinBox()
        self.ySpin.setMaximum(height)
        self.ySpin.valueChanged.connect(self.cropChanged.emit)
        self.widthSpin = QSpinBox()
        self.widthSpin.setMaximum(width)
        self.widthSpin.valueChanged.connect(self.cropChanged.emit)
        self.heightSpin = QSpinBox()
        self.heightSpin.setMaximum(height)
        self.heightSpin.valueChanged.connect(self.cropChanged.emit)

        rectLayout = QGridLayout()
        rectLayout.addWidget(QLabel(self.tr("X")), 0, 0)
        rectLayout.addWidget(self.xSpin, 0, 1)
        rectLayout.addWidget(QLabel(self.tr("Y")), 0, 2)
        rectLayout.addWidget(self.ySpin, 0, 3)
        rectLayout.addWidget(QLabel(self.tr("Width")), 1, 0)
        rectLayout.addWidget(self.widthSpin, 1, 1)
        rectLayout.addWidget(QLabel(self.tr("Height")), 1, 2)
        rectLayout.addWidget(self.heightSpin, 1, 3)
        rectLayout.addWidget(self.rectAutoButton, 2, 3)

        rectWidget = QWidget()
        rectWidget.setLayout(rectLayout)

        self.x1Spin = QSpinBox()
        self.x1Spin.setMaximum(width)
        self.x1Spin.valueChanged.connect(self.cropChanged.emit)
        self.y1Spin = QSpinBox()
        self.y1Spin.setMaximum(height)
        self.y1Spin.valueChanged.connect(self.cropChanged.emit)
        self.x2Spin = QSpinBox()
        self.x2Spin.setMaximum(width)
        self.x2Spin.valueChanged.connect(self.cropChanged.emit)
        self.y2Spin = QSpinBox()
        self.y2Spin.setMaximum(height)
        self.y2Spin.valueChanged.connect(self.cropChanged.emit)
        self.x3Spin = QSpinBox()
        self.x3Spin.setMaximum(width)
        self.x3Spin.valueChanged.connect(self.cropChanged.emit)
        self.y3Spin = QSpinBox()
        self.y3Spin.setMaximum(height)
        self.y3Spin.valueChanged.connect(self.cropChanged.emit)
        self.x4Spin = QSpinBox()
        self.x4Spin.setMaximum(width)
        self.x4Spin.valueChanged.connect(self.cropChanged.emit)
        self.y4Spin = QSpinBox()
        self.y4Spin.setMaximum(height)
        self.y4Spin.valueChanged.connect(self.cropChanged.emit)

        quadLayout = QGridLayout()
        quadLayout.addWidget(QLabel(self.tr("X1")), 0, 0)
        quadLayout.addWidget(self.x1Spin, 0, 1)
        quadLayout.addWidget(QLabel(self.tr("Y1")), 0, 2)
        quadLayout.addWidget(self.y1Spin, 0, 3)
        quadLayout.addWidget(QLabel(self.tr("X2")), 0, 4)
        quadLayout.addWidget(self.x2Spin, 0, 5)
        quadLayout.addWidget(QLabel(self.tr("Y2")), 0, 6)
        quadLayout.addWidget(self.y2Spin, 0, 7)
        quadLayout.addWidget(QLabel(self.tr("X3")), 1, 0)
        quadLayout.addWidget(self.x3Spin, 1, 1)
        quadLayout.addWidget(QLabel(self.tr("Y3")), 1, 2)
        quadLayout.addWidget(self.y3Spin, 1, 3)
        quadLayout.addWidget(QLabel(self.tr("X4")), 1, 4)
        quadLayout.addWidget(self.x4Spin, 1, 5)
        quadLayout.addWidget(QLabel(self.tr("Y4")), 1, 6)
        quadLayout.addWidget(self.y4Spin, 1, 7)

        quadWidget = QWidget()
        quadWidget.setLayout(quadLayout)

        self.circleAutoButton = QPushButton(self.tr("Auto"))
        self.circleAutoButton.clicked.connect(self.setAutoBorders)
        self.xCircleSpin = QSpinBox()
        self.xCircleSpin.setMaximum(width)
        self.xCircleSpin.valueChanged.connect(self.cropChanged.emit)
        self.yCircleSpin = QSpinBox()
        self.yCircleSpin.setMaximum(height)
        self.yCircleSpin.valueChanged.connect(self.cropChanged.emit)
        self.widthCircleSpin = QSpinBox()
        self.widthCircleSpin.setMaximum(width)
        self.widthCircleSpin.valueChanged.connect(self.cropChanged.emit)
        self.heightCircleSpin = QSpinBox()
        self.heightCircleSpin.setMaximum(height)
        self.heightCircleSpin.valueChanged.connect(self.cropChanged.emit)

        circleLayout = QGridLayout()
        circleLayout.addWidget(QLabel(self.tr("X")), 0, 0)
        circleLayout.addWidget(self.xCircleSpin, 0, 1)
        circleLayout.addWidget(QLabel(self.tr("Y")), 0, 2)
        circleLayout.addWidget(self.yCircleSpin, 0, 3)
        circleLayout.addWidget(QLabel(self.tr("Width")), 1, 0)
        circleLayout.addWidget(self.widthCircleSpin, 1, 1)
        circleLayout.addWidget(QLabel(self.tr("Height")), 1, 2)
        circleLayout.addWidget(self.heightCircleSpin, 1, 3)
        circleLayout.addWidget(self.circleAutoButton, 2, 3)

        circleWidget = QWidget()
        circleWidget.setLayout(circleLayout)

        settings = QSettings()
        cropTool = settings.value('crop_dialog/crop_tool', 0, type=int)
        self.tab = QTabWidget(self)
        self.tab.addTab(rectWidget, QIcon(':/shape_handles.png'), None)
        self.tab.setTabToolTip(0, self.tr("Rect"))
        self.tab.addTab(circleWidget, QIcon(':/shape_circle.png'), None)
        self.tab.setTabToolTip(1, self.tr("Circle"))
        self.tab.addTab(quadWidget, QIcon(':/shape_handles_free.png'), None)
        self.tab.setTabToolTip(2, self.tr("Quad"))
        self.tab.currentChanged.connect(self.tabChanged)
        self.tab.setCurrentIndex(cropTool)

        buttonBox = QDialogButtonBox(Qt.Horizontal)
        buttonBox.addButton(QDialogButtonBox.Ok)
        buttonBox.addButton(QDialogButtonBox.Cancel)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(self.tab)
        layout.addWidget(buttonBox)

        self.setLayout(layout)

    def showEvent(self, _e):
        self.setFixedSize(self.size())

    def tabChanged(self, index):
        settings = QSettings()
        settings.setValue('crop_dialog/crop_tool', self.currentTool())

        self.currentToolChanged.emit(index)

    def currentTool(self):
        return self.tab.currentIndex()
    
    def setAutoBorders(self):
        if self.currentTool() == 0:
            self.xSpin.setValue(self.auto_rect[0])
            self.ySpin.setValue(self.auto_rect[1])
            self.widthSpin.setValue(self.auto_rect[2])
            self.heightSpin.setValue(self.auto_rect[3])
        elif self.currentTool() == 1:
            self.xCircleSpin.setValue(self.auto_rect[0])
            self.yCircleSpin.setValue(self.auto_rect[1])
            self.widthCircleSpin.setValue(self.auto_rect[2])
            self.heightCircleSpin.setValue(self.auto_rect[3])


class DoubleSlider(QSlider):
    def setValue(self, value):
        super().setValue(int(value))


@storeDlgPositionDecorator
class RotateDialog(QDialog):
    valueChanged = pyqtSignal(float)

    def __init__(self, parent):
        super().__init__(parent, Qt.WindowCloseButtonHint)
        self.setWindowTitle(self.tr("Rotate"))

        angleLabel = QLabel(self.tr("Angle"))

        angleSlider = DoubleSlider(Qt.Horizontal)
        angleSlider.setRange(-180, 180)
        angleSlider.setTickInterval(10)
        angleSlider.setTickPosition(QSlider.TicksAbove)
        angleSlider.setMinimumWidth(200)

        self.angleSpin = QDoubleSpinBox()
        self.angleSpin.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.angleSpin.setRange(-180, 180)
        self.angleSpin.setSingleStep(0.1)
        self.angleSpin.setAccelerated(True)
        self.angleSpin.setKeyboardTracking(False)

        angleSlider.valueChanged.connect(self.angleSpin.setValue)
        self.angleSpin.valueChanged.connect(angleSlider.setValue)
        self.angleSpin.valueChanged.connect(self.valueChanged.emit)

        angleLayout = QHBoxLayout()
        angleLayout.addWidget(angleLabel)
        angleLayout.addWidget(angleSlider)
        angleLayout.addWidget(self.angleSpin)

        settings = QSettings()
        autoCropEnabled = settings.value('rotate_dialog/auto_crop', False, type=bool)
        self.autoCrop = QCheckBox(self.tr("Auto crop"))
        self.autoCrop.stateChanged.connect(self.autoCropChanged)
        self.autoCrop.setChecked(autoCropEnabled)

        gridEnabled = settings.value('rotate_dialog/grid', False, type=bool)
        self.gridShown = QCheckBox(self.tr("Show grid"))
        self.gridShown.stateChanged.connect(self.gridChanged)
        self.gridShown.setChecked(gridEnabled)

        buttonBox = QDialogButtonBox(Qt.Horizontal)
        buttonBox.addButton(QDialogButtonBox.Ok)
        buttonBox.addButton(QDialogButtonBox.Cancel)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(angleLayout)
        layout.addWidget(self.autoCrop)
        layout.addWidget(self.gridShown)
        layout.addWidget(buttonBox)

        self.setLayout(layout)

    def showEvent(self, _e):
        self.setFixedSize(self.size())

    def autoCropChanged(self, state):
        settings = QSettings()
        settings.setValue('rotate_dialog/auto_crop', state)

        self.valueChanged.emit(self.angleSpin.value())

    def isAutoCrop(self):
        return self.autoCrop.isChecked()

    def gridChanged(self, state):
        settings = QSettings()
        settings.setValue('rotate_dialog/grid', state)

        self.valueChanged.emit(self.angleSpin.value())

    def isGridShown(self):
        return self.gridShown.isChecked()


class BoundingPointItem(QGraphicsRectItem):
    SIZE = 4
    TOP_LEFT = 0
    TOP_RIGHT = 1
    BOTTOM_RIGHT = 2
    BOTTOM_LEFT = 3
    TOP = 4
    RIGHT = 5
    BOTTOM = 6
    LEFT = 7

    def __init__(self, bounding, width, height, corner):
        self.bounding = bounding
        self.width = width
        self.height = height
        self.corner = corner

        if corner == self.TOP_LEFT:
            x = 0
            y = 0
        elif corner == self.TOP_RIGHT:
            x = width
            y = 0
        elif corner == self.BOTTOM_RIGHT:
            x = width
            y = height
        elif corner == self.BOTTOM_LEFT:
            x = 0
            y = height
        elif corner == self.TOP:
            x = width / 2
            y = 0
        elif corner == self.RIGHT:
            x = width
            y = height / 2
        elif corner == self.BOTTOM:
            x = width / 2
            y = height
        else:
            x = 0
            y = height / 2

        super().__init__(-self.SIZE / 2, -self.SIZE / 2, self.SIZE, self.SIZE)
        self.setPos(QPointF(x, y))

        self.setBrush(Qt.white)
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        # self.setFlag(QGraphicsItem.ItemSendsScenePositionChanges)
        self.setAcceptHoverEvents(True)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            return self.bounding.update(self, value)
        elif change == QGraphicsItem.ItemPositionHasChanged:
            self.bounding.updateRect()

        return super().itemChange(change, value)

    def hoverEnterEvent(self, event):
        if self.corner in (self.TOP_LEFT, self.BOTTOM_RIGHT):
            self.setCursor(Qt.SizeFDiagCursor)
        elif self.corner in (self.TOP_RIGHT, self.BOTTOM_LEFT):
            self.setCursor(Qt.SizeBDiagCursor)
        elif self.corner in (self.TOP, self.BOTTOM):
            self.setCursor(Qt.SizeVerCursor)
        else:
            self.setCursor(Qt.SizeHorCursor)

        super().hoverEnterEvent(event)


class BoundingLineItem(QGraphicsLineItem):

    def __init__(self, bounding, fixed_):
        self.bounding = bounding
        self.fixed = fixed_

        super().__init__()

        self.setPen(QPen(Qt.DashLine))
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        if self.fixed:
            self.setFlag(QGraphicsItem.ItemIsMovable)
            self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
            # self.setFlag(QGraphicsItem.ItemSendsScenePositionChanges)
            self.setAcceptHoverEvents(True)

    def _isHorizontal(self):
        angle = self.line().angle()
        return (angle in (0, 180))

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            return self.bounding.update(self, value)

        return super().itemChange(change, value)

    def hoverEnterEvent(self, event):
        if self._isHorizontal():
            self.setCursor(Qt.SizeVerCursor)
        else:
            self.setCursor(Qt.SizeHorCursor)

        super().hoverEnterEvent(event)


class MaskPolygonItem(QGraphicsPixmapItem):

    def __init__(self):
        super().__init__()

        self.setOpacity(0.2)
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations)

    def setPolygon(self, width, height, x1, y1, x2, y2, x3, y3, x4, y4):
        image = QImage(width, height, QImage.Format_ARGB32)
        image.fill(Qt.black)

        brush = QBrush(Qt.white)
        painter = QPainter(image)
        painter.setBrush(brush)
        painter.setPen(Qt.NoPen)
        painter.setRenderHint(QPainter.Antialiasing, True)  # Use AA
        points = [QPoint(x1, y1), QPoint(x2, y2), QPoint(x3, y3), QPoint(x4, y4)]
        painter.drawPolygon(points)
        painter.end()

        mask = image.createMaskFromColor(QColor(Qt.white).rgb())
        bitmap = QBitmap.fromImage(mask)
        pixmap = QPixmap.fromImage(image)
        pixmap.setMask(bitmap)
        self.setPixmap(pixmap)


class GraphicsBoundingItem(QObject):
    rectChanged = pyqtSignal()

    def __init__(self, width, height, scale, fixed_):
        super().__init__()

        self.width = width
        self.height = height
        self.scale = scale
        self.fixed = fixed_

        point1 = BoundingPointItem(self, self.width, self.height,
                                   BoundingPointItem.TOP_LEFT)
        point2 = BoundingPointItem(self, self.width, self.height,
                                   BoundingPointItem.TOP_RIGHT)
        point3 = BoundingPointItem(self, self.width, self.height,
                                   BoundingPointItem.BOTTOM_RIGHT)
        point4 = BoundingPointItem(self, self.width, self.height,
                                   BoundingPointItem.BOTTOM_LEFT)

        self.points = [point1, point2, point3, point4]

        line1 = BoundingLineItem(self, self.fixed)
        line2 = BoundingLineItem(self, self.fixed)
        line3 = BoundingLineItem(self, self.fixed)
        line4 = BoundingLineItem(self, self.fixed)

        self.lines = [line1, line2, line3, line4]

        self.mask = MaskPolygonItem()

        self.updateRect()

    def update(self, obj, pos):
        p1 = self.points[BoundingPointItem.TOP_LEFT]
        p2 = self.points[BoundingPointItem.TOP_RIGHT]
        p3 = self.points[BoundingPointItem.BOTTOM_RIGHT]
        p4 = self.points[BoundingPointItem.BOTTOM_LEFT]

        for item in self.items():
            item.setFlag(QGraphicsItem.ItemSendsGeometryChanges, False)

        if obj in self.lines:
            line = obj
            if line in (self.lines[0], self.lines[2]):
                pos.setX(0)
            else:
                pos.setY(0)

            newPos = line.line().p1() / self.scale + pos
            if line == self.lines[0]:  # --
                if newPos.y() < 0:
                    newPos.setY(0)
                oppositePos = p3.pos()
                if newPos.y() > oppositePos.y() - BoundingPointItem.SIZE:
                    newPos.setY(oppositePos.y() - BoundingPointItem.SIZE)

                p1.setY(newPos.y())
                p2.setY(newPos.y())
                x1 = self.lines[1].line().x1()
                x2 = self.lines[1].line().x2()
                self.lines[1].setLine(x1, p2.y() * self.scale,
                                      x2, p3.y() * self.scale)
                x1 = self.lines[3].line().x1()
                x2 = self.lines[3].line().x2()
                self.lines[3].setLine(x1, p4.y() * self.scale,
                                      x2, p1.y() * self.scale)
            elif line == self.lines[1]:  # |
                if newPos.x() > self.width:
                    newPos.setX(self.width)
                oppositePos = p1.pos()
                if newPos.x() < oppositePos.x() + BoundingPointItem.SIZE:
                    newPos.setX(oppositePos.x() + BoundingPointItem.SIZE)

                p2.setX(newPos.x())
                p3.setX(newPos.x())
                y1 = self.lines[0].line().y1()
                y2 = self.lines[0].line().y2()
                self.lines[0].setLine(p1.x() * self.scale, y1,
                                      p2.x() * self.scale, y2)
                y1 = self.lines[2].line().y1()
                y2 = self.lines[2].line().y2()
                self.lines[2].setLine(p3.x() * self.scale, y1,
                                      p4.x() * self.scale, y2)
            elif line == self.lines[2]:  # --
                if newPos.y() > self.height:
                    newPos.setY(self.height)
                oppositePos = p1.pos()
                if newPos.y() < oppositePos.y() + BoundingPointItem.SIZE:
                    newPos.setY(oppositePos.y() + BoundingPointItem.SIZE)

                p3.setY(newPos.y())
                p4.setY(newPos.y())
                x1 = self.lines[1].line().x1()
                x2 = self.lines[1].line().x2()
                self.lines[1].setLine(x1, p2.y() * self.scale,
                                      x2, p3.y() * self.scale)
                x1 = self.lines[3].line().x1()
                x2 = self.lines[3].line().x2()
                self.lines[3].setLine(x1, p4.y() * self.scale,
                                      x2, p1.y() * self.scale)
            else:
                if newPos.x() < 0:
                    newPos.setX(0)
                oppositePos = p2.pos()
                if newPos.x() > oppositePos.x() - BoundingPointItem.SIZE:
                    newPos.setX(oppositePos.x() - BoundingPointItem.SIZE)

                p1.setX(newPos.x())
                p4.setX(newPos.x())
                y1 = self.lines[0].line().y1()
                y2 = self.lines[0].line().y2()
                self.lines[0].setLine(p1.x() * self.scale, y1,
                                      p2.x() * self.scale, y2)
                y1 = self.lines[2].line().y1()
                y2 = self.lines[2].line().y2()
                self.lines[2].setLine(p3.x() * self.scale, y1,
                                      p4.x() * self.scale, y2)

            pos = newPos - line.line().p1() / self.scale
        elif obj in self.points:
            point = obj
            newPos = pos
            if point.corner == point.TOP_LEFT:
                if newPos.x() < 0:
                    newPos.setX(0)
                if newPos.y() < 0:
                    newPos.setY(0)

                oppositePos = p2.scenePos()
                if newPos.x() > oppositePos.x() - point.SIZE:
                    newPos.setX(oppositePos.x() - point.SIZE)
                oppositePos = p4.scenePos()
                if newPos.y() > oppositePos.y() - point.SIZE:
                    newPos.setY(oppositePos.y() - point.SIZE)

                if self.fixed:
                    self.points[point.BOTTOM_LEFT].setX(newPos.x())
                    self.points[point.TOP_RIGHT].setY(newPos.y())
                else:
                    if not self.is_convex(newPos.x(), newPos.y(), p2.x(), p2.y(), p3.x(), p3.y(), p4.x(), p4.y()):
                        newPos = self.points[point.TOP_LEFT].pos()
            elif point.corner == point.TOP_RIGHT:
                if newPos.x() > self.width:
                    newPos.setX(self.width)
                if newPos.y() < 0:
                    newPos.setY(0)

                oppositePos = p1.scenePos()
                if newPos.x() < oppositePos.x() + point.SIZE:
                    newPos.setX(oppositePos.x() + point.SIZE)
                oppositePos = p3.scenePos()
                if newPos.y() > oppositePos.y() - point.SIZE:
                    newPos.setY(oppositePos.y() - point.SIZE)

                if self.fixed:
                    self.points[point.BOTTOM_RIGHT].setX(newPos.x())
                    self.points[point.TOP_LEFT].setY(newPos.y())
                else:
                    if not self.is_convex(p1.x(), p1.y(), newPos.x(), newPos.y(), p3.x(), p3.y(), p4.x(), p4.y()):
                        newPos = self.points[point.TOP_RIGHT].pos()
            elif point.corner == point.BOTTOM_RIGHT:
                if newPos.x() > self.width:
                    newPos.setX(self.width)
                if newPos.y() > self.height:
                    newPos.setY(self.height)

                oppositePos = p4.scenePos()
                if newPos.x() < oppositePos.x() + point.SIZE:
                    newPos.setX(oppositePos.x() + point.SIZE)
                oppositePos = p2.scenePos()
                if newPos.y() < oppositePos.y() + point.SIZE:
                    newPos.setY(oppositePos.y() + point.SIZE)

                if self.fixed:
                    self.points[point.BOTTOM_LEFT].setY(newPos.y())
                    self.points[point.TOP_RIGHT].setX(newPos.x())
                else:
                    if not self.is_convex(p1.x(), p1.y(), p2.x(), p2.y(), newPos.x(), newPos.y(), p4.x(), p4.y()):
                        newPos = self.points[point.BOTTOM_RIGHT].pos()
            else:  # self.corner == self.BOTTOM_LEFT
                if newPos.x() < 0:
                    newPos.setX(0)
                if newPos.y() > self.height:
                    newPos.setY(self.height)

                oppositePos = p3.scenePos()
                if newPos.x() > oppositePos.x() - point.SIZE:
                    newPos.setX(oppositePos.x() - point.SIZE)
                oppositePos = p1.scenePos()
                if newPos.y() < oppositePos.y() + point.SIZE:
                    newPos.setY(oppositePos.y() + point.SIZE)

                if self.fixed:
                    self.points[point.BOTTOM_RIGHT].setY(newPos.y())
                    self.points[point.TOP_LEFT].setX(newPos.x())
                else:
                    if not self.is_convex(p1.x(), p1.y(), p2.x(), p2.y(), p3.x(), p3.y(), newPos.x(), newPos.y()):
                        newPos = self.points[point.BOTTOM_LEFT].pos()

            pos = newPos

        self.mask.setPolygon(self.width * self.scale, self.height * self.scale,
                             p1.x() * self.scale, p1.y() * self.scale,
                             p2.x() * self.scale, p2.y() * self.scale,
                             p3.x() * self.scale, p3.y() * self.scale,
                             p4.x() * self.scale, p4.y() * self.scale)

        for item in self.items():
            item.setFlag(QGraphicsItem.ItemSendsGeometryChanges)

        self.rectChanged.emit()

        return pos
    
    def is_convex(self, xa, ya, xb, yb, xc, yc, xd, yd):
        t1 = ((xd - xa) * (yb - ya) - (yd - ya) * (xb - xa))
        t2 = ((xd - xb) * (yc - yb) - (yd - yb) * (xc - xb))
        t3 = ((xd - xc) * (ya - yc) - (yd - yc) * (xa - xc))
        t4 = ((xa - xc) * (yb - yc) - (ya - yc) * (xb - xc))
        return t1 * t2 * t3 * t4 > 0

    def updateRect(self):
        p1 = self.points[BoundingPointItem.TOP_LEFT]
        p2 = self.points[BoundingPointItem.TOP_RIGHT]
        p3 = self.points[BoundingPointItem.BOTTOM_RIGHT]
        p4 = self.points[BoundingPointItem.BOTTOM_LEFT]

        self.lines[0].setLine(p1.x() * self.scale,
                              (p1.y() - self.lines[0].pos().y()) * self.scale,
                              p2.x() * self.scale,
                              (p2.y() - self.lines[0].pos().y()) * self.scale)
        self.lines[1].setLine((p2.x() - self.lines[1].pos().x()) * self.scale,
                              p2.y() * self.scale,
                              (p3.x() - self.lines[1].pos().x()) * self.scale,
                              p3.y() * self.scale)
        self.lines[2].setLine(p3.x() * self.scale,
                              (p3.y() - self.lines[2].pos().y()) * self.scale,
                              p4.x() * self.scale,
                              (p4.y() - self.lines[2].pos().y()) * self.scale)
        self.lines[3].setLine((p4.x() - self.lines[3].pos().x()) * self.scale,
                              p4.y() * self.scale,
                              (p1.x() - self.lines[3].pos().x()) * self.scale,
                              p1.y() * self.scale)

        self.mask.setPolygon(self.width * self.scale, self.height * self.scale,
                             p1.x() * self.scale, p1.y() * self.scale,
                             p2.x() * self.scale, p2.y() * self.scale,
                             p3.x() * self.scale, p3.y() * self.scale,
                             p4.x() * self.scale, p4.y() * self.scale)

    def setScale(self, scale):
        self.scale = scale

        self.updateRect()

    def items(self):
        return [self.mask, ] + self.lines + self.points

    def cropPoints(self):
        return [p.pos() for p in self.points]


class BoundingCircleItem(QGraphicsEllipseItem):

    def __init__(self):
        super().__init__()

        self.setPen(QPen(Qt.DashLine))
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations)


class MaskCircleItem(QGraphicsPixmapItem):

    def __init__(self):
        super().__init__()

        self.setOpacity(0.2)
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations)

    def setRect(self, width, height, x, y, w, h):
        image = QImage(width, height, QImage.Format_ARGB32)
        image.fill(Qt.black)

        brush = QBrush(Qt.white)
        painter = QPainter(image)
        painter.setBrush(brush)
        painter.setPen(Qt.NoPen)
        painter.setRenderHint(QPainter.Antialiasing, True)  # Use AA
        painter.drawEllipse(x, y, w, h)
        painter.end()

        mask = image.createMaskFromColor(QColor(Qt.white).rgb())
        bitmap = QBitmap.fromImage(mask)
        pixmap = QPixmap.fromImage(image)
        pixmap.setMask(bitmap)
        self.setPixmap(pixmap)


class GraphicsCircleBoundingItem(QObject):
    rectChanged = pyqtSignal()

    def __init__(self, width, height, scale):
        super().__init__()

        self.width = width
        self.height = height
        self.scale = scale

        point1 = BoundingPointItem(self, self.width, self.height,
                                   BoundingPointItem.TOP)
        point2 = BoundingPointItem(self, self.width, self.height,
                                   BoundingPointItem.RIGHT)
        point3 = BoundingPointItem(self, self.width, self.height,
                                   BoundingPointItem.BOTTOM)
        point4 = BoundingPointItem(self, self.width, self.height,
                                   BoundingPointItem.LEFT)

        self.points = [point1, point2, point3, point4]

        self.circle = BoundingCircleItem()
        self.mask = MaskCircleItem()

        self.updateRect()

    def update(self, obj, pos):
        p1 = self.points[0]
        p2 = self.points[1]
        p3 = self.points[2]
        p4 = self.points[3]

        for item in self.items():
            item.setFlag(QGraphicsItem.ItemSendsGeometryChanges, False)

        if obj in self.points:
            point = obj
            newPos = pos
            if point.corner == point.TOP:
                newPos.setX(point.x())
                if newPos.y() < 0:
                    newPos.setY(0)

                oppositePos = p3.scenePos()
                if newPos.y() > oppositePos.y() - point.SIZE:
                    newPos.setY(oppositePos.y() - point.SIZE)
                oppositePos = p2.scenePos()
                if newPos.x() > oppositePos.x() - point.SIZE:
                    newPos.setX(oppositePos.x() - point.SIZE)
                oppositePos = p4.scenePos()
                if newPos.x() < oppositePos.x() + point.SIZE:
                    newPos.setX(oppositePos.x() + point.SIZE)

                halfY = newPos.y() + (p3.y() - newPos.y()) / 2
                p2.setY(halfY)
                p4.setY(halfY)
            elif point.corner == point.RIGHT:
                newPos.setY(point.y())
                if newPos.x() > self.width:
                    newPos.setX(self.width)

                oppositePos = p4.scenePos()
                if newPos.x() < oppositePos.x() + point.SIZE:
                    newPos.setX(oppositePos.x() + point.SIZE)
                oppositePos = p1.scenePos()
                if newPos.y() < oppositePos.y() + point.SIZE:
                    newPos.setY(oppositePos.y() + point.SIZE)
                oppositePos = p3.scenePos()
                if newPos.y() > oppositePos.y() - point.SIZE:
                    newPos.setY(oppositePos.y() - point.SIZE)

                halfX = newPos.x() - (newPos.x() - p4.x()) / 2
                p1.setX(halfX)
                p3.setX(halfX)
            elif point.corner == point.BOTTOM:
                newPos.setX(point.x())
                if newPos.y() > self.height:
                    newPos.setY(self.height)

                oppositePos = p1.scenePos()
                if newPos.y() < oppositePos.y() + point.SIZE:
                    newPos.setY(oppositePos.y() + point.SIZE)
                oppositePos = p2.scenePos()
                if newPos.x() > oppositePos.x() - point.SIZE:
                    newPos.setX(oppositePos.x() - point.SIZE)
                oppositePos = p4.scenePos()
                if newPos.x() < oppositePos.x() + point.SIZE:
                    newPos.setX(oppositePos.x() + point.SIZE)

                halfY = newPos.y() - (newPos.y() - p1.y()) / 2
                p2.setY(halfY)
                p4.setY(halfY)
            else:  # self.corner == self.LEFT
                newPos.setY(point.y())
                if newPos.x() < 0:
                    newPos.setX(0)

                oppositePos = p2.scenePos()
                if newPos.x() > oppositePos.x() - point.SIZE:
                    newPos.setX(oppositePos.x() - point.SIZE)
                oppositePos = p1.scenePos()
                if newPos.y() < oppositePos.y() + point.SIZE:
                    newPos.setY(oppositePos.y() + point.SIZE)
                oppositePos = p3.scenePos()
                if newPos.y() > oppositePos.y() - point.SIZE:
                    newPos.setY(oppositePos.y() - point.SIZE)

                halfX = newPos.x() + (p2.x() - newPos.x()) / 2
                p1.setX(halfX)
                p3.setX(halfX)

            pos = newPos

        for item in self.items():
            item.setFlag(QGraphicsItem.ItemSendsGeometryChanges)

        self.rectChanged.emit()

        return pos

    def updateRect(self):
        p1 = self.points[0]
        p2 = self.points[1]
        p3 = self.points[2]
        p4 = self.points[3]

        self.mask.setRect(self.width * self.scale, self.height * self.scale,
                          p4.x() * self.scale, p1.y() * self.scale,
                          (p2.x() - p4.x()) * self.scale, (p3.y() - p1.y()) * self.scale)
        self.circle.setRect(p4.x() * self.scale, p1.y() * self.scale,
                            (p2.x() - p4.x()) * self.scale, (p3.y() - p1.y()) * self.scale)

    def setScale(self, scale):
        self.scale = scale

        self.updateRect()

    def items(self):
        return [self.mask, self.circle] + self.points

    def cropPoints(self):
        return [p.pos() for p in self.points]


class GraphicsGridItem(QObject):
    STEP = 40

    def __init__(self, width, height, scale):
        super().__init__()

        self.width = width * scale - 1
        self.height = height * scale - 1

        self.v_lines = []
        for i in range(int(self.width / self.STEP) + 1):
            line = QGraphicsLineItem()
            line.setPen(QPen(QColor(Qt.red)))
            line.setFlag(QGraphicsItem.ItemIgnoresTransformations)

            line.setLine(i * self.STEP, 0, i * self.STEP, self.height)

            self.v_lines.append(line)

        self.h_lines = []
        for i in range(int(self.height / self.STEP) + 1):
            line = QGraphicsLineItem()
            line.setPen(QPen(QColor(Qt.red)))
            line.setFlag(QGraphicsItem.ItemIgnoresTransformations)

            self.h_lines.append(line)

            line.setLine(0, i * self.STEP, self.width, i * self.STEP)

    def items(self):
        return self.v_lines + self.h_lines


class GraphicsScene(QGraphicsScene):

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        mime = event.mimeData()
        if mime.hasUrls():
            url = mime.urls()[0]
            self.parent().loadFromFile(url.toLocalFile())


class GraphicsView(QGraphicsView):
    doubleClicked = pyqtSignal()

    def __init__(self, scene, parent):
        super().__init__(scene, parent)

        self.setStyleSheet("border: 0px;")

    def wheelEvent(self, event):
        self.setTransformationAnchor(QGraphicsView.NoAnchor)
        # self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

        oldPos = self.mapToScene(event.position().toPoint())

        if event.angleDelta().y() > 0:
            self.parent().zoomIn()
        else:
            self.parent().zoomOut()

        # Get the new position
        newPos = self.mapToScene(event.position().toPoint())

        # Move scene to old position
        delta = newPos - oldPos
        self.translate(delta.x(), delta.y())

    def mouseDoubleClickEvent(self, event):
        self.setTransformationAnchor(QGraphicsView.NoAnchor)
        # self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

        oldPos = self.mapToScene(event.position().toPoint())

        self.parent().zoomIn()

        # Get the new position
        newPos = self.mapToScene(event.position().toPoint())

        # Move scene to old position
        delta = newPos - oldPos
        self.translate(delta.x(), delta.y())

        self.doubleClicked.emit()


@storeDlgSizeDecorator
class ImageEditorDialog(QDialog):
    latestDir = IMAGE_PATH
    imageSaved = pyqtSignal(QImage)

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowSystemMenuHint |
                         Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)

        self.setTitle()

        settings = QSettings()

        self.scene = GraphicsScene(self)
        self.viewer = GraphicsView(self.scene, self)

        self.viewer.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.viewer.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.viewer.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        color = settings.value('image_viewer/window_color', QColor(Qt.white), type=QColor)
        self.viewer.setBackgroundBrush(QBrush(color))

        self.menuBar = QMenuBar()

        self.toolBar = QToolBar()

        self.statusBar = QStatusBar()

        self.sizeLabel = QLabel()
        self.statusBar.addWidget(self.sizeLabel)

        self.zoomLabel = QLabel()
        self.statusBar.addWidget(self.zoomLabel)

        layout = QVBoxLayout()
        layout.setMenuBar(self.menuBar)
        layout.addWidget(self.toolBar)
        layout.addWidget(self.viewer)
        layout.addWidget(self.statusBar)
        layout.setContentsMargins(QMargins())
        layout.setSpacing(0)
        self.setLayout(layout)

        self.name = ''
        self.isChanged = False
        self.cropDlg = None
        self.rotateDlg = None
        self.grid = None
        self.bounding = None
        self.isFullScreen = False
        self._pixmapHandle = None
        self._origPixmap = None
        self._startPixmap = None
        self.scale = 1
        self.minScale = ZOOM_MIN / 100
        self.isFitToWindow = True
        self.undo_stack = UndoStack()

        self.createActions()
        self.createMenus()
        self.createToolBar()

        self._updateActions()

    def createActions(self):
        self.openAct = QAction(self.tr("Browse in viewer"), self, triggered=self.open)
        self.saveAsAct = QAction(self.tr("&Save As..."), self, shortcut=QKeySequence.SaveAs, triggered=self.saveAs)
        # self.printAct = QAction(self.tr("&Print..."), self, shortcut=QKeySequence.Print, enabled=False, triggered=self.print_)
        self.exitAct = QAction(self.tr("E&xit"), self, shortcut=QKeySequence.Quit, triggered=self.close)
        self.fullScreenAct = QAction(self.tr("Full Screen"), self, shortcut=QKeySequence.FullScreen, triggered=self.fullScreen)
        self.zoomInAct = QAction(QIcon(':/zoom_in.png'), self.tr("Zoom &In (25%)"), self, shortcut=Qt.Key_Plus, triggered=self.zoomIn)
        self.zoomOutAct = QAction(QIcon(':/zoom_out.png'), self.tr("Zoom &Out (25%)"), self, shortcut=Qt.Key_Minus, triggered=self.zoomOut)
        self.normalSizeAct = QAction(QIcon(':/arrow_out.png'), self.tr("&Normal Size"), self, shortcut=Qt.Key_A, triggered=self.normalSize)
        self.fitToWindowAct = QAction(QIcon(':/arrow_in.png'), self.tr("&Fit to Window"), self, shortcut=Qt.Key_0, triggered=self.fitToWindow)
        self.showToolBarAct = QAction(self.tr("Show Tool Bar"), self, checkable=True, triggered=self.showToolBar)
        self.showStatusBarAct = QAction(self.tr("Show Status Bar"), self, checkable=True, triggered=self.showStatusBar)
        self.rotateLeftAct = QAction(QIcon(':/arrow_rotate_anticlockwise.png'), self.tr("Rotate to Left"), self, shortcut=QKeySequence.MoveToPreviousWord, triggered=self.rotateLeft)
        self.rotateRightAct = QAction(QIcon(':/arrow_rotate_clockwise.png'), self.tr("Rotate to Right"), self, shortcut=QKeySequence.MoveToNextWord, triggered=self.rotateRight)
        self.rotateAct = QAction(self.tr("Rotate..."), self, shortcut=Qt.CTRL|Qt.Key_R, checkable=True, triggered=self.rotate)
        self.cropAct = QAction(QIcon(':/shape_handles.png'), self.tr("Crop..."), self, shortcut=Qt.Key_C, checkable=True, triggered=self.crop)
        self.autocropAct = QAction(self.tr("Autocrop"), self, triggered=self.autocrop)
        self.saveAct = QAction(QIcon(':/save.png'), self.tr("Save"), self, shortcut=QKeySequence.Save, triggered=self.save)
        self.saveAct.setDisabled(True)
        self.copyAct = QAction(QIcon(':/page_copy.png'), self.tr("Copy"), self, shortcut=QKeySequence.Copy, triggered=self.copy)
        self.pasteAct = QAction(QIcon(':/page_paste.png'), self.tr("Paste"), self, shortcut=QKeySequence.Paste, triggered=self.paste)
        self.undoAct = QAction(QIcon(':/undo.png'), self.tr("Undo"), self, shortcut=QKeySequence.Undo, triggered=self.undo)
        self.undoAct.setDisabled(True)
        self.redoAct = QAction(QIcon(':/redo.png'), self.tr("Redo"), self, shortcut=QKeySequence.Redo, triggered=self.redo)
        self.redoAct.setDisabled(True)
        self.windowColorAct = QAction(self.tr("Window color"), self, triggered=self.selectWindowColor)
        self.cutLeftAct = QAction(self.tr("Cut left half"), self, triggered=self.cutLeft)
        self.cutRightAct = QAction(self.tr("Cut right half"), self, triggered=self.cutRight)

        settings = QSettings()
        toolBarShown = settings.value('image_viewer/tool_bar', True, type=bool)
        self.showToolBarAct.setChecked(toolBarShown)
        self.toolBar.setVisible(toolBarShown)
        statusBarShown = settings.value('image_viewer/status_bar', True, type=bool)
        self.showStatusBarAct.setChecked(statusBarShown)
        self.statusBar.setVisible(statusBarShown)

    def createMenus(self):
        self.fileMenu = QMenu(self.tr("&File"), self)
        self.fileMenu.addAction(self.openAct)
        self.fileMenu.addAction(self.saveAct)
        self.fileMenu.addAction(self.saveAsAct)
        # self.fileMenu.addAction(self.printAct)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.exitAct)

        self.editMenu = QMenu(self.tr("&Edit"), self)
        self.editMenu.addAction(self.undoAct)
        self.editMenu.addAction(self.redoAct)
        self.editMenu.addSeparator()
        self.editMenu.addAction(self.copyAct)
        self.editMenu.addAction(self.pasteAct)
        self.editMenu.addAction(self.cutLeftAct)
        self.editMenu.addAction(self.cutRightAct)
        self.editMenu.addSeparator()
        self.editMenu.addAction(self.rotateLeftAct)
        self.editMenu.addAction(self.rotateRightAct)
        self.editMenu.addAction(self.rotateAct)
        self.editMenu.addAction(self.cropAct)
        self.editMenu.addAction(self.autocropAct)

        self.viewMenu = QMenu(self.tr("&View"), self)
        self.viewMenu.addAction(self.fullScreenAct)
        self.viewMenu.addSeparator()
        self.viewMenu.addAction(self.zoomInAct)
        self.viewMenu.addAction(self.zoomOutAct)
        self.viewMenu.addAction(self.normalSizeAct)
        self.viewMenu.addAction(self.fitToWindowAct)
        self.viewMenu.addSeparator()
        self.viewMenu.addAction(self.showToolBarAct)
        self.viewMenu.addAction(self.showStatusBarAct)

        self.settingsMenu = QMenu(self.tr("Settings"), self)
        self.settingsMenu.addAction(self.windowColorAct)

        self.menuBar.addMenu(self.fileMenu)
        self.menuBar.addMenu(self.editMenu)
        self.menuBar.addMenu(self.viewMenu)
        self.menuBar.addMenu(self.settingsMenu)

    def createToolBar(self):
        self.zoomSpin = QSpinBox(self)
        self.zoomSpin.setRange(self.minScale * 100, ZOOM_MAX)
        self.zoomSpin.setSuffix("%")
        self.zoomSpin.setValue(self.scale * 100)
        self.zoomSpin.valueChanged.connect(self.zoom)

        self.toolBar.addAction(self.saveAct)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.zoomInAct)
        self.toolBar.addWidget(self.zoomSpin)
        self.toolBar.addAction(self.zoomOutAct)
        self.toolBar.addAction(self.normalSizeAct)
        self.toolBar.addAction(self.fitToWindowAct)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.rotateLeftAct)
        self.toolBar.addAction(self.rotateRightAct)
        self.toolBar.addAction(self.cropAct)

    def setTitle(self, title=None, subtitle=None):
        competed_title_parts = []
        if subtitle:
            competed_title_parts.append(subtitle)
        if title:
            competed_title_parts.append(title)
        self.name = '_'.join(competed_title_parts)
        competed_title_parts.append(self.tr("Image editor"))

        super().setWindowTitle(' - '.join(competed_title_parts))

    def markWindowTitle(self, is_changed):
        title = self.windowTitle()
        if title[0] != '*' and is_changed:
            super().setWindowTitle('*' + title)
        elif title[0] == '*' and not is_changed:
            super().setWindowTitle(title[1:])

    def showToolBar(self, status):
        settings = QSettings()
        settings.setValue('image_viewer/tool_bar', status)
        self.toolBar.setVisible(status)

    def showStatusBar(self, status):
        settings = QSettings()
        settings.setValue('image_viewer/status_bar', status)
        self.statusBar.setVisible(status)

    def selectWindowColor(self):
        settings = QSettings()
        color = settings.value('image_viewer/window_color', QColor(Qt.white), type=QColor)

        dlg = QColorDialog(color, self)
        if dlg.exec_() == QDialog.Accepted:
            color = dlg.currentColor()
            settings.setValue('image_viewer/window_color', color)
            self.viewer.setBackgroundBrush(QBrush(color))

    def hasImage(self):
        return self._pixmapHandle is not None

    def clearImage(self):
        if self.hasImage():
            self.scene.removeItem(self._pixmapHandle)
            self._pixmapHandle = None

    def pixmap(self):
        if self.hasImage():
            return self._pixmapHandle.pixmap()
        return None

    def showEvent(self, _e):
        self.updateViewer()

    def resizeEvent(self, _e):
        if self.isVisible():
            self.updateViewer()

    def setImage(self, image):
        if type(image) is QPixmap:
            image = image.toImage()

        if image.hasAlphaChannel():
            # Fill transparent color if present
            settings = QSettings()
            color = settings.value('mainwindow/transparent_color', QColor(Qt.white), type=QColor)
            fixed_image = QImage(image.size(), QImage.Format_RGB32)
            fixed_image.fill(color)
            painter = QPainter(fixed_image)
            painter.drawImage(0, 0, image)
            painter.end()
        else:
            fixed_image = image

        pixmap = QPixmap.fromImage(fixed_image)

        if self.hasImage():
            self._pixmapHandle.setPixmap(pixmap)
        else:
            self._origPixmap = pixmap
            self._pixmapHandle = self.scene.addPixmap(pixmap)

        self.viewer.setSceneRect(QRectF(pixmap.rect()))
        self.updateViewer()

        self._updateActions()

        self.sizeLabel.setText("%dx%d" % (image.width(), image.height()))

    def getImage(self):
        return self._pixmapHandle.pixmap().toImage()

    def open(self):
        fileName = self._saveTmpImage()

        executor = QDesktopServices()
        executor.openUrl(QUrl.fromLocalFile(fileName))

    def _saveTmpImage(self):
        tmpDir = QDir(TemporaryDir.path())
        file = QTemporaryFile(tmpDir.absoluteFilePath("img_XXXXXX.jpg"))
        file.setAutoRemove(False)
        file.open()

        fileName = QFileInfo(file).absoluteFilePath()
        self._pixmapHandle.pixmap().save(fileName)

        return fileName

    def saveAs(self):
        supported_formats = QImageReader.supportedImageFormats()
        formats = "*.jpg *.jpeg *.png *.bmp *.tiff"
        if b'webp' in supported_formats:
            formats += " *.webp"
        if b'jp2' in supported_formats:
            formats += " *.jp2"

        filters = (self.tr("Images (%s)") % formats,
                   self.tr("All files (*.*)"))
        fileName, _selectedFilter = getSaveFileName(
            self, 'save_image', self.name, self.latestDir, filters)
        if fileName:
            self._pixmapHandle.pixmap().save(fileName)

            file_info = QFileInfo(fileName)
            self.latestDir = file_info.absolutePath()

    def done(self, r):
        if self.cropDlg and self.cropDlg.isVisible():
            self.cropDlg.close()
            return
        if self.rotateDlg and self.rotateDlg.isVisible():
            self.rotateDlg.close()
            return

        if self.isFullScreen:
            self.isFullScreen = False

            self.menuBar.show()
            self.toolBar.setVisible(self.showToolBarAct.isChecked())
            self.statusBar.setVisible(self.showStatusBarAct.isChecked())

            self.showNormal()
        else:
            if self.isChanged:
                result = QMessageBox.warning(
                    self, self.tr("Save"),
                    self.tr("Image was changed. Save changes?"),
                    QMessageBox.Save | QMessageBox.No, QMessageBox.No)
                if result == QMessageBox.Save:
                    self.save(confirm_save=False)

            super().done(r)

    def fullScreen(self):
        self.isFullScreen = True

        self.menuBar.hide()
        self.toolBar.hide()
        self.statusBar.hide()

        self.showFullScreen()

    def normalSize(self):
        self.viewer.setTransformationAnchor(QGraphicsView.AnchorViewCenter)

        self.zoom(100)

    def fitToWindow(self):
        self.isFitToWindow = True

        sceneRect = self.viewer.sceneRect()
        scaleH = (self.viewer.height() - 4) / sceneRect.height()
        scaleW = (self.viewer.width() - 4) / sceneRect.width()
        if scaleH < 1 or scaleW < 1:
            self.viewer.fitInView(sceneRect, Qt.KeepAspectRatio)
            self.scale = min(scaleH, scaleW)
        else:
            self.viewer.resetTransform()
            self.scale = 1

        self._updateGrid()
        if self.bounding:
            self.bounding.setScale(self.scale)

        self._updateZoomActions()

    def copy(self):
        image = self._pixmapHandle.pixmap().toImage()
        mime = QMimeData()
        mime.setImageData(image)

        clipboard = QApplication.clipboard()
        clipboard.setMimeData(mime)

    def paste(self):
        mime = QApplication.clipboard().mimeData()
        if mime.hasImage():
            pixmap = self._pixmapHandle.pixmap()
            self.pushUndo(pixmap)
            self.setImage(mime.imageData())
            self.isChanged = True
            self.markWindowTitle(self.isChanged)
            self._updateEditActions()
        elif mime.hasUrls():
            url = mime.urls()[0]
            self.loadFromFile(url.toLocalFile())

    def cutLeft(self):
        pixmap = self._pixmapHandle.pixmap()
        left_half = pixmap.copy(0, 0,
                                pixmap.width() // 2, pixmap.height())
        right_half = pixmap.copy(pixmap.width() // 2, 0,
                                 pixmap.width() - pixmap.width() // 2, pixmap.height())

        image = left_half.toImage()
        mime = QMimeData()
        mime.setImageData(image)

        clipboard = QApplication.clipboard()
        clipboard.setMimeData(mime)

        self.pushUndo(pixmap)
        self.setImage(right_half)
        self.isChanged = True
        self.markWindowTitle(self.isChanged)
        self._updateEditActions()

    def cutRight(self):
        pixmap = self._pixmapHandle.pixmap()
        left_half = pixmap.copy(0, 0,
                                pixmap.width() // 2, pixmap.height())
        right_half = pixmap.copy(pixmap.width() // 2, 0,
                                 pixmap.width() - pixmap.width() // 2, pixmap.height())

        image = right_half.toImage()
        mime = QMimeData()
        mime.setImageData(image)

        clipboard = QApplication.clipboard()
        clipboard.setMimeData(mime)

        self.pushUndo(pixmap)
        self.setImage(left_half)
        self.isChanged = True
        self.markWindowTitle(self.isChanged)
        self._updateEditActions()

    def loadFromFile(self, fileName):
        image = QImage()
        result = image.load(fileName)
        if result:
            pixmap = self._pixmapHandle.pixmap()
            self.pushUndo(pixmap)
            self.setImage(image)
            self.isChanged = True
            self.markWindowTitle(self.isChanged)
            self._updateEditActions()

    def zoomIn(self):
        new_zoom = ZOOM_LIST[0]
        for zoom in ZOOM_LIST:
            if zoom > self.scale * 100:
                new_zoom = zoom

        self.zoom(new_zoom)

    def zoomOut(self):
        new_zoom = self.minScale
        for zoom in ZOOM_LIST:
            if zoom < self.scale * 100:
                new_zoom = zoom
                break

        self.zoom(new_zoom)

    def zoom(self, zoom):
        if not self.hasImage():
            return

        scale = zoom / 100
        if scale < self.minScale:
            scale = self.minScale
        if scale > ZOOM_MAX / 100:
            scale = ZOOM_MAX / 100
        need_scale = scale / self.scale

        if scale > self.minScale:
            self.isFitToWindow = False
        else:
            self.isFitToWindow = True

        if scale != self.scale:
            self.scale = scale
            self.viewer.scale(need_scale, need_scale)

            self._updateGrid()
            if self.bounding:
                self.bounding.setScale(self.scale)

        self._updateZoomActions()

    def updateViewer(self):
        if not self.hasImage():
            return

        sceneRect = self.viewer.sceneRect()
        minHeightScale = (self.viewer.height() - 4) / sceneRect.height()
        minWidthScale = (self.viewer.width() - 4) / sceneRect.width()
        self.minScale = max(min(minHeightScale, minWidthScale), ZOOM_MIN / 100)
        if self.minScale > 1:
            self.minScale = 1

        if self.isFitToWindow:
            self.fitToWindow()

        self._updateGrid()
        if self.bounding:
            self.bounding.setScale(self.scale)

        self._updateZoomActions()

    def _updateZoomActions(self):
        sceneRect = self.viewer.sceneRect()
        imageRect = self.viewer.mapToScene(self.viewer.rect()).boundingRect()
        if imageRect.contains(sceneRect):
            self.viewer.setDragMode(QGraphicsView.NoDrag)
        else:
            self.viewer.setDragMode(QGraphicsView.ScrollHandDrag)

        self.zoomInAct.setDisabled(self.scale >= ZOOM_MAX / 100)
        self.zoomOutAct.setDisabled(self.scale <= self.minScale)
        self.fitToWindowAct.setDisabled(self.isFitToWindow)
        self.normalSizeAct.setDisabled(self.scale == 1)

        zoom = self.scale * 100 + 0.5

        self.zoomSpin.blockSignals(True)
        self.zoomSpin.setValue(zoom)
        self.zoomSpin.blockSignals(False)

        self.zoomLabel.setText("%d%%" % zoom)

    def rotateLeft(self):
        transform = QTransform()
        trans = transform.rotate(-90)
        pixmap = self._pixmapHandle.pixmap()
        self.pushUndo(pixmap)
        pixmap = pixmap.transformed(trans)
        self.setImage(pixmap)

        self.isChanged = True
        self.markWindowTitle(self.isChanged)
        self._updateEditActions()

    def rotateRight(self):
        transform = QTransform()
        trans = transform.rotate(90)
        pixmap = self._pixmapHandle.pixmap()
        self.pushUndo(pixmap)
        pixmap = pixmap.transformed(trans)
        self.setImage(pixmap)

        self.isChanged = True
        self.markWindowTitle(self.isChanged)
        self._updateEditActions()

    def _updateGrid(self):
        if self.grid:
            for item in self.grid.items():
                self.scene.removeItem(item)

        if self.rotateDlg and self.rotateDlg.isVisible():
            if self.rotateDlg.isGridShown():
                sceneRect = self.viewer.sceneRect()
                w = sceneRect.width()
                h = sceneRect.height()
                self.grid = GraphicsGridItem(w, h, self.scale)
                for item in self.grid.items():
                    self.scene.addItem(item)
            else:
                self.grid = None
        else:
            self.grid = None

    def rotate(self):
        if self.rotateAct.isChecked():
            self.rotateDlg = RotateDialog(self)
            self.rotateDlg.valueChanged.connect(self.rotateChanged)
            self.rotateDlg.finished.connect(self.rotateClose)
            self.rotateDlg.show()
            self._startPixmap = self._pixmapHandle.pixmap()
            center = self.viewer.viewport().rect().center()
            self._startCenter = self.viewer.mapToScene(center)

            self._updateEditActions()
        else:
            self.rotateDlg.close()
            self.rotateDlg = None

        self._updateGrid()

    def rotateChanged(self, value):
        transform = QTransform()
        trans = transform.rotate(value)
        pixmap = self._startPixmap.transformed(trans, Qt.SmoothTransformation)

        w = self._startPixmap.width()
        h = self._startPixmap.height()
        if self.rotateDlg.isAutoCrop():
            if (-45 < value and value < 45) or value < -135 or 135 < value:
                xoffset = (pixmap.width() - w) // 2
                yoffset = (pixmap.height() - h) // 2
                rect = QRect(xoffset, yoffset, w, h)
            else:
                xoffset = (pixmap.width() - h) // 2
                yoffset = (pixmap.height() - w) // 2
                rect = QRect(xoffset, yoffset, h, w)
            pixmap = pixmap.copy(rect)
        else:
            xoffset = (pixmap.width() - w) // 2
            yoffset = (pixmap.height() - h) // 2

        self.setImage(pixmap)

        if not self.rotateDlg.isAutoCrop():
            self.viewer.centerOn(self._startCenter.x() + xoffset,
                                 self._startCenter.y() + yoffset)

        self._updateGrid()

    def rotateClose(self, result):
        self._updateGrid()

        if result:
            self.isChanged = True
            self.markWindowTitle(self.isChanged)
            self.pushUndo(self._startPixmap)
        else:
            self.setImage(self._startPixmap)
            self.viewer.centerOn(self._startCenter)

        self._startPixmap = None

        self.rotateAct.setChecked(False)
        self._updateEditActions()
    
    def crop(self):
        if self.cropAct.isChecked():
            sceneRect = self.viewer.sceneRect()
            w = int(sceneRect.width())
            h = int(sceneRect.height())

            image = self._pixmapHandle.pixmap().toImage()
            auto_rect = findBorders(image)

            self.cropDlg = CropDialog(w, h, auto_rect, self)
            self.cropDlg.finished.connect(self.cropClose)
            self.cropDlg.currentToolChanged.connect(self.cropToolChanged)
            self.cropDlg.cropChanged.connect(self.cropDlgChanged)
            self.cropDlg.show()

            self.cropToolChanged(self.cropDlg.currentTool())

            self._updateEditActions()
        else:
            self.cropDlg.close()
            self.cropDlg = None

    def cropToolChanged(self, _index):
        if self.bounding:
            for item in self.bounding.items():
                self.scene.removeItem(item)
            self.bounding = None

        sceneRect = self.viewer.sceneRect()
        w = sceneRect.width()
        h = sceneRect.height()

        if self.cropDlg.currentTool() in (0, 2):
            fixed_rect = (self.cropDlg.currentTool() == 0)
            self.bounding = GraphicsBoundingItem(w, h, self.scale, fixed_rect)
        else:
            self.bounding = GraphicsCircleBoundingItem(w, h, self.scale)
        for item in self.bounding.items():
            self.scene.addItem(item)

        self.bounding.rectChanged.connect(self.cropChanged)
        self.cropChanged()

    def cropChanged(self):
        points = self.bounding.cropPoints()

        self.cropDlg.cropChanged.disconnect(self.cropDlgChanged)
        if self.cropDlg.currentTool() == 0:
            self.cropDlg.xSpin.setValue(int(points[0].x()))
            self.cropDlg.ySpin.setValue(int(points[0].y()))
            self.cropDlg.widthSpin.setValue(int(points[2].x() - points[0].x()))
            self.cropDlg.heightSpin.setValue(int(points[2].y() - points[0].y()))
        elif self.cropDlg.currentTool() == 1:
            self.cropDlg.xCircleSpin.setValue(int(points[3].x()))
            self.cropDlg.yCircleSpin.setValue(int(points[0].y()))
            self.cropDlg.widthCircleSpin.setValue(int(points[1].x() - points[3].x()))
            self.cropDlg.heightCircleSpin.setValue(int(points[2].y() - points[0].y()))
        else:
            self.cropDlg.x1Spin.setValue(int(points[0].x()))
            self.cropDlg.y1Spin.setValue(int(points[0].y()))
            self.cropDlg.x2Spin.setValue(int(points[1].x()))
            self.cropDlg.y2Spin.setValue(int(points[1].y()))
            self.cropDlg.x3Spin.setValue(int(points[2].x()))
            self.cropDlg.y3Spin.setValue(int(points[2].y()))
            self.cropDlg.x4Spin.setValue(int(points[3].x()))
            self.cropDlg.y4Spin.setValue(int(points[3].y()))
        self.cropDlg.cropChanged.connect(self.cropDlgChanged)

    def cropDlgChanged(self, i):
        self.bounding.rectChanged.disconnect(self.cropChanged)
        if self.cropDlg.currentTool() == 0:
            x = self.cropDlg.xSpin.value()
            y = self.cropDlg.ySpin.value()
            w = self.cropDlg.widthSpin.value()
            h = self.cropDlg.heightSpin.value()
            self.bounding.points[0].setX(x)
            self.bounding.points[0].setY(y)
            self.bounding.points[2].setX(x + w)
            self.bounding.points[2].setY(y + h)
            self.cropChanged()
        elif self.cropDlg.currentTool() == 1:
            x = self.cropDlg.xCircleSpin.value()
            y = self.cropDlg.yCircleSpin.value()
            w = self.cropDlg.widthCircleSpin.value()
            h = self.cropDlg.heightCircleSpin.value()
            self.bounding.points[3].setX(x)
            self.bounding.points[0].setY(y)
            self.bounding.points[1].setX(x + w)
            self.bounding.points[2].setY(y + h)
            self.cropChanged()
        else:
            self.bounding.points[0].setX(self.cropDlg.x1Spin.value())
            self.bounding.points[0].setY(self.cropDlg.y1Spin.value())
            self.bounding.points[1].setX(self.cropDlg.x2Spin.value())
            self.bounding.points[1].setY(self.cropDlg.y2Spin.value())
            self.bounding.points[2].setX(self.cropDlg.x3Spin.value())
            self.bounding.points[2].setY(self.cropDlg.y3Spin.value())
            self.bounding.points[3].setX(self.cropDlg.x4Spin.value())
            self.bounding.points[3].setY(self.cropDlg.y4Spin.value())
            self.cropChanged()
        self.bounding.rectChanged.connect(self.cropChanged)

    def cropClose(self, result):
        points = self.bounding.cropPoints()

        for item in self.bounding.items():
            self.scene.removeItem(item)
        self.bounding = None

        if result:
            pixmap = self._pixmapHandle.pixmap()
            self.pushUndo(pixmap)

            if self.cropDlg.currentTool() == 0:
                rect = QRectF(points[0], points[2]).toRect()

                pixmap = pixmap.copy(rect)
                self.setImage(pixmap)

                self.isChanged = True
            elif self.cropDlg.currentTool() == 1:
                pixmap = cropCircle(pixmap, points)
                if pixmap:
                    self.setImage(pixmap)

                    self.isChanged = True
            else:
                pixmap = perspectiveTransformation(pixmap, points)
                if pixmap:
                    self.setImage(pixmap)

                    self.isChanged = True

        self.markWindowTitle(self.isChanged)
        self.cropAct.setChecked(False)
        self._updateEditActions()

    def autocrop(self):
        pixmap = self._pixmapHandle.pixmap()
        self.pushUndo(pixmap)

        sceneRect = self.viewer.sceneRect()
        w = int(sceneRect.width())
        h = int(sceneRect.height())

        image = pixmap.toImage()
        x1 = self.__findBorderV(image, range(w//2), range(h))
        x2 = self.__findBorderV(image, range(w-1, w//2, -1), range(h)) + 1
        y1 = self.__findBorderH(image, range(h//2), range(w))
        y2 = self.__findBorderH(image, range(h-1, h//2, -1), range(w)) + 1

        rect = QRect(x1, y1, x2-x1, y2-y1)

        pixmap = pixmap.copy(rect)
        self.setImage(pixmap)

        self.isChanged = True
        self.markWindowTitle(self.isChanged)

    def _updateActions(self):
        enabled = self.hasImage()

        self.zoomSpin.setEnabled(enabled)
        self.openAct.setEnabled(enabled)
        self.saveAsAct.setEnabled(enabled)
        self.zoomInAct.setEnabled(enabled)
        self.zoomOutAct.setEnabled(enabled)
        self.normalSizeAct.setEnabled(enabled)
        self.fitToWindowAct.setEnabled(enabled)
        self.rotateLeftAct.setEnabled(enabled)
        self.rotateRightAct.setEnabled(enabled)
        self.rotateAct.setEnabled(enabled)
        self.cropAct.setEnabled(enabled)
        self.autocropAct.setEnabled(enabled)
        self.copyAct.setEnabled(enabled)
        self.cutLeftAct.setEnabled(enabled)
        self.cutRightAct.setEnabled(enabled)

    def _updateEditActions(self):
        inCrop = self.cropAct.isChecked()
        inRotate = self.rotateAct.isChecked()
        self.exitAct.setDisabled(inCrop or inRotate)
        self.saveAsAct.setDisabled(inCrop or inRotate)
        self.copyAct.setDisabled(inCrop or inRotate)
        self.pasteAct.setDisabled(inCrop or inRotate)
        self.rotateLeftAct.setDisabled(inCrop or inRotate)
        self.rotateRightAct.setDisabled(inCrop or inRotate)
        self.rotateAct.setDisabled(inCrop)
        self.cropAct.setDisabled(inRotate)

        if inCrop or inRotate:
            self.saveAct.setDisabled(True)
        else:
            self.saveAct.setEnabled(self.isChanged)

    def _updateUndoActions(self):
        self.undoAct.setEnabled(self.undo_stack.can_undo())
        self.redoAct.setEnabled(self.undo_stack.can_redo())

    def save(self, confirm_save=True):
        if confirm_save:
            settings = QSettings()
            show = settings.value('image_viewer/confirm_save', True, type=bool)
            if show:
                msg_box = QMessageBox(QMessageBox.Warning, self.tr("Save"),
                                      self.tr("Save changes to current image?"),
                                      QMessageBox.Save | QMessageBox.No,
                                      self)
                msg_box.setDefaultButton(QMessageBox.No)
                cb = QCheckBox(self.tr("Don't show this again"))
                msg_box.setCheckBox(cb)
                result = msg_box.exec_()
                if result != QMessageBox.Save:
                    return
                else:
                    if cb.isChecked():
                        settings.setValue('image_viewer/confirm_save', False)

        if self.isChanged:
            self._origPixmap = self._pixmapHandle.pixmap()
            self.imageSaved.emit(self.getImage())

        self.isChanged = False
        self.undo_stack.store_pos()
        self.markWindowTitle(self.isChanged)
        self._updateEditActions()

    def pushUndo(self, pixmap):
        self.undo_stack.push(pixmap)

        self._updateUndoActions()

    def undo(self):
        pixmap = self.undo_stack.undo()
        self.undo_stack.push_redo(self._pixmapHandle.pixmap())

        self._updateUndoActions()

        self.setImage(pixmap)

        if self.isChanged:
            if not self.undo_stack.is_pos_changed():
                self.isChanged = False
        else:
            self.isChanged = True
        self.markWindowTitle(self.isChanged)
        self._updateEditActions()

    def redo(self):
        pixmap = self.undo_stack.redo()
        self.undo_stack.push_undo(self._pixmapHandle.pixmap())

        self._updateUndoActions()

        self.setImage(pixmap)

        if self.isChanged:
            if not self.undo_stack.is_pos_changed():
                self.isChanged = False
        else:
            self.isChanged = True
        self.markWindowTitle(self.isChanged)
        self._updateEditActions()
