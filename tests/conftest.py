"""Point HOME at a temporary folder before vortex is imported, so tests never
touch the real ~/.vortex (settings, history, downloaded yt-dlp)."""
import os
import sys
import tempfile
from pathlib import Path

import pytest

_home = tempfile.mkdtemp(prefix="vortex-test-home-")
os.environ["HOME"] = _home
os.environ["USERPROFILE"] = _home
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def pytest_addoption(parser):
    parser.addoption("--network", action="store_true",
                     help="also run tests that download from YouTube and GitHub")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--network"):
        return
    skip = pytest.mark.skip(reason="needs --network")
    for item in items:
        if "network" in item.keywords:
            item.add_marker(skip)
