# Building Vortex on Windows

Step-by-step guide to produce `Vortex-Setup.exe` (the Windows installer) from
source. Do the **one-time setup** once per machine. After that, every build is
just `build-win.bat`.

---

## One-time setup

### 1. Install Python

Download Python 3.10 or newer from <https://www.python.org/downloads/windows/>.
Run the installer and **tick the "Add python.exe to PATH" checkbox** on the
first screen. Default settings otherwise.

Verify in a new Command Prompt:

```
python --version
pip --version
```

Both should print a version.

### 2. Clone the repo

```
cd %USERPROFILE%\Documents
git clone https://github.com/FarAbove420/vortex.git
cd vortex
```

If you don't have `git`, install it from <https://git-scm.com/download/win>.

### 3. Install Python dependencies

From inside the `vortex` folder:

```
pip install -r requirements-build.txt
```

This installs CustomTkinter, yt-dlp (with its optional extras), certifi,
imageio-ffmpeg, and PyInstaller.

### 4. Install Inno Setup

Download from <https://jrsoftware.org/isdl.php> and run the installer.
Inno Setup is what wraps `Vortex.exe` into a single `Vortex-Setup.exe`
installer.

Default install location is fine. The build script will find `ISCC.exe`
(Inno Setup's compiler) automatically.

---

## Building

In the `vortex` folder:

```
build-win.bat
```

The script runs three steps:

1. Cleans `build\` and the previous `dist\Vortex.exe` and `dist\Vortex-Setup.exe`
2. Runs PyInstaller using `Vortex-win.spec` to produce `dist\Vortex.exe` (one self-contained file)
3. Runs Inno Setup using `Vortex.iss` to produce `dist\Vortex-Setup.exe`

When it finishes:

- **`dist\Vortex-Setup.exe`** is the installer to share or run.
- **`dist\Vortex.exe`** is the app itself, useful for testing without
  installing.

---

## Installing the result

Double-click `Vortex-Setup.exe`. Because the installer is **unsigned**,
Windows SmartScreen will show a blue "Windows protected your PC" dialog:

1. Click **More info**
2. Click **Run anyway**
3. Walk through the wizard (Next, Next, Install)

The app installs to `%LOCALAPPDATA%\Programs\Vortex\` (per-user) by default;
you can switch to a system-wide install (Program Files) on the
"Privilege" page of the wizard.

---

## Updating

When `main.py` or any dependency changes:

```
git pull
pip install -U -r requirements-build.txt   # new deps and the latest yt-dlp
build-win.bat
```

The new installer overwrites `dist\Vortex-Setup.exe`.

---

## Troubleshooting

**`'python' is not recognized as an internal or external command`**
Python wasn't added to PATH during install. Reinstall Python with the "Add
python.exe to PATH" checkbox ticked, or add it to PATH manually.

**`Could not find ISCC.exe`** at step [3/3]
Inno Setup isn't installed, or it's in an unusual location. Reinstall from
<https://jrsoftware.org/isdl.php> with default settings.

**PyInstaller error: `No module named 'customtkinter'`**
`pip install -r requirements-build.txt` wasn't run, or was run in a different
Python environment than the one on PATH. Re-run it from this folder.

**`Vortex.exe` launches but crashes immediately**
A crash during startup shows a traceback dialog. Errors after the window
opens go to `%USERPROFILE%\.vortex\vortex.log`. Most common cause: a
missing data file. Add it to the `datas` list in `Vortex-win.spec` and
rebuild.
