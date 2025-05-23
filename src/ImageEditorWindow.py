from PySide6.QtCore import QSettings, QFileInfo, Qt, QStandardPaths, QDir
from PySide6.QtGui import QIcon, QAction, QBrush, QColor, QImage
from PySide6.QtWidgets import QApplication, QStyle, QMessageBox, QDialog, QFileDialog, QHBoxLayout, QGroupBox, QRadioButton

from ImageEditor import ImageEditorDialog, SettingsDialog
from ImageProxy import ImageProxy
from ImageScrollLabel import ImageScrollLabel
from Tools.Gui import getSaveFileName, ColorButton
from Tools.misc import saveImageFilters

IMAGE_PATH = QStandardPaths.standardLocations(QStandardPaths.PicturesLocation)[0]


class WindowSettingsDialog(SettingsDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        settings = QSettings()

        color = settings.value('mainwindow/transparent_color', QColor(Qt.white), type=QColor)
        self.transparentColorButton = ColorButton(color, self)

        self.transparentRadio = QRadioButton(self.tr("Transparent"))
        self.transparentRadio.toggled.connect(self.transparentRadioToggled)
        self.colorRadio = QRadioButton(self.tr("Color"))
        if settings.value('mainwindow/transparent_store', True, type=bool):
            self.transparentRadio.setChecked(True)
        else:
            self.colorRadio.setChecked(True)

        colorBtnLayout = QHBoxLayout()
        colorBtnLayout.addWidget(self.colorRadio)
        colorBtnLayout.addWidget(self.transparentColorButton)
        colorBtnLayout.setAlignment(Qt.AlignLeft)

        colorLayout = QHBoxLayout()
        colorLayout.addWidget(self.transparentRadio)
        colorLayout.addLayout(colorBtnLayout)

        colorGroup = QGroupBox(self.tr("Image background color"), self)
        colorGroup.setLayout(colorLayout)

        self.main_layout.addRow(colorGroup)

    def transparentRadioToggled(self, checked):
        self.transparentColorButton.setDisabled(checked)

    def save(self):
        settings = QSettings()

        settings.setValue('mainwindow/transparent_store', self.transparentRadio.isChecked())
        settings.setValue('mainwindow/transparent_color', self.transparentColorButton.color())

        super().save()


class ImageEditorWindow(ImageEditorDialog):

    def __init__(self, parent=None):
        super().__init__(parent, scrollpanel=True)

        self.navigationMenu.removeAction(self.prevRecordAct)
        self.navigationMenu.removeAction(self.nextRecordAct)

        self.setWindowIcon(QIcon(':/slide.png'))
        
        self.viewer.doubleClicked.connect(self.viewerDoubleClicked)

        self.scrollPanel.hide()

        self.saveImageConnected = False

    def createActions(self):
        super().createActions()

        style = QApplication.style()
        icon = style.standardIcon(QStyle.SP_DirOpenIcon)
        self.openFolderAct = QAction(icon, self.tr("Open folder..."), self, triggered=self.openFolder)

    def createMenus(self):
        super().createMenus()

        self.fileMenu.insertAction(self.saveAct, self.openFolderAct)

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
            self.navigationMenu.setEnabled(False)

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
                self.navigationMenu.setEnabled(True)

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

    def settings(self):
        dlg = WindowSettingsDialog(self)
        if dlg.exec() == QDialog.Accepted:
            color = dlg.windowColorButton.color()
            self.viewer.setBackgroundBrush(QBrush(color))

    def _updateEditActions(self):
        super()._updateEditActions()

        inCrop = self.cropAct.isChecked()
        inRotate = self.rotateAct.isChecked()
        self.openFolderAct.setDisabled(inCrop or inRotate)
