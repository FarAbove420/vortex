@echo off
REM Vortex Windows build script.
REM Run from the repo root in a Command Prompt with Python on PATH.
REM Requires:
REM   - Python 3.10+ with `pip install -r requirements-build.txt`
REM   - Inno Setup 6 installed (https://jrsoftware.org/isdl.php)
REM See WINDOWS_BUILD.md for full setup steps.

setlocal enabledelayedexpansion

echo === [1/3] Cleaning old build artifacts ===
if exist build  rmdir /s /q build
if exist "dist\Vortex.exe"  del /q "dist\Vortex.exe"
if exist "dist\Vortex-Setup.exe"  del /q "dist\Vortex-Setup.exe"

echo.
echo === [2/3] Building Vortex.exe with PyInstaller ===
pyinstaller Vortex-win.spec --noconfirm
if errorlevel 1 (
    echo.
    echo PyInstaller failed. See messages above.
    exit /b 1
)
if not exist "dist\Vortex.exe" (
    echo.
    echo PyInstaller finished but dist\Vortex.exe is missing. Aborting.
    exit /b 1
)

echo.
echo === [3/3] Building installer with Inno Setup ===

REM Find ISCC.exe (Inno Setup compiler).
REM First try PATH, then the default install location.
set "ISCC="
for /f "delims=" %%i in ('where ISCC 2^>nul') do set "ISCC=%%i"
if "!ISCC!"=="" (
    if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
)
if "!ISCC!"=="" (
    if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
)
if "!ISCC!"=="" (
    if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
)
if "!ISCC!"=="" (
    echo.
    echo Could not find ISCC.exe ^(Inno Setup 6 compiler^).
    echo Install Inno Setup 6 from https://jrsoftware.org/isdl.php
    echo and re-run this script.
    exit /b 1
)

echo Using ISCC at: !ISCC!
"!ISCC!" Vortex.iss
if errorlevel 1 (
    echo.
    echo Inno Setup compile failed. See messages above.
    exit /b 1
)

echo.
echo === Done ===
echo Installer: dist\Vortex-Setup.exe
echo App:       dist\Vortex.exe
endlocal
