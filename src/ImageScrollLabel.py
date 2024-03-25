from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QImage, QPixmap
from PySide6.QtWidgets import QLabel, QWidget, QSizePolicy
from PySide6.QtCore import Signal as pyqtSignal


class ImageScrollLabel(QLabel):
    imageClicked = pyqtSignal(QWidget)
    imageEdited = pyqtSignal(QLabel)

    def __init__(self, field=None, title=None, parent=None):
        super().__init__(parent)

        self.parent = parent
        self.field = field
        self.title = title or 'photo'
        self.image = QImage()

        self.clear()

        self.setBackgroundRole(QPalette.Base)
        self.setSizePolicy(QSizePolicy.Ignored,
                           QSizePolicy.Ignored)
        self.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumWidth(100)

    def setActive(self, active):
        if active:
            self.setStyleSheet("border: 2px solid green;")
        else:
            self.setStyleSheet("")

    def mouseReleaseEvent(self, _e):
        self.imageClicked.emit(self)

    def clear(self):
        self.image = QImage()
        pixmap = QPixmap.fromImage(self.image)
        self.setPixmap(pixmap)

    def resizeEvent(self, _e):
        self._showImage()

    def showEvent(self, _e):
        self._showImage()

    def loadFromFile(self, file):
        image = QImage(file)
        self._setImage(image)

    def loadFromData(self, data):
        if not data:
            data = None

        image = QImage()
        result = image.loadFromData(data)
        if result:
            self._setImage(image)

        return result

    def imageSaved(self, image):
        self._setImage(image)
        self.imageEdited.emit(self)

    def _setImage(self, image):
        self.image = image
        self._showImage()

    def _showImage(self):
        if self.image.isNull():
            return

        # Label not shown => can't get size for resizing image
        if not self.isVisible():
            return

        if self.image.width() > self.width() or \
                                        self.image.height() > self.height():
            scaledImage = self.image.scaled(self.size(),
                                Qt.KeepAspectRatio, Qt.SmoothTransformation)
        else:
            scaledImage = self.image

        pixmap = QPixmap.fromImage(scaledImage)
        self.setPixmap(pixmap)
