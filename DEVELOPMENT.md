# Developing Vortex

How to run Vortex from source, test it, build it and release a new version.
For what the app does, see the [README](README.md).

## Running from source

You need Python 3.10 or newer.

```bash
git clone https://github.com/FarAbove420/vortex.git
cd vortex
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### Tests

```bash
pip install -r requirements-dev.txt
python -m pytest                 # fast, offline
python -m pytest --network       # also real downloads from YouTube and GitHub
```

Tests use a temporary home folder, so they never touch your own `~/.vortex`.

### Code layout

| Path | What's in it |
|---|---|
| `main.py` | Starts the app |
| `vortex/config.py` | Paths, logging, settings |
| `vortex/ytdl.py` | The one place yt-dlp is imported |
| `vortex/media.py` | Download options, downloading, preview, search, thumbnails |
| `vortex/updater.py` | yt-dlp, Deno and Vortex updates |
| `vortex/history.py` | Download history |
| `vortex/system.py` | Opening files, notifications, single instance |
| `vortex/ui/` | The window and one file per tab |

## How updates work

- **yt-dlp** is downloaded to `~/.vortex/yt-dlp/` and checked against the
  release's `SHA2-256SUMS`. The previous download is kept as a fallback.
- **Deno** is downloaded to `~/.vortex/bin/` and checked against its
  `.sha256sum` file.

Versions are read from where `github.com/<project>/releases/latest` redirects
to, so the GitHub API's limit of 60 requests per hour doesn't apply. The
checksums protect against broken downloads; like `yt-dlp -U`, Vortex doesn't
check signatures.

## Building the app

GitHub Actions builds both versions: push a tag like `v0.3.0` and
`.github/workflows/release.yml` builds Windows (Intel/AMD and a native ARM64
build, both in one installer that picks the right one) and macOS, and publishes a
release with the notes from [CHANGELOG.md](CHANGELOG.md). "Run workflow" on the
Actions tab builds without publishing.

To build yourself:

- **Windows**: see [WINDOWS_BUILD.md](WINDOWS_BUILD.md). It produces
  `Vortex.exe` and a `Vortex-Setup.exe` installer.
- **macOS**: needs a universal2 Python from python.org. Fetch the Intel FFmpeg
  binary once, then build:

  ```bash
  pip install -r requirements-build.txt
  ./vendor/fetch-x86_64-ffmpeg.sh
  pyinstaller Vortex.spec --noconfirm
  ```

  The result is `dist/Vortex.app`.

The app icon is drawn by `assets/make_icon.py`, which writes `icon.png`,
`Vortex.icns` and `Vortex.ico`. Only run it again if you change the design
(it needs Pillow, and macOS for the `.icns`).

Drag and drop isn't supported because Tk needs a native add-on for it
(tkdnd), which breaks the universal macOS build.

### Releasing a new version

1. Update the version in three places: `__version__` in `vortex/__init__.py`
   (the macOS build reads it from there), `MyAppVersion` in `Vortex.iss`, and
   `version_info.txt`.
2. Add a section for it to `CHANGELOG.md`.
3. Commit, then tag and push: `git tag v0.3.0 && git push origin v0.3.0`.
   The workflow refuses a tag that doesn't match `vortex/__init__.py`.
