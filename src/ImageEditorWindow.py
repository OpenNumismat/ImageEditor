from PySide6.QtCore import QSettings, QFileInfo, Qt
from PySide6.QtGui import QIcon, QAction, QKeySequence, QImageReader, QImage, QColor
from PySide6.QtWidgets import QApplication, QStyle, QFileDialog, QMessageBox, QColorDialog, QDialog

from ImageEditor import ImageEditorDialog


class ImageEditorWindow(ImageEditorDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowIcon(QIcon(':/slide.png'))
        
        self.imageSaved.connect(self.saveImage)

    def createActions(self):
        super().createActions()

        style = QApplication.style()
        icon = style.standardIcon(QStyle.SP_DialogOpenButton)
        self.openFileAct = QAction(icon, self.tr("&Open..."), self, shortcut=QKeySequence.Open, triggered=self.openFile)
        self.transparentColorAct = QAction(self.tr("Background color"), self, triggered=self.selectTransparentColor)

    def createMenus(self):
        super().createMenus()

        self.fileMenu.insertAction(self.openAct, self.openFileAct)
        self.settingsMenu.addAction(self.transparentColorAct)

    def createToolBar(self):
        super().createToolBar()

        self.toolBar.insertAction(self.saveAct, self.openFileAct)

    def openFile(self):
        supported_formats = QImageReader.supportedImageFormats()
        formats = "*.jpg *.jpeg *.bmp *.png *.tif *.tiff *.gif"
        if b'webp' in supported_formats:
            formats += " *.webp"
        if b'jp2' in supported_formats:
            formats += " *.jp2"

        caption = self.tr("Open File")
        filters = (self.tr("Images (%s)") % formats,
                   self.tr("All files (*.*)"))
        file_name, _ = QFileDialog.getOpenFileName(self,
                caption, self.latestDir, ';;'.join(filters))
        if file_name:
            self.loadFromFile(file_name)

    def loadFromFile(self, fileName):
        if self.isChanged:
            result = QMessageBox.warning(
                self, self.tr("Save"),
                self.tr("Image was changed. Save changes?"),
                QMessageBox.Save | QMessageBox.No | QMessageBox.Cancel, QMessageBox.Cancel)
            if result == QMessageBox.Save:
                self.save(confirm_save=False)
            elif result == QMessageBox.Cancel:
                return

        image = QImage(fileName)
        self.setImage(image)

        file_info = QFileInfo(fileName)
        self.latestDir = file_info.absolutePath()

        file_title = file_info.fileName()
        self.setTitle(file_title)

        self.origFileName = fileName

        self.undo_stack = []
        self.undoAct.setDisabled(True)
        self.redo_stack = []
        self.redoAct.setDisabled(True)
        self.isChanged = False
        # self.markWindowTitle(self.isChanged)
        self._updateEditActions()

    def saveImage(self, image):
        image.save(self.origFileName)

    def selectTransparentColor(self):
        settings = QSettings()
        color = settings.value('mainwindow/transparent_color', QColor(Qt.white), type=QColor)

        dlg = QColorDialog(color, self)
        if dlg.exec_() == QDialog.Accepted:
            color = dlg.currentColor()
            settings.setValue('mainwindow/transparent_color', color)
