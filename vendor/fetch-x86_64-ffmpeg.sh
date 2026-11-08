#!/usr/bin/env bash
# Fetch the x86_64 ffmpeg slice used by the macOS universal2 build of Vortex.
#
# imageio-ffmpeg ships per-arch wheels on PyPI rather than as GitHub release
# assets, so we grab the macOS x86_64 wheel and pull the ffmpeg binary out of
# it. The arm64 slice already comes with the imageio-ffmpeg installed in your
# Python environment; this script only covers the Intel half.
#
# Re-run is safe: if the binary is already in place, the script exits cleanly.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="$SCRIPT_DIR/ffmpeg-macos-x86_64-v9.0.2"

WHEEL_URL="https://files.pythonhosted.org/packages/da/24/2c3a7c69453bfb8374ddbbb5007346bad4a4247bc86882f3521cd615f929/imageio_ffmpeg-0.8.1-py3-none-macosx_10_13_x86_64.whl"
# SHA-256 of the wheel as published on PyPI:
# https://pypi.org/pypi/imageio-ffmpeg/0.8.1/json
WHEEL_SHA256="9538a10e598257263b5de1a1c1b86e7603417bc219245b1e279b452e5e48cc20"
WHEEL_INNER_PATH="imageio_ffmpeg/binaries/ffmpeg-macos-x86_64-v9.0.2"

if [[ -x "$TARGET" ]]; then
    echo "Already present: $TARGET"
    exit 0
fi

TMP_WHEEL="$(mktemp -t iio_ffmpeg_x86.XXXXXX).whl"
trap 'rm -f "$TMP_WHEEL"' EXIT

echo "Downloading imageio-ffmpeg 0.8.1 x86_64 wheel..."
curl -fsSL -o "$TMP_WHEEL" "$WHEEL_URL"

echo "Verifying checksum..."
echo "$WHEEL_SHA256  $TMP_WHEEL" | shasum -a 256 -c -

echo "Extracting $WHEEL_INNER_PATH..."
unzip -p "$TMP_WHEEL" "$WHEEL_INNER_PATH" > "$TARGET"
chmod +x "$TARGET"

echo "Done: $TARGET"
file "$TARGET"
