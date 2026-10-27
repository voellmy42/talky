"""macOS destination identity and explicitly selected text; never read the whole field."""
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
    selected_text: str = ''
    selection_kind: str = 'caret'


class FocusTracker:
    @staticmethod
    def _range(value):
        if value is None:
            return None
        try:
            ok, span = AX.AXValueGetValue(value, AX.kAXValueCFRangeType, None)
            return tuple(span) if ok and span[0] >= 0 and span[1] >= 0 else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _editable(field):
        for name in (AX.kAXSelectedTextAttribute, AX.kAXValueAttribute):
            error, writable = AX.AXUIElementIsAttributeSettable(field, name, None)
            if error == AX.kAXErrorSuccess and writable:
                return True
        return False

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
            AX.AXUIElementSetMessagingTimeout(field, 0.15)
            role = self._attribute(field, AX.kAXRoleAttribute)
            subrole = self._attribute(field, AX.kAXSubroleAttribute)
            if role not in ('AXTextField', 'AXTextArea', 'AXComboBox') or subrole == 'AXSecureTextField':
                return None
            selection = self._attribute(field, AX.kAXSelectedTextRangeAttribute)
            span = self._range(selection)
            text, kind = '', 'caret'
            if span is None or span[1] > 0:
                selected = self._attribute(field, AX.kAXSelectedTextAttribute)
                if span is not None and span[1] > 0:
                    if (isinstance(selected, str) and selected
                            and len(selected.encode('utf-16-le')) // 2 == span[1]
                            and self._editable(field)):
                        text, kind = selected, 'text'
                    else:
                        kind = 'unavailable'
                elif selected != '':
                    kind = 'unavailable'
            return Destination(pid, window, field, selection, text, kind)
        except Exception:
            return None

    def matches(self, target):
        current = self.capture()
        if target is None or current is None or target.pid != current.pid:
            return False
        if not CFEqual(target.window, current.window) or not CFEqual(target.field, current.field):
            return False
        if target.selection is not None:
            if current.selection is None or not CFEqual(target.selection, current.selection):
                return False
        return (target.selection_kind == current.selection_kind
                and target.selected_text == current.selected_text)
