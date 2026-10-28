"""A bounded, nonactivating HUD. Only the main thread mutates its layers."""
import math
import time

import AppKit
import Quartz
import objc
from Foundation import NSOperationQueue


def presentation(text):
    """Keep full explanatory messages available below concise activity labels."""
    text = text.strip()
    language = next((code for code in ('EN', 'DE') if f'· {code}' in text), '')
    if text.startswith('Editing selection'):
        return 'Editing selection', 'Speak the change you want', language, 'editing', 'text.cursor'
    if text.startswith('Dictating') or 'Listening' in text:
        return 'Listening', 'Speak naturally', language, 'listening', 'mic.fill'
    for words, title in ((('Warming', 'Loading'), 'Getting ready'),
                         (('Transcribing', 'Understanding'), 'Transcribing'),
                         (('Applying',), 'Applying edit'),
                         (('Checking destination',), 'Checking destination'),
                         (('Processing', 'Summarizing'), 'Processing')):
        if any(word in text for word in words):
            return title, text, language, 'processing', 'ellipsis'
    if 'Meeting' in text:
        return text, 'Meeting recording', '', 'meeting', 'record.circle'
    if 'Text ready' in text or text.startswith('Selection changed'):
        return 'Text ready', 'Copy Last Result from the Talky menu', '', 'notice', 'info.circle'
    if text in ('Ready', 'Text inserted', 'Result copied', 'Original text copied', 'Last result cleared') or text.startswith(('Dictation complete', 'Edit complete')):
        title = text.split(' — ')[0]
        return title, text if ' — ' in text else 'On-device · Private by design', '', 'success', 'checkmark'
    title = 'Cancelled' if text.startswith('Cancelled') else 'Notice'
    return title, text, '', 'notice', 'info.circle'


def wave_heights(level, phase, processing=False):
    """Small fixed envelope; audio amplitude never changes layout or window size."""
    level = min(1.0, max(0.0, level))
    return [3 + (15 if processing else 22 * level) *
            (0.38 + 0.62 * math.sin(math.pi * (i + 1) / 12)) *
            (0.5 + 0.5 * math.sin(phase * (2.4 if processing else 4) - i * .65))
            for i in range(11)]


class _Panel(AppKit.NSPanel):
    def canBecomeKeyWindow(self):
        return False

    def canBecomeMainWindow(self):
        return False


class OverlayWindow:
    WIDTH, HEIGHT = 344, 60

    def __init__(self, style='standard'):
        width, height = self.WIDTH, self.HEIGHT
        self._window = _Panel.alloc().initWithContentRect_styleMask_backing_defer_(
            AppKit.NSMakeRect(0, 0, width, height),
            AppKit.NSWindowStyleMaskBorderless | AppKit.NSWindowStyleMaskNonactivatingPanel,
            AppKit.NSBackingStoreBuffered, False)
        self._window.setLevel_(AppKit.NSStatusWindowLevel + 1)
        self._window.setOpaque_(False)
        self._window.setBackgroundColor_(AppKit.NSColor.clearColor())
        self._window.setIgnoresMouseEvents_(True)
        self._window.setHasShadow_(True)
        self._window.setHidesOnDeactivate_(False)
        self._window.setCollectionBehavior_(AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces |
                                            AppKit.NSWindowCollectionBehaviorStationary |
                                            AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary)
        content = AppKit.NSView.alloc().initWithFrame_(AppKit.NSMakeRect(0, 0, width, height))
        self._window.setContentView_(content)
        content.setWantsLayer_(True)
        self._bg = AppKit.NSVisualEffectView.alloc().initWithFrame_(content.bounds())
        self._bg.setMaterial_(AppKit.NSVisualEffectMaterialHUDWindow)
        self._bg.setBlendingMode_(AppKit.NSVisualEffectBlendingModeBehindWindow)
        self._bg.setState_(AppKit.NSVisualEffectStateActive)
        self._bg.setAppearance_(AppKit.NSAppearance.appearanceNamed_(AppKit.NSAppearanceNameDarkAqua))
        self._bg.setWantsLayer_(True)
        self._bg.layer().setCornerRadius_(22)
        self._bg.layer().setMasksToBounds_(True)
        self._bg.layer().setBorderWidth_(.5)
        self._bg.layer().setBorderColor_(AppKit.NSColor.colorWithWhite_alpha_(1, .18).CGColor())
        content.addSubview_(self._bg)
        self._icon = AppKit.NSImageView.alloc().initWithFrame_(AppKit.NSMakeRect(16, 36, 12, 12))
        content.addSubview_(self._icon)
        self._label = self._text(content, (36, 32, 221, 20), 13, True)
        self._detail = self._text(content, (16, 11, 267, 17), 10, False)
        self._badge = self._text(content, (262, 34, 66, 17), 9, True)
        self._badge.setAlignment_(AppKit.NSTextAlignmentRight)
        self._bars = []
        for i in range(11):
            bar = Quartz.CALayer.layer()
            bar.setCornerRadius_(1.5)
            self._bg.layer().addSublayer_(bar)
            self._bars.append(bar)
        self._mode = 'success'
        self._motion_override = False
        self._timer = self._hide_timer = self._meeting_timer = None
        self._visible = False
        self._level = 0.0
        self._last_text = None
        self._last_tick = time.monotonic()
        self._state_started = self._last_tick
        self._style = 'standard'
        self._fun = None
        self.level_source = lambda: 0.0
        self._display_observer = None
        self._observe_display()
        self._position()
        self.update_text('Ready')
        self.set_style(style)

    def set_style(self, style):
        if style not in ('standard', 'fun'):
            raise ValueError('Unknown appearance')
        self._style = style
        if style == 'fun' and self._fun is None:
            from tools.ui_fun import FunCharacter
            self._fun = FunCharacter(self._window.contentView())
        self.WIDTH, self.HEIGHT = (260, 200) if style == 'fun' else (344, 60)
        self._window.setContentSize_(AppKit.NSMakeSize(self.WIDTH, self.HEIGHT))
        for view in (self._bg, self._icon, self._label, self._detail, self._badge):
            view.setHidden_(style == 'fun')
        if self._fun:
            self._fun.view.setHidden_(style != 'fun')
        self.update_text(self._last_text or 'Ready')
        if self._visible:
            self._position()

    def _observe_display(self):
        if self._display_observer is None:
            self._display_observer = AppKit.NSWorkspace.sharedWorkspace().notificationCenter().addObserverForName_object_queue_usingBlock_(
                AppKit.NSWorkspaceAccessibilityDisplayOptionsDidChangeNotification, None,
                NSOperationQueue.mainQueue(), lambda notification: self._display_options_changed())

    def _display_options_changed(self):
        self._refresh_material()
        self._tick(None)
        self._sync_timer()

    @staticmethod
    def _text(parent, rect, size, bold):
        label = AppKit.NSTextField.labelWithString_('')
        label.setFrame_(AppKit.NSMakeRect(*rect))
        label.setFont_(AppKit.NSFont.systemFontOfSize_weight_(size,
                        AppKit.NSFontWeightMedium if bold else AppKit.NSFontWeightRegular))
        label.setTextColor_(AppKit.NSColor.colorWithWhite_alpha_(1, .94 if bold else .66))
        label.setLineBreakMode_(AppKit.NSLineBreakByTruncatingTail)
        label.setWantsLayer_(True)
        parent.addSubview_(label)
        return label

    def _position(self):
        # Follow the screen containing the pointer when a new interaction begins.
        point = AppKit.NSEvent.mouseLocation()
        screen = next((s for s in AppKit.NSScreen.screens()
                       if AppKit.NSPointInRect(point, s.frame())), AppKit.NSScreen.mainScreen())
        rect = screen.visibleFrame()
        self._window.setFrameOrigin_(AppKit.NSMakePoint(
            rect.origin.x + (rect.size.width - self.WIDTH) / 2, rect.origin.y + 16))

    def _reduced(self):
        return self._motion_override or AppKit.NSWorkspace.sharedWorkspace().accessibilityDisplayShouldReduceMotion()

    def _refresh_material(self):
        solid = AppKit.NSWorkspace.sharedWorkspace().accessibilityDisplayShouldReduceTransparency()
        self._bg.layer().setBackgroundColor_(AppKit.NSColor.colorWithWhite_alpha_(.09, 1 if solid else .72).CGColor())

    def update_text(self, text):
        title, detail, language, self._mode, symbol = presentation(text)
        if text != self._last_text:
            self._state_started = time.monotonic()
        if text != self._last_text and self._visible and not self._reduced():
            for label in (self._label, self._detail):
                transition = Quartz.CATransition.animation()
                transition.setType_('fade')
                transition.setDuration_(.16)
                label.layer().addAnimation_forKey_(transition, 'text-fade')
        self._last_text = text
        self._label.setStringValue_(title)
        self._detail.setStringValue_(detail)
        status_only = self._mode in ('notice', 'success')
        self._detail.setFrame_(AppKit.NSMakeRect(16, 6 if status_only else 11,
                                                312 if status_only else 267, 27 if status_only else 17))
        self._detail.setMaximumNumberOfLines_(2 if status_only else 1)
        self._detail.cell().setWraps_(status_only)
        self._detail.cell().setScrollable_(False)
        for bar in self._bars:
            bar.setHidden_(status_only)
        self._detail.setToolTip_(text)
        self._window.contentView().setAccessibilityLabel_(text)
        self._badge.setStringValue_(' · '.join(filter(None, (language, 'esc' if self._mode in ('listening', 'editing', 'processing') else ''))))
        self._icon.setImage_(AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(symbol, title))
        self._color = {'editing': AppKit.NSColor.systemPurpleColor(),
                       'listening': AppKit.NSColor.systemTealColor(),
                       'processing': AppKit.NSColor.systemBlueColor(),
                       'meeting': AppKit.NSColor.systemRedColor(),
                       'notice': AppKit.NSColor.systemOrangeColor(),
                       'success': AppKit.NSColor.systemGreenColor()}[self._mode]
        self._icon.setContentTintColor_(self._color)
        if self._fun and self._style == 'fun':
            self._fun.update(title, self._mode, text, self._badge.stringValue())
        self._refresh_material()
        self._tick(None)
        self._sync_timer()

    def _sync_timer(self):
        animated = self._mode in ('listening', 'editing', 'processing')
        if self._style == 'fun':
            animated = animated or self._mode == 'meeting' or (
                self._mode == 'success' and time.monotonic() - self._state_started < .75)
        moving = self._visible and animated and not self._reduced()
        if moving and self._timer is None:
            self._timer = AppKit.NSTimer.timerWithTimeInterval_repeats_block_(1 / 30, True, self._tick)
            AppKit.NSRunLoop.mainRunLoop().addTimer_forMode_(self._timer, AppKit.NSRunLoopCommonModes)
        elif not moving and self._timer is not None:
            self._timer.invalidate()
            self._timer = None

    def _tick(self, timer):
        now = time.monotonic()
        dt = min(.1, max(0, now - self._last_tick))
        self._last_tick = now
        reduced = self._reduced()
        target = self.level_source() if self._mode in ('listening', 'editing') else 0
        target = min(1.0, max(0.0, float(target)))
        tau = .065 if target > self._level else .22
        self._level += (target - self._level) * (1 - math.exp(-dt / tau))
        heights = wave_heights(0 if reduced else self._level, now,
                               self._mode == 'processing' and not reduced)
        Quartz.CATransaction.begin()
        Quartz.CATransaction.setDisableActions_(True)
        for i, (bar, height) in enumerate(zip(self._bars, heights)):
            bar.setBackgroundColor_(self._color.CGColor())
            bar.setOpacity_(.8)
            bar.setFrame_(AppKit.NSMakeRect(286 + i * 3.8, 19 - height / 2, 2.3, height))
        if self._fun and self._style == 'fun':
            self._fun.tick(self._mode, heights, now, reduced, now - self._state_started)
        Quartz.CATransaction.commit()
        self._sync_timer()

    def show(self, text='Listening…'):
        self._observe_display()
        if self._hide_timer:
            self._hide_timer.invalidate()
            self._hide_timer = None
        opening = not self._visible
        self._visible = True
        self.update_text(text)
        if opening:
            self._position()
            self._window.setAlphaValue_(0 if not self._reduced() else 1)
            self._window.orderFrontRegardless()
        self._fade(1)

    def _fade(self, alpha):
        AppKit.NSAnimationContext.beginGrouping()
        AppKit.NSAnimationContext.currentContext().setDuration_(0 if self._reduced() else .18)
        self._window.animator().setAlphaValue_(alpha)
        AppKit.NSAnimationContext.endGrouping()

    def hide(self):
        self._visible = False
        self._level = 0
        self._sync_timer()
        if self._hide_timer:
            self._hide_timer.invalidate()
        self._fade(0)
        def finish(timer):
            self._window.orderOut_(None)
            self._hide_timer = None
        self._hide_timer = AppKit.NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
            .01 if self._reduced() else .2, False, finish)

    def set_dictation_style(self):
        pass  # State, rather than callers, owns the appearance.

    def set_meeting_style(self):
        pass

    def start_meeting_timer(self, get_elapsed):
        self.stop_meeting_timer()
        def tick(timer):
            seconds = int(get_elapsed())
            minutes, seconds = divmod(seconds, 60)
            self.show(f'Meeting · {minutes:02d}:{seconds:02d}')
        tick(None)
        self._meeting_timer = AppKit.NSTimer.scheduledTimerWithTimeInterval_repeats_block_(1, True, tick)

    def stop_meeting_timer(self):
        if self._meeting_timer:
            self._meeting_timer.invalidate()
            self._meeting_timer = None

    def close(self):
        self.hide()
        self.stop_meeting_timer()
        if self._hide_timer:
            self._hide_timer.invalidate()
            self._hide_timer = None
        self._window.orderOut_(None)
        if self._display_observer:
            AppKit.NSWorkspace.sharedWorkspace().notificationCenter().removeObserver_(self._display_observer)
            self._display_observer = None
