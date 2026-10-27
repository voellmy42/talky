import sys
import threading
import time

import pyautogui
import pyperclip

if sys.platform == "darwin":
    import AppKit
    import Quartz


class OutputInjector:
    """Pastes text at the cursor while preserving the user's clipboard."""

    def __init__(self, restore_delay=0.35, focus_tracker=None):
        pyautogui.PAUSE = 0.02
        self._restore_delay = restore_delay
        self._clipboard_lock = threading.Lock()
        self._clipboard_generation = 0
        self._saved_clipboard = None
        self.focus_tracker = focus_tracker

    def copy(self, text):
        """An explicit user copy owns the clipboard until they replace it."""
        with self._clipboard_lock:
            self._clipboard_generation += 1
            self._saved_clipboard = None
            self._set_clipboard_text(text)

    def deliver(self, text, target, dispatch):
        if self.focus_tracker is None or not self.focus_tracker.matches(target):
            return 'available'

        def guarded_send(send):
            def checked_send():
                if not self.focus_tracker.matches(target):
                    raise RuntimeError('Destination changed')
                send()
            return dispatch(checked_send)

        return 'sent' if self.inject(text, guarded_send) else 'available'

    def _snapshot_clipboard(self):
        if sys.platform != "darwin":
            return pyperclip.paste()

        pasteboard = AppKit.NSPasteboard.generalPasteboard()
        if pasteboard is None:
            raise RuntimeError("macOS pasteboard is unavailable")
        snapshot = []
        for pasteboard_item in pasteboard.pasteboardItems() or []:
            values = []
            for pasteboard_type in pasteboard_item.types() or []:
                data = pasteboard_item.dataForType_(pasteboard_type)
                if data is not None:
                    values.append((pasteboard_type, data.copy()))
            snapshot.append(values)
        return snapshot

    def _set_clipboard_text(self, text):
        if sys.platform != "darwin":
            pyperclip.copy(text)
            return None

        pasteboard = AppKit.NSPasteboard.generalPasteboard()
        if pasteboard is None:
            raise RuntimeError("macOS pasteboard is unavailable")
        pasteboard.clearContents()
        if not pasteboard.setString_forType_(text, AppKit.NSPasteboardTypeString):
            raise RuntimeError('Could not write to macOS pasteboard')
        return pasteboard.changeCount()

    def _restore_clipboard(self, snapshot):
        if sys.platform != "darwin":
            pyperclip.copy(snapshot)
            return
        items = []
        for values in snapshot:
            item = AppKit.NSPasteboardItem.alloc().init()
            for pasteboard_type, data in values:
                item.setData_forType_(data, pasteboard_type)
            items.append(item)

        pasteboard = AppKit.NSPasteboard.generalPasteboard()
        pasteboard.clearContents()
        if items:
            pasteboard.writeObjects_(items)

    def _clipboard_was_replaced(self, expected_change_count):
        if sys.platform != "darwin" or expected_change_count is None:
            return False
        pasteboard = AppKit.NSPasteboard.generalPasteboard()
        if pasteboard is None:
            return False
        return pasteboard.changeCount() != expected_change_count

    @staticmethod
    def _send_paste_shortcut():
        if sys.platform != "darwin":
            pyautogui.hotkey("ctrl", "v")
            return

        source = Quartz.CGEventSourceCreate(
            Quartz.kCGEventSourceStateCombinedSessionState
        )
        command_flag = Quartz.kCGEventFlagMaskCommand
        events = [
            Quartz.CGEventCreateKeyboardEvent(source, 55, True),
            Quartz.CGEventCreateKeyboardEvent(source, 9, True),
            Quartz.CGEventCreateKeyboardEvent(source, 9, False),
            Quartz.CGEventCreateKeyboardEvent(source, 55, False),
        ]
        Quartz.CGEventSetFlags(events[1], command_flag)
        Quartz.CGEventSetFlags(events[2], command_flag)
        for event in events:
            Quartz.CGEventPost(Quartz.kCGAnnotatedSessionEventTap, event)

    def _schedule_restore(self, generation, expected_change_count):
        def restore():
            time.sleep(self._restore_delay)
            with self._clipboard_lock:
                if generation != self._clipboard_generation:
                    return

                snapshot = self._saved_clipboard
                self._saved_clipboard = None
                if snapshot is None:
                    return
                if self._clipboard_was_replaced(expected_change_count):
                    return
                try:
                    self._restore_clipboard(snapshot)
                except Exception as error:
                    print(f"[core_output] Clipboard restore failed: {error}", flush=True)

        threading.Thread(target=restore, daemon=True).start()

    def _restore_after_failure(self, generation, expected_change_count=None):
        with self._clipboard_lock:
            if generation != self._clipboard_generation:
                return
            snapshot = self._saved_clipboard
            self._saved_clipboard = None
            if snapshot is not None and not self._clipboard_was_replaced(expected_change_count):
                self._restore_clipboard(snapshot)

    def inject(self, text: str, dispatch=None) -> bool:
        """Inject text at the current cursor position using the clipboard."""
        if not text:
            return False

        print("[core_output] Injecting formatted payload...", flush=True)
        generation = None
        expected_change_count = None
        try:
            with self._clipboard_lock:
                if self._saved_clipboard is None:
                    self._saved_clipboard = self._snapshot_clipboard()
                self._clipboard_generation += 1
                generation = self._clipboard_generation
                expected_change_count = self._set_clipboard_text(text)

            # NSPasteboard writes are synchronous; this tiny pause is enough for
            # target apps to observe its change count before the native key event.
            time.sleep(0.015)

            def send_if_current():
                with self._clipboard_lock:
                    if generation != self._clipboard_generation or self._clipboard_was_replaced(expected_change_count):
                        raise RuntimeError('Clipboard changed before paste')
                    self._send_paste_shortcut()

            if dispatch is None:
                send_if_current()
            elif not dispatch(send_if_current):
                self._restore_after_failure(generation, expected_change_count)
                return False
            self._schedule_restore(generation, expected_change_count)
            print("[core_output] Injection successful.", flush=True)
            return True
        except Exception as error:
            print(f"[core_output] Clipboard injection failed: {error}", flush=True)
            if generation is not None:
                try:
                    self._restore_after_failure(generation, expected_change_count)
                except Exception:
                    pass
            # A failed paste must not turn into uncontrolled typing, especially
            # for Unicode, multiline prompts or a newly focused application.
            return False


if __name__ == "__main__":
    injector = OutputInjector()
    print("Testing output injection. Focus a text field within 3 seconds...")
    time.sleep(3)
    injector.inject("This is a test injection.")
