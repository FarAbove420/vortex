# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Vortex on Windows.
# Run with: pyinstaller Vortex-win.spec --noconfirm
#
# Produces dist/Vortex/Vortex.exe in "one-folder" mode (Vortex.exe alongside
# its DLLs and resource folder). One-folder is what Inno Setup expects.

import customtkinter
import imageio_ffmpeg
from pathlib import Path

CTK_PATH               = Path(customtkinter.__file__).parent
IMAGEIO_FFMPEG_BIN_DIR = Path(imageio_ffmpeg.__file__).parent / 'binaries'

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # CustomTkinter theme JSON + fonts
        (str(CTK_PATH / 'assets'), 'customtkinter/assets'),
        # imageio-ffmpeg's bundled static ffmpeg.exe. Bundling the whole
        # binaries folder lets imageio_ffmpeg.get_ffmpeg_exe() find it at
        # runtime the same way it does in development.
        (str(IMAGEIO_FFMPEG_BIN_DIR), 'imageio_ffmpeg/binaries'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Vortex',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,                     # no terminal window on launch
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,                         # add a path to Vortex.ico here later
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Vortex',
)
