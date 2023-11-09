import os

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QProgressDialog, QFileDialog, QApplication, QCheckBox, QMessageBox


def getSaveFileName(parent, name, filename, dir_, filters):
    if isinstance(filters, str):
        filters = (filters,)
    settings = QSettings()
    keyDir = name + '/last_dir'
    keyFilter = name + '/last_filter'
    lastExportDir = settings.value(keyDir, dir_)
    defaultFileName = os.path.join(lastExportDir, filename)
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
