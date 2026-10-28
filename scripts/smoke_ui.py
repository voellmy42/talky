"""Render native UI and check menu states without recording, models or paste.

Run with the project's Python on a logged-in Mac desktop.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import AppKit
from Foundation import NSDate, NSRunLoop
from app import TalkyApp, SetupWizard
from tools.ui_preview import VisualPreview, STATES


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
    preview = None
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
        for state in ('not_installed', 'downloading', 'loading', 'ready', 'failed', 'unloaded'):
            talky.status_bar.set_ai_status(state, state)
            assert bool(talky.status_bar._ai_install_item.isEnabled()) == (state not in ('downloading', 'loading', 'ready'))
            assert bool(talky.status_bar._ai_cancel_item.isEnabled()) == (state == 'downloading')
        assert talky.status_bar.get_formatting_mode() == 'fast'
        menu = talky.status_bar._status_item.menu()
        assert not any('Polished' in item.title() for item in menu.itemArray())
        for name, text in (('dictating', 'Dictating · EN — Esc to cancel'),
                            ('editing', 'Editing selection · DE — Esc to cancel'),
                            ('applying', 'Applying your edit… Esc to cancel')):
            talky.overlay.update_text(text)
            render(talky.overlay._window.contentView(), output / (name + '.png'))
        talky.overlay.update_text('Text ready — Copy Last Result')
        render(talky.overlay._window.contentView(), output / 'recovery.png')
        # Test real native animation/lifecycle with synthetic levels, not hardware.
        preview = VisualPreview()
        preview.show()
        key_window = AppKit.NSApplication.sharedApplication().keyWindow()
        for index, (name, _) in enumerate(STATES):
            preview.select(index)
            NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(.2))
            assert AppKit.NSApplication.sharedApplication().keyWindow() == key_window
            assert not preview.overlay._window.canBecomeKeyWindow()
            assert preview.overlay._window.ignoresMouseEvents()
            for bar in preview.overlay._bars:
                frame = bar.frame()
                assert 0 <= frame.origin.x and frame.origin.x + frame.size.width <= preview.overlay.WIDTH
                assert 0 <= frame.origin.y and frame.origin.y + frame.size.height <= 32
            render(preview.overlay._window.contentView(), output / ('preview-' + str(index) + '.png'))
        preview.select(0)
        preview.overlay.level_source = lambda: .8
        NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(.3))
        assert preview.overlay._level > .5
        first = [bar.frame().size.height for bar in preview.overlay._bars]
        NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(.2))
        assert first != [bar.frame().size.height for bar in preview.overlay._bars]
        render(preview.overlay._window.contentView(), output / 'waveform-active.png')
        render(preview.window.contentView(), output / 'appearance-preview.png')
        preview.overlay._motion_override = True
        preview.select(0)
        assert preview.overlay._timer is None
        assert all(bar.frame().size.height == 3 for bar in preview.overlay._bars)
        preview.overlay._motion_override = False
        preview.select(2)
        assert preview.overlay._timer is not None
        preview.overlay.hide()
        assert preview.overlay._timer is None
        preview.overlay.show('Transcribing…')
        NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(.3))
        assert preview.overlay._window.isVisible()  # A stale hide must not remove it.
        print('Native UI checks passed; previews:', output)
    finally:
        if preview:
            preview.close()
        wizard.close()
        talky.overlay.close()
        AppKit.NSStatusBar.systemStatusBar().removeStatusItem_(talky.status_bar._status_item)


if __name__ == '__main__':
    main()
