import sys
from PySide6.QtCore import QCoreApplication, QLibraryInfo, QLocale, QTranslator
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from ImageEditorWindow import ImageEditorWindow
from Tools import TemporaryDir


def main():
    app = QApplication(sys.argv)

    QCoreApplication.setOrganizationName('Janis')
    QCoreApplication.setApplicationName('ImageEditor')

    TemporaryDir.init('ImageEditor')

    locale = QLocale()

    translator = QTranslator(app)
    if translator.load(locale, 'lang', '_', ':/i18n'):
        app.installTranslator(translator)

    path = QLibraryInfo.path(QLibraryInfo.TranslationsPath)
    translator = QTranslator(app)
    if translator.load(locale, 'qtbase', '_', path):
        app.installTranslator(translator)

    dlg = ImageEditorWindow()
    if len(sys.argv) > 1:
        file_name = sys.argv[1]
        dlg.loadFromFile(file_name)
    dlg.exec()

    # Clear temporary files
    TemporaryDir.remove()


if __name__ == "__main__":
    import resources
    main()
