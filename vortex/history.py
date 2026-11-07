"""Finished downloads, kept in ~/.vortex/history.json across restarts."""
import json
import os
from datetime import datetime

from .config import HISTORY_PATH, log

MAX_ENTRIES = 300


def load() -> list[dict]:
    try:
        data = json.loads(HISTORY_PATH.read_text())
        return data if isinstance(data, list) else []
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as e:
        log.warning("History unreadable: %s", e)
        return []


def _save(entries: list[dict]):
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = HISTORY_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(entries[:MAX_ENTRIES], indent=1))
    os.replace(tmp, HISTORY_PATH)


def add(title: str, url: str, filepath: str, status: str):
    entries = load()
    entries.insert(0, {
        "title": title, "url": url, "filepath": filepath, "status": status,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    try:
        _save(entries)
    except OSError as e:
        log.warning("Could not save history: %s", e)


def clear():
    try:
        _save([])
    except OSError as e:
        log.warning("Could not clear history: %s", e)
