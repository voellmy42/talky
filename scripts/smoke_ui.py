"""Render native UI and check menu states without recording, models or paste.

Run with the project's Python on a logged-in Mac desktop.
"""
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import AppKit
from Foundation import NSDate, NSRunLoop
from app import TalkyApp, SetupWizard
from tools.ui_preview import VisualPreview, STATES
from tools.core_config import ConfigManager


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
    wizard = SetupWizard(lambda: None, on_preview=talky._show_preview)
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
        saved_config = talky._config
        with tempfile.TemporaryDirectory(dir='build') as root:
            talky._config = ConfigManager(str(Path(root) / 'config.json'))
            talky._set_appearance('fun')
            assert talky.overlay._style == 'fun'
            assert not talky.overlay._visible
            assert ConfigManager(talky._config._path).get_appearance() == 'fun'
            assert bool(talky.status_bar._appearance_items['fun'].state())
            talky._set_appearance('standard')
        talky._config = saved_config
        for name, text in (('dictating', 'Dictating · EN — Esc to cancel'),
                            ('editing', 'Editing selection · DE — Esc to cancel'),
                            ('applying', 'Applying your edit… Esc to cancel')):
            talky.overlay.update_text(text)
            render(talky.overlay._window.contentView(), output / (name + '.png'))
        talky.overlay.update_text('Text ready — Copy Last Result')
        render(talky.overlay._window.contentView(), output / 'recovery.png')
        # Test real native animation/lifecycle with synthetic levels, not hardware.
        wizard._show_preview()
        preview = talky._preview
        talky._show_preview()
        assert talky._preview is preview  # Onboarding and menu share one companion.
        preview.overlay.level_source = lambda: .8
        key_window = AppKit.NSApplication.sharedApplication().keyWindow()
        original_preferences = dict(talky._config._data)
        for style in ('standard', 'fun'):
            preview.set_style(style)
            for index, (name, _) in enumerate(STATES):
                preview.select(index)
                NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(.2))
                assert AppKit.NSApplication.sharedApplication().keyWindow() == key_window
                assert not preview.overlay._window.canBecomeKeyWindow()
                assert preview.overlay._window.ignoresMouseEvents()
                bars = preview.overlay._fun.bars if style == 'fun' else preview.overlay._bars
                for bar in bars:
                    frame = bar.frame()
                    assert 0 <= frame.origin.x and frame.origin.x + frame.size.width <= preview.overlay.WIDTH
                    assert (84 <= frame.origin.y and frame.origin.y + frame.size.height <= 100) if style == 'fun' else (
                        0 <= frame.origin.y and frame.origin.y + frame.size.height <= 32)
                render(preview.overlay._window.contentView(), output / (style + '-' + str(index) + '.png'))
            if style == 'fun':
                preview.select(4)
                NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(.9))
                assert preview.overlay._timer is None  # Celebration is finite.
                preview.overlay._motion_override = True
                preview.select(0)
                assert preview.overlay._timer is None
                assert all(bar.frame().size.height == 2 for bar in preview.overlay._fun.bars)
                render(preview.overlay._window.contentView(), output / 'fun-reduced-motion.png')
                preview.overlay._motion_override = False
        assert talky._config._data == original_preferences  # Preview never saves a style.
        for style in ('standard', 'fun', 'standard'):
            preview.set_style(style)
            assert preview.overlay._style == style
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
        preview.close()
        preview.set_style('fun')
        assert not preview.overlay._visible  # Changing a hidden style cannot summon the pet.
        assert preview.overlay._timer is None
        assert not preview.overlay._window.isVisible()
        preview.show()
        assert preview.overlay._visible
        preview.close()
        print('Native UI checks passed; previews:', output)
    finally:
        if preview:
            preview.close()
        wizard.close()
        talky.overlay.close()
        AppKit.NSStatusBar.systemStatusBar().removeStatusItem_(talky.status_bar._status_item)


if __name__ == '__main__':
    main()
