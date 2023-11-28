from ImageEditor import ImageEditorDialog

from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *


class ImageEditorWindow(ImageEditorDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.latestDir = QStandardPaths.standardLocations(QStandardPaths.PicturesLocation)[0]

        self.setWindowTitle('ImageEditor')

    def createActions(self):
        super().createActions()

        style = QApplication.style()
        icon = style.standardIcon(QStyle.SP_DialogOpenButton)
        self.openFileAct = QAction(icon, self.tr("&Open..."), self, shortcut=QKeySequence.Open, triggered=self.openFile)

    def createMenus(self):
        super().createMenus()

        self.fileMenu.insertAction(self.openAct, self.openFileAct)

    def createToolBar(self):
        super().createToolBar()

        self.toolBar.insertAction(self.zoomInAct, self.openFileAct)
        self.toolBar.insertSeparator(self.zoomInAct)

    def openFile(self):
        supported_formats = QImageReader.supportedImageFormats()
        formats = "*.jpg *.jpeg *.bmp *.png *.tif *.tiff *.gif"
        if b'webp' in supported_formats:
            formats += " *.webp"
        if b'jp2' in supported_formats:
            formats += " *.jp2"

        caption = QApplication.translate('ImageEdit', "Open File")
        filter_ = QApplication.translate('ImageEdit',
                            "Images (%s);;All files (*.*)" % formats)
        fileName, _selectedFilter = QFileDialog.getOpenFileName(self,
                caption, self.latestDir, filter_)
        if fileName:
            file_info = QFileInfo(fileName)
            self.latestDir = file_info.absolutePath()

            self.loadFromFile(fileName)

    def loadFromFile(self, fileName):
        image = QImage(fileName)
        self.setImage(image)
