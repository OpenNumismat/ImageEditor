import os

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QFileDialog, QApplication


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
