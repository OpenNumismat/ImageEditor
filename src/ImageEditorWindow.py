from PySide6.QtCore import QSettings, QFileInfo, Qt, QStandardPaths
from PySide6.QtGui import QIcon, QAction, QImage, QColor
from PySide6.QtWidgets import QMessageBox, QColorDialog, QDialog

from ImageEditor import ImageEditorDialog
from Tools.Gui import getSaveFileName
from Tools.misc import saveImageFilters

IMAGE_PATH = QStandardPaths.standardLocations(QStandardPaths.PicturesLocation)[0]


class ImageEditorWindow(ImageEditorDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowIcon(QIcon(':/slide.png'))
        
        self.imageSaved.connect(self.saveImage)
        self.viewer.doubleClicked.connect(self.viewerDoubleClicked)

    def createActions(self):
        super().createActions()

        self.transparentColorAct = QAction(self.tr("Background color"), self, triggered=self.selectTransparentColor)

    def createMenus(self):
        super().createMenus()

        self.settingsMenu.addAction(self.transparentColorAct)

    def createToolBar(self):
        super().createToolBar()

        self.toolBar.insertAction(self.saveAct, self.openFileAct)

    def viewerDoubleClicked(self):
        if not self.hasImage():
            self.openFile()

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
        settings = QSettings()
        settings.setValue('images/last_dir', file_info.absolutePath())

        file_title = file_info.fileName()
        self.setTitle(file_title)

        self.origFileName = fileName

        self.undo_stack.clear()
        self.undoAct.setDisabled(True)
        self.redoAct.setDisabled(True)
        self.isChanged = False
        # self.markWindowTitle(self.isChanged)
        self._updateEditActions()

    def saveImage(self, image):
        image.save(self.origFileName)

    def saveAs(self):
        fileName, _selectedFilter = getSaveFileName(
            self, 'images', self.name, IMAGE_PATH, saveImageFilters())
        if fileName:
            self._pixmapHandle.pixmap().save(fileName)

            file_info = QFileInfo(fileName)
            settings = QSettings()
            settings.setValue('images/last_dir', file_info.absolutePath())

            file_title = file_info.fileName()
            self.setTitle(file_title)

            self.origFileName = fileName

            self.isChanged = False

    def selectTransparentColor(self):
        settings = QSettings()
        color = settings.value('mainwindow/transparent_color', QColor(Qt.white), type=QColor)

        dlg = QColorDialog(color, self)
        if dlg.exec_() == QDialog.Accepted:
            color = dlg.currentColor()
            settings.setValue('mainwindow/transparent_color', color)
