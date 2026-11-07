# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Vortex on Windows.
# Run with: pyinstaller Vortex-win.spec --noconfirm
#
# Produces dist/Vortex.exe in one-file mode (single self-contained executable).

import customtkinter
import imageio_ffmpeg
from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata

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
        # Window icon (the .exe icon itself is set below)
        ('assets/Vortex.ico', 'assets'),
    # yt-dlp's version metadata: updater.py reads it to compare with
    # the downloaded yt-dlp without importing the built-in one
    ] + copy_metadata('yt-dlp'),
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PIL'],                  # Pillow is only for assets/make_icon.py
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    exclude_binaries=False,
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
    icon='assets/Vortex.ico',
    version='version_info.txt',
    onefile=True,
)
