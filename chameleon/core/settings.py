"""Remembering the user's choices between runs, in a small JSON file in the user's settings folder."""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path

log = logging.getLogger(__name__)


def settings_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "Chameleon" / "settings.json"


@dataclass(slots=True)
class Settings:
    output_format: str = "jpeg"  # an OutputFormat value
    quality: int = 90
    keep_metadata: bool = True
    remove_location: bool = False
    existing: str = "skip"  # an ExistingFiles value
    include_subfolders: bool = True
    save_next_to_originals: bool = True
    destination: str = ""
    workers: int = 0  # 0: the default for this computer
    last_folder: str = ""

    @classmethod
    def load(cls, path: Path | None = None) -> Settings:
        path = path or settings_path()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return cls()
        except (OSError, ValueError):
            log.warning("Ignoring unreadable settings file %s", path, exc_info=True)
            return cls()
        if not isinstance(data, dict):
            return cls()
        known = {field.name: field for field in fields(cls)}
        defaults = cls()
        values = {}
        for key, value in data.items():
            # Keep only known settings of the right type, so a hand-edited file can't break the app.
            if key in known and isinstance(value, type(getattr(defaults, key))):
                values[key] = value
        return cls(**values)

    def save(self, path: Path | None = None) -> None:
        path = path or settings_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        except OSError:
            log.warning("Could not save settings to %s", path, exc_info=True)
