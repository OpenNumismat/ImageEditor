import sys
from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QDialog
from ImageEditor import ImageEditorDialog


def main():
    app = QApplication(sys.argv)

    locale = QLocale()

    translator = QTranslator(app)
    if translator.load(locale, 'lang', '_', ':/i18n'):
        app.installTranslator(translator)

    path = QLibraryInfo.path(QLibraryInfo.TranslationsPath)
    translator = QTranslator(app)
    if translator.load(locale, 'qtbase', '_', path):
        app.installTranslator(translator)

    image = QImage("C:/Users/ignatov_vi/Documents/OpenNumismat/Area_20230309.png")

    dlg = ImageEditorDialog()
    dlg.setWindowTitle('ImageEditor')
    dlg.setImage(image)
    dlg.exec()


if __name__ == "__main__":
    import resources
    main()
