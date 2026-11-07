# Third-party software

Vortex's own code is MIT licensed (see `LICENSE`). The packaged app (the
Windows installer and the macOS app) also contains the software below, each
under its own license.

| Component | What it does in Vortex | License | Source |
|---|---|---|---|
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Downloads the media | Unlicense | https://github.com/yt-dlp/yt-dlp |
| [yt-dlp-ejs](https://github.com/yt-dlp/ejs) | Helps yt-dlp with YouTube's JavaScript challenges | Unlicense AND MIT AND ISC | https://github.com/yt-dlp/ejs |
| [FFmpeg](https://ffmpeg.org) | Merges, converts and trims media | GPL (see below) | https://ffmpeg.org/download.html |
| [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) | Provides the FFmpeg binaries | BSD-2-Clause | https://github.com/imageio/imageio-ffmpeg |
| [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) | User interface | MIT | https://github.com/TomSchimansky/CustomTkinter |
| [certifi](https://github.com/certifi/python-certifi) | HTTPS certificate list | MPL-2.0 | https://github.com/certifi/python-certifi |
| [Python](https://www.python.org) and Tcl/Tk | Runtime, bundled by PyInstaller | PSF License, Tcl/Tk license | https://www.python.org/downloads/source/ |

## FFmpeg

The FFmpeg 7.1 binaries come from the imageio-ffmpeg 0.6.0 wheels on PyPI.
They are built with `--enable-gpl` (and include libx264 and libx265), so the
FFmpeg binary is licensed under the GNU General Public License. Vortex runs
FFmpeg as a separate program and does not link to it.

To see the exact build configuration of the bundled binary, run it with
`-version`. The FFmpeg source code is available at
https://ffmpeg.org/download.html and the license terms at
https://ffmpeg.org/legal.html.
