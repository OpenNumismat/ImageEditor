from PySide6.QtCore import QSettings, QFileInfo, Qt, QStandardPaths, QDir
from PySide6.QtGui import QIcon, QAction, QImage, QColor, QPixmap, QPalette
from PySide6.QtWidgets import QApplication, QStyle, QMessageBox, QColorDialog, QDialog, QFileDialog, QLabel, QWidget, QSizePolicy
from PySide6.QtCore import Signal as pyqtSignal

from ImageEditor import ImageEditorDialog
from Tools.Gui import getSaveFileName
from Tools.misc import saveImageFilters

IMAGE_PATH = QStandardPaths.standardLocations(QStandardPaths.PicturesLocation)[0]


class ImageProxy():

    def __init__(self):
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
        self._current = field

    def imageSaved(self, image):
        self.currentImage().imageSaved(image)


class ImageScrollLabel(QLabel):
    MimeType = 'num/image'
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


class ImageEditorWindow(ImageEditorDialog):

    def __init__(self, parent=None):
        super().__init__(parent, scrollpanel=True)

        self.setWindowIcon(QIcon(':/slide.png'))
        
        self.viewer.doubleClicked.connect(self.viewerDoubleClicked)

        self.scrollPanel.hide()

        self.saveImageConnected = False

    def createActions(self):
        super().createActions()

        style = QApplication.style()
        icon = style.standardIcon(QStyle.SP_DirOpenIcon)
        self.openFolderAct = QAction(icon, self.tr("Open folder..."), self, triggered=self.openFolder)
        self.transparentColorAct = QAction(self.tr("Background color"), self, triggered=self.selectTransparentColor)

    def createMenus(self):
        super().createMenus()

        self.fileMenu.insertAction(self.saveAct, self.openFolderAct)
        self.settingsMenu.addAction(self.transparentColorAct)

    def createToolBar(self):
        super().createToolBar()

        self.toolBar.insertAction(self.saveAct, self.openFileAct)

    def viewerDoubleClicked(self):
        if not self.hasImage():
            self.openFile()

    def openFile(self):
        if super().openFile():
            self.scrollPanel.clear()
            self.scrollPanel.hide()

            self.imageSaved.connect(self.saveImage)
            self.saveImageConnected = True

    def openFolder(self):
        settings = QSettings()
        last_dir = settings.value('images/last_dir', IMAGE_PATH)

        folder = QFileDialog.getExistingDirectory(
            self, self.tr("Open image folder"), last_dir)
        if folder:
            dir_ = QDir(folder)
            filter_ = ('*.png', '*.jpg', '*.jpeg', '*.bmp',
                       '*.tif', '*.tiff', '*.gif', '*.webp')
            files = dir_.entryInfoList(filter_, QDir.Files, QDir.Name)
            if len(files) > 0:
                proxy = ImageProxy()
                for file in files:
                    image = ImageScrollLabel(field=file.filePath(), title=file.fileName())
                    image.loadFromFile(file.filePath())
                    image.imageEdited.connect(self.imageEdited)
                    proxy.append(image)
    
                proxy.setCurrent(files[0].filePath())
                self.setImageProxy(proxy)
                self.scrollPanel.show()

                if self.saveImageConnected:
                    self.imageSaved.disconnect(self.saveImage)
                    self.saveImageConnected = False

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

    def imageEdited(self, image):
        image.image.save(image.field)

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
