# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Vortex. Run with: pyinstaller Vortex.spec

import re
import customtkinter
import imageio_ffmpeg
from pathlib import Path

# Single source for the version number: __version__ in main.py
VERSION = re.search(r'__version__ = "([^"]+)"',
                    (Path(SPECPATH) / 'main.py').read_text()).group(1)

CTK_PATH      = Path(customtkinter.__file__).parent
IMAGEIO_FFMPEG_BIN_DIR = Path(imageio_ffmpeg.__file__).parent / 'binaries'
# x86_64 ffmpeg vendored from the macosx_10_9_x86_64 wheel on PyPI, so the
# universal2 bundle has an Intel binary too. imageio_ffmpeg picks the right
# one at runtime via FNAME_PER_PLATFORM.
VENDOR_FFMPEG_X86_64 = Path(SPECPATH) / 'vendor' / 'ffmpeg-macos-x86_64-v7.1'

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        (str(CTK_PATH / 'assets'), 'customtkinter/assets'),
        (str(IMAGEIO_FFMPEG_BIN_DIR), 'imageio_ffmpeg/binaries'),
        (str(VENDOR_FFMPEG_X86_64), 'imageio_ffmpeg/binaries'),
        ('assets/icon.png', 'assets'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # websockets' optional C speedups ship as an arm64-only wheel, which
    # breaks the universal2 build. websockets falls back to pure Python.
    # PIL (Pillow) is only used by assets/make_icon.py, not by the app.
    excludes=['websockets.speedups', 'PIL'],
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
    target_arch='universal2',
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
    icon='assets/Vortex.icns',
    bundle_identifier='com.vortex.app',
    info_plist={
        'CFBundleName':              'Vortex',
        'CFBundleDisplayName':       'Vortex',
        'CFBundleShortVersionString':VERSION,
        'CFBundleVersion':           VERSION,
        'NSHighResolutionCapable':   True,
        'LSMinimumSystemVersion':    '10.13.0',
    },
)
