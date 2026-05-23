# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Vortex. Run with: pyinstaller Vortex.spec

import customtkinter
import imageio_ffmpeg
from pathlib import Path

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
    icon=None,
    bundle_identifier='com.vortex.app',
    info_plist={
        'CFBundleName':              'Vortex',
        'CFBundleDisplayName':       'Vortex',
        'CFBundleShortVersionString':'0.1.1',
        'CFBundleVersion':           '0.1.1',
        'NSHighResolutionCapable':   True,
        'LSMinimumSystemVersion':    '10.13.0',
    },
)
