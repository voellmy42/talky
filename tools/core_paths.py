import sys
import os


def resource_path(relative_path):
    """Resolve path to bundled resource (works both from source and PyInstaller .app)."""
    if getattr(sys, '_MEIPASS', None):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), relative_path)
