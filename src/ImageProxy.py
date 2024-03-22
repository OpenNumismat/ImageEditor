from PySide6.QtCore import QObject
from PySide6.QtCore import Signal as pyqtSignal


class ImageProxy(QObject):
    prevRecordEvent = pyqtSignal(QObject)
    nextRecordEvent = pyqtSignal(QObject)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._current = None
        self._images = []

    def images(self):
        return self._images

    def setImages(self, images):
        self._images = images

    def append(self, image):
        self._images.append(image)

    def currentImage(self):
        for image in self._images:
            if image.field == self._current:
                return image

    def setCurrent(self, field):
        if self._images:
            self._current = self._images[0].field
            for image in self._images:
                if image.field == field:
                    self._current = field
        else:
            self._current = None

    def imageSaved(self, image):
        self.currentImage().imageSaved(image)

    def prev(self):
        if self._images:
            _prev = self._images[0]
            for image in self._images:
                if image.field == self._current:
                    self.setCurrent(_prev.field)
                    return _prev
                else:
                    _prev = image

        return None

    def next(self):
        if self._images:
            _next = self._images[-1]
            for image in reversed(self._images):
                if image.field == self._current:
                    self.setCurrent(_next.field)
                    return _next
                else:
                    _next = image

        return None

    def prevRecord(self, editor):
        self.prevRecordEvent.emit(editor)

    def nextRecord(self, editor):
        self.nextRecordEvent.emit(editor)
