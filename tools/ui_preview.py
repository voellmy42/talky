"""Permission-free visual preview. No pipeline, audio hardware or text delivery."""
import math
import time

import AppKit
import objc

from tools.ui_overlay import OverlayWindow


STATES = (
    ('Listening', 'Dictating · EN — Esc to cancel'),
    ('Voice editing', 'Editing selection · DE — Esc to cancel'),
    ('Transcribing', 'Transcribing…'),
    ('Applying edit', 'Applying your edit… Esc to cancel'),
    ('Complete', 'Text inserted'),
    ('Recovery', 'Text ready — Copy Last Result'),
    ('Meeting', 'Meeting · 02:34'),
    ('Cancelled', 'Cancelled'),
)


class _PreviewTarget(AppKit.NSObject):
    @objc.typedSelector(b'v@:@')
    def style_(self, sender):
        self.owner.set_style('fun' if sender.tag() else 'standard')

    @objc.typedSelector(b'v@:@')
    def choose_(self, sender):
        self.owner.select(sender.tag())

    @objc.typedSelector(b'v@:@')
    def motion_(self, sender):
        self.owner.overlay._motion_override = bool(sender.state())
        self.owner.select(self.owner.index)

    @objc.typedSelector(b'v@:@')
    def replay_(self, sender):
        self.owner.play()

    def windowWillClose_(self, notification):
        self.owner.close()


class VisualPreview:
    def __init__(self, on_close=None, style='standard'):
        self.overlay = OverlayWindow(style=style)
        self.overlay.level_source = self._sample
        self._on_close = on_close
        self._timer = None
        self.index = 0
        self._start = time.monotonic()
        self._target = _PreviewTarget.alloc().init()
        self._target.owner = self
        self.window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            AppKit.NSMakeRect(0, 0, 460, 470),
            AppKit.NSWindowStyleMaskTitled | AppKit.NSWindowStyleMaskClosable,
            AppKit.NSBackingStoreBuffered, False)
        self.window.setTitle_('Talky · Appearance Preview')
        self.window.setLevel_(AppKit.NSFloatingWindowLevel)
        self.window.setReleasedWhenClosed_(False)
        self.window.setDelegate_(self._target)
        self.window.center()
        view = self.window.contentView()
        self._label(view, 'Small presence. Big personality.', (28, 406, 404, 30), 21, True)
        self._label(view, 'APPEARANCE PREVIEW', (28, 439, 404, 15), 10, True)
        self._label(view, 'Simulated audio · Microphone stays off\nCompare styles without changing your saved appearance.',
                    (28, 353, 404, 43), 12)
        self.style_buttons = []
        for i, title in enumerate(('Standard', 'Fun · Walkie-talkie')):
            button = AppKit.NSButton.buttonWithTitle_target_action_(title, self._target, 'style:')
            button.setTag_(i)
            button.setFrame_(AppKit.NSMakeRect(24 + i * 208, 302, 204, 34))
            view.addSubview_(button)
            self.style_buttons.append(button)
        self._update_style_buttons()
        self.buttons = []
        for i, (title, _) in enumerate(STATES):
            column, row = i % 2, i // 2
            button = AppKit.NSButton.buttonWithTitle_target_action_(title, self._target, 'choose:')
            button.setFrame_(AppKit.NSMakeRect(24 + column * 208, 249 - row * 42, 204, 34))
            button.setTag_(i)
            view.addSubview_(button)
            self.buttons.append(button)
        motion = AppKit.NSButton.checkboxWithTitle_target_action_(
            'Preview with reduced motion', self._target, 'motion:')
        motion.setFrame_(AppKit.NSMakeRect(28, 64, 404, 25))
        view.addSubview_(motion)
        replay = AppKit.NSButton.buttonWithTitle_target_action_('Play all states', self._target, 'replay:')
        replay.setFrame_(AppKit.NSMakeRect(270, 20, 162, 32))
        view.addSubview_(replay)
        self._caption = self._label(view, '', (28, 24, 235, 23), 11)

    def _update_style_buttons(self):
        for i, button in enumerate(self.style_buttons):
            selected = ('standard', 'fun')[i] == self.overlay._style
            button.setState_(AppKit.NSControlStateValueOn if selected else AppKit.NSControlStateValueOff)
            button.setBezelColor_(AppKit.NSColor.controlAccentColor() if selected else None)

    def set_style(self, style):
        self.overlay.set_style(style)
        self._update_style_buttons()
        if self.window.isVisible():
            self._display(self.index)

    @staticmethod
    def _label(view, text, rect, size, bold=False):
        label = AppKit.NSTextField.wrappingLabelWithString_(text)
        label.setFrame_(AppKit.NSMakeRect(*rect))
        label.setFont_(AppKit.NSFont.systemFontOfSize_weight_(size,
                      AppKit.NSFontWeightSemibold if bold else AppKit.NSFontWeightRegular))
        if not bold:
            label.setTextColor_(AppKit.NSColor.secondaryLabelColor())
        view.addSubview_(label)
        return label

    def _sample(self):
        elapsed = time.monotonic() - self._start
        # A reproducible phrase envelope with pauses; explicitly simulated.
        envelope = max(0, math.sin(elapsed * 1.3)) ** .6
        return envelope * (.4 + .38 * (1 + math.sin(elapsed * 5)) / 2)

    def _display(self, index):
        self.index = index
        self.overlay.show(STATES[index][1])
        if self.overlay._mode in ('listening', 'editing'):
            self.overlay._detail.setStringValue_('Simulated audio · Microphone off')
        self._caption.setStringValue_(STATES[index][0] + ' · Preview')
        for i, button in enumerate(self.buttons):
            button.setState_(AppKit.NSControlStateValueOn if i == index else AppKit.NSControlStateValueOff)

    def select(self, index):
        self._stop()
        self._display(index)

    def play(self):
        self._stop()
        self._display(0)
        def advance(timer):
            if self.index == len(STATES) - 1:
                self._stop()
            else:
                self._display(self.index + 1)
        self._timer = AppKit.NSTimer.scheduledTimerWithTimeInterval_repeats_block_(2.8, True, advance)

    def _stop(self):
        if self._timer:
            self._timer.invalidate()
            self._timer = None

    def show(self):
        self.window.makeKeyAndOrderFront_(None)
        AppKit.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        self.select(self.index)

    def close(self):
        self._stop()
        self.overlay.close()
        self.window.orderOut_(None)
        if self._on_close:
            self._on_close()


def run_preview():
    app = AppKit.NSApplication.sharedApplication()
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
    preview = VisualPreview(on_close=lambda: app.terminate_(None))
    preview.show()
    app.run()


if __name__ == '__main__':
    run_preview()
