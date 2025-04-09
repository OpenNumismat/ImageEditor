import os

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QDialog,
    QFileDialog,
    QPushButton,
    QSizePolicy,
    QSplitter,
)


class Splitter(QSplitter):

    def __init__(self, title, orientation=Qt.Horizontal, parent=None):
        super().__init__(orientation, parent)

        self.title = title
        self.splitterMoved.connect(self.splitterPosChanged)

    def splitterPosChanged(self, _pos, _index):
        settings = QSettings()
        settings.setValue('pageview/splittersizes' + self.title, self.sizes())

    def showEvent(self, _e):
        settings = QSettings()
        sizes = settings.value('pageview/splittersizes' + self.title)
        if sizes:
            for i, size in enumerate(sizes):
                sizes[i] = int(size)

            self.splitterMoved.disconnect(self.splitterPosChanged)
            self.setSizes(sizes)
            self.splitterMoved.connect(self.splitterPosChanged)


class ColorButton(QPushButton):

    def __init__(self, color, parent=None):
        super().__init__(parent)

        self._color = color

        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.updateColorButton(self._color)
        self.clicked.connect(self.colorButtonClicked)

    def color(self):
        return self._color

    def colorButtonClicked(self):
        dlg = QColorDialog(self._color, self)
        if dlg.exec() == QDialog.Accepted:
            self._color = dlg.currentColor()
            self.updateColorButton(self._color)

    def updateColorButton(self, color):
        pixmap = QPixmap(16, 16)
        pixmap.fill(color)
        icon = QIcon(pixmap)
        self.setIcon(icon)


def getSaveFileName(parent, name, filename, dir_, filters):
    settings = QSettings()

    keyDir = name + '/last_dir'
    keyFilter = name + '/last_filter'
    lastExportDir = settings.value(keyDir, dir_)
    defaultFileName = os.path.join(lastExportDir, filename)

    if isinstance(filters, str):
        filters = (filters,)
    if '.' in filename:
        ext = filename.split('.')[-1]
        for filter_ in filters:
            if f"*.{ext}" in filter_:
                defaultFilter = filter_
                break
    else:
        defaultFilter = settings.value(keyFilter)

    caption = QApplication.translate("GetSaveFileName", "Save as")

    fileName, selectedFilter = QFileDialog.getSaveFileName(
        parent, caption, defaultFileName, filter=';;'.join(filters),
        selectedFilter=defaultFilter)
    if fileName:
        lastExportDir = os.path.dirname(fileName)
        settings.setValue(keyDir, lastExportDir)
        settings.setValue(keyFilter, selectedFilter)

    return fileName, selectedFilter
