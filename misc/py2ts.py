#!/usr/bin/env python3

import os
from PySide6.QtCore import QLibraryInfo

base_path = os.path.join(os.path.dirname(__file__), "../src")

pyqt_path = QLibraryInfo.path(QLibraryInfo.LibraryExecutablesPath)
lupdate_path = os.path.join(pyqt_path, 'lupdate')

src_files = []
for dirname, _, filenames in os.walk(base_path):
    for filename in filenames:
        _, file_extension = os.path.splitext(filename)
        if file_extension in ('.py', '.ui'):
            src_files.append(os.path.join(dirname, filename))

dst_file = os.path.join(base_path, "i18n/lang.ts")
os.system(' '.join([lupdate_path, ' '.join(src_files), '-ts', dst_file, '-noobsolete', '-locations', 'none']))
#os.system(' '.join([lupdate_path, base_path, '-ts', dst_file, '-noobsolete', '-extensions', ','.join(['py', 'ui'])]))
