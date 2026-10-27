"""Render native UI and check menu states without recording, models or paste.

Run with the project's Python on a logged-in Mac desktop.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import AppKit
from Foundation import NSDate, NSRunLoop
from app import TalkyApp, SetupWizard


def render(view, path):
    view.displayIfNeeded()
    bitmap = view.bitmapImageRepForCachingDisplayInRect_(view.bounds())
    view.cacheDisplayInRect_toBitmapImageRep_(view.bounds(), bitmap)
    data = bitmap.representationUsingType_properties_(AppKit.NSBitmapImageFileTypePNG, {})
    assert data.writeToFile_atomically_(str(path), True)


def main():
    output = Path(__file__).resolve().parents[1] / 'build' / 'ui-preview'
    output.mkdir(parents=True, exist_ok=True)
    talky = TalkyApp(lambda *args: None)
    wizard = SetupWizard(lambda: None)
    try:
        render(wizard._window.contentView(), output / 'welcome.png')
        wizard._build_checklist_page()
        NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(.3))
        render(wizard._window.contentView(), output / 'permissions.png')
        for state, has_result in (('recording', False), ('transcribing', True),
                                  ('cancelling', False), ('ready', True)):
            talky.status_bar.set_session_status(state, state, has_result)
            items = talky.status_bar._dictation_items
            assert bool(items['copyDictation:'].isEnabled()) == has_result
            assert bool(items['cancelDictation:'].isEnabled()) == (state in ('recording', 'transcribing'))
        for choice in talky.status_bar._shortcut_items:
            talky.status_bar._toggle_shortcut = choice
            talky.status_bar._update_shortcut_checks()
            assert talky.status_bar.get_toggle_shortcut() == choice
            for code, item in talky.status_bar._shortcut_items.items():
                assert bool(item.state()) == (code == choice)
        talky.overlay.update_text('Text ready — Copy Last Dictation')
        render(talky.overlay._window.contentView(), output / 'recovery.png')
        print('Native UI checks passed; previews:', output)
    finally:
        wizard.close()
        talky.overlay._window.orderOut_(None)
        AppKit.NSStatusBar.systemStatusBar().removeStatusItem_(talky.status_bar._status_item)


if __name__ == '__main__':
    main()
