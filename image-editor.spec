# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['src/run.py'],
    pathex=['src'],
    binaries=[],
    datas=[("LICENSE", ".")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

import ImageEditor

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=ImageEditor.__name__,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='src/icons/slide.png',
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version="versionfile.txt",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=ImageEditor.__name__,
)
