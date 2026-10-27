import json
import os
from datetime import datetime, timezone


class ConfigManager:
    """Manages ~/.talky_config.json for setup state persistence."""

    VALID_LANGUAGES = {"de", "en"}
    VALID_FORMATTING_MODES = {"fast", "polished"}
    VALID_TOGGLE_SHORTCUTS = {'section', 'ctrl_shift_space', 'off'}

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
        temp_path = f"{self._path}.tmp"
        try:
            parent = os.path.dirname(self._path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(temp_path, "w") as f:
                json.dump(self._data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, self._path)
        except Exception as e:
            print(f"[core_config] Error saving config: {e}")
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except OSError:
                pass

    def is_setup_complete(self) -> bool:
        return self._data.get("has_completed_setup", False)

    def mark_setup_complete(self):
        self._data["has_completed_setup"] = True
        self._data["setup_completed_at"] = datetime.now(timezone.utc).isoformat()
        self.save()

    def get_language(self) -> str:
        language = self._data.get("language", "en")
        return language if language in self.VALID_LANGUAGES else "en"

    def set_language(self, language: str):
        if language not in self.VALID_LANGUAGES:
            raise ValueError(f"Unsupported language: {language}")
        self._data["language"] = language
        self.save()

    def get_formatting_mode(self) -> str:
        mode = self._data.get("formatting_mode", "fast")
        return mode if mode in self.VALID_FORMATTING_MODES else "fast"

    def get_ai_editing_enabled(self) -> bool:
        # Preserve the user's explicit AI choice from the polishing preview.
        return self._data.get('ai_editing_enabled', self.get_formatting_mode() == 'polished') is True

    def set_ai_editing_enabled(self, enabled):
        self._data['ai_editing_enabled'] = bool(enabled)
        self.save()

    def set_formatting_mode(self, mode: str):
        if mode not in self.VALID_FORMATTING_MODES:
            raise ValueError(f"Unsupported formatting mode: {mode}")
        self._data["formatting_mode"] = mode
        self.save()

    def get_toggle_shortcut(self):
        shortcut = self._data.get('toggle_shortcut', 'section')
        return shortcut if shortcut in self.VALID_TOGGLE_SHORTCUTS else 'section'

    def set_toggle_shortcut(self, shortcut):
        if shortcut not in self.VALID_TOGGLE_SHORTCUTS:
            raise ValueError(f'Unsupported shortcut: {shortcut}')
        self._data['toggle_shortcut'] = shortcut
        self.save()
