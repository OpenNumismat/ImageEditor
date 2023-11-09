import sys
from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QDialog
from ImageEditor import ImageEditorDialog
from Tools import TemporaryDir


def main():
    app = QApplication(sys.argv)

    TemporaryDir.init('ImageEditor')

    locale = QLocale()

    translator = QTranslator(app)
    if translator.load(locale, 'lang', '_', ':/i18n'):
        app.installTranslator(translator)

    path = QLibraryInfo.path(QLibraryInfo.TranslationsPath)
    translator = QTranslator(app)
    if translator.load(locale, 'qtbase', '_', path):
        app.installTranslator(translator)

    if len(sys.argv) > 1:
        file_name = sys.argv[1]
        image = QImage(file_name)
    else:
        image = None

    dlg = ImageEditorDialog()
    dlg.setWindowTitle('ImageEditor')
    if image:
        dlg.setImage(image)
    dlg.exec()

    # Clear temporary files
    TemporaryDir.remove()


if __name__ == "__main__":
    import resources
    main()
