import json
import os
from datetime import datetime, timezone


class ConfigManager:
    """Manages ~/.talky_config.json for setup state persistence."""

    def __init__(self, path="~/.talky_config.json"):
        self._path = os.path.expanduser(path)
        self._data = {}
        self.load()

    def load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, "r") as f:
                    self._data = json.load(f)
            except Exception as e:
                print(f"[core_config] Error loading config: {e}")
                self._data = {}

    def save(self):
        try:
            with open(self._path, "w") as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            print(f"[core_config] Error saving config: {e}")

    def is_setup_complete(self) -> bool:
        return self._data.get("has_completed_setup", False)

    def mark_setup_complete(self):
        self._data["has_completed_setup"] = True
        self._data["setup_completed_at"] = datetime.now(timezone.utc).isoformat()
        self.save()
