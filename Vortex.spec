# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Vortex. Run with: pyinstaller Vortex.spec

import customtkinter
import imageio_ffmpeg
from pathlib import Path

CTK_PATH      = Path(customtkinter.__file__).parent
IMAGEIO_FFMPEG_BIN_DIR = Path(imageio_ffmpeg.__file__).parent / 'binaries'

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # CustomTkinter ships theme JSON + fonts in an 'assets' folder.
        (str(CTK_PATH / 'assets'), 'customtkinter/assets'),
        # imageio-ffmpeg's bundled static ffmpeg binary. Bundling the whole
        # 'binaries' folder lets imageio_ffmpeg.get_ffmpeg_exe() find it the
        # same way it does in normal Python.
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
    console=False,                     # windowed app, no terminal
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
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

app = BUNDLE(
    coll,
    name='Vortex.app',
    icon=None,
    bundle_identifier='com.vortex.app',
    info_plist={
        'CFBundleName':              'Vortex',
        'CFBundleDisplayName':       'Vortex',
        'CFBundleShortVersionString':'0.1.0',
        'CFBundleVersion':           '0.1.0',
        'NSHighResolutionCapable':   True,
        'LSMinimumSystemVersion':    '10.13.0',
    },
)
