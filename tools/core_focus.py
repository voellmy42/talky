"""macOS destination identity. Never read the contents of the input field."""
from dataclasses import dataclass

import AppKit
import ApplicationServices as AX
from CoreFoundation import CFEqual


@dataclass(frozen=True)
class Destination:
    pid: int
    window: object
    field: object
    selection: object = None


class FocusTracker:
    @staticmethod
    def _attribute(element, name):
        error, value = AX.AXUIElementCopyAttributeValue(element, name, None)
        return value if error == AX.kAXErrorSuccess else None

    def capture(self):
        try:
            app = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
            if app is None:
                return None
            pid = app.processIdentifier()
            element = AX.AXUIElementCreateApplication(pid)
            AX.AXUIElementSetMessagingTimeout(element, 0.15)
            window = self._attribute(element, AX.kAXFocusedWindowAttribute)
            field = self._attribute(element, AX.kAXFocusedUIElementAttribute)
            if window is None or field is None:
                return None
            role = self._attribute(field, AX.kAXRoleAttribute)
            subrole = self._attribute(field, AX.kAXSubroleAttribute)
            if role not in ('AXTextField', 'AXTextArea', 'AXComboBox') or subrole == 'AXSecureTextField':
                return None
            selection = self._attribute(field, AX.kAXSelectedTextRangeAttribute)
            return Destination(pid, window, field, selection)
        except Exception:
            return None

    def matches(self, target):
        current = self.capture()
        if target is None or current is None or target.pid != current.pid:
            return False
        if not CFEqual(target.window, current.window) or not CFEqual(target.field, current.field):
            return False
        if target.selection is not None:
            return current.selection is not None and bool(CFEqual(target.selection, current.selection))
        return True
