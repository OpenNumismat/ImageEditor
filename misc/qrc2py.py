#!/usr/bin/env python3

import os
from PySide6.QtCore import QLibraryInfo

base_path = os.path.join(os.path.dirname(__file__), "../src")

pyqt_path = QLibraryInfo.path(QLibraryInfo.LibraryExecutablesPath)
rcc_path = os.path.join(pyqt_path, 'rcc')
src_file = os.path.join(base_path, "resources.qrc")
dst_file = os.path.join(base_path, "resources.py")
os.system(' '.join([rcc_path, src_file, '-no-compress', '-o', dst_file, '--generator', 'python']))
