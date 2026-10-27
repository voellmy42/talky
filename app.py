import objc
import AppKit
import ApplicationServices
import subprocess
import threading
import Quartz
import AVFoundation

from tools.core_config import ConfigManager


# ---------------------------------------------------------------------------
# Main-thread dispatcher
# ---------------------------------------------------------------------------

class _Dispatcher(AppKit.NSObject):
    """Dispatches callables to the main thread via performSelectorOnMainThread."""

    _blocks = {}
    _counter = 0
    _lock = threading.Lock()

    def doBlock_(self, key):
        with _Dispatcher._lock:
            fn = _Dispatcher._blocks.pop(key, None)
        if fn:
            fn()

    @classmethod
    def dispatch_to_main(cls, fn):
        with cls._lock:
            key = f"block_{cls._counter}"
            cls._counter += 1
            cls._blocks[key] = fn
        inst = cls.alloc().init()
        inst.performSelectorOnMainThread_withObject_waitUntilDone_(
            "doBlock:", key, False
        )


# ---------------------------------------------------------------------------
# Rounded background view
# ---------------------------------------------------------------------------

class _RoundedBackgroundView(AppKit.NSVisualEffectView):
    """Modern background with glassmorphism and tinting."""

    def initWithFrame_(self, frame):
        self = objc.super(_RoundedBackgroundView, self).initWithFrame_(frame)
        if self:
            self.setWantsLayer_(True)
            self.setMaterial_(AppKit.NSVisualEffectMaterialHUDWindow)
            self.setBlendingMode_(AppKit.NSVisualEffectBlendingModeBehindWindow)
            self.setState_(AppKit.NSVisualEffectStateActive)
            self.layer().setCornerRadius_(frame.size.height / 2)
            self.layer().setMasksToBounds_(True)
            self.layer().setBorderWidth_(0.5)
            self.layer().setBorderColor_(
                AppKit.NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.2).CGColor()
            )

            # Tint layer for different modes (e.g., meeting mode blue tint)
            self._tint_layer = Quartz.CALayer.layer()
            self._tint_layer.setFrame_(self.bounds())
            self._tint_layer.setOpacity_(0.0)
            self.layer().addSublayer_(self._tint_layer)
        return self

    def setTint_withAlpha_(self, color, alpha):
        self._tint_layer.setBackgroundColor_(color.CGColor())
        self._tint_layer.setOpacity_(alpha)

    def drawRect_(self, rect):
        # Visual effect view handles its own drawing
        pass


# ---------------------------------------------------------------------------
# Overlay window
# ---------------------------------------------------------------------------

class OverlayWindow:
    """Modern floating pill showing recording, warming up, or meeting state."""

    def __init__(self):
        width, height = 360, 48
        screen = AppKit.NSScreen.mainScreen().frame()
        # Position on the visible screen, above the Dock.
        screen = AppKit.NSScreen.mainScreen().visibleFrame()
        x = (screen.size.width - width) / 2
        x += screen.origin.x
        y = screen.origin.y + 32

        self._window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            AppKit.NSMakeRect(x, y, width, height),
            AppKit.NSWindowStyleMaskBorderless,
            AppKit.NSBackingStoreBuffered,
            False,
        )
        self._window.setLevel_(AppKit.NSStatusWindowLevel + 1)
        self._window.setOpaque_(False)
        self._window.setBackgroundColor_(AppKit.NSColor.clearColor())
        self._window.setIgnoresMouseEvents_(True)
        self._window.setHasShadow_(True)
        self._window.setCollectionBehavior_(
            AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
            | AppKit.NSWindowCollectionBehaviorStationary
        )

        content = AppKit.NSView.alloc().initWithFrame_(
            AppKit.NSMakeRect(0, 0, width, height)
        )
        self._window.setContentView_(content)

        # Background with glassmorphism
        self._bg = _RoundedBackgroundView.alloc().initWithFrame_(
            AppKit.NSMakeRect(0, 0, width, height)
        )
        content.addSubview_(self._bg)

        # Pulsing status indicator dot
        self._indicator = AppKit.NSView.alloc().initWithFrame_(
            AppKit.NSMakeRect(16, (height - 10) / 2, 10, 10)
        )
        self._indicator.setWantsLayer_(True)
        self._indicator.layer().setCornerRadius_(5)
        content.addSubview_(self._indicator)

        # Main label
        self._label = AppKit.NSTextField.labelWithString_("")
        # Adjust frame to be next to the indicator
        self._label.setFrame_(AppKit.NSMakeRect(36, (height - 24) / 2 - 1, width - 52, 24))
        self._label.setFont_(
            AppKit.NSFont.systemFontOfSize_weight_(15, AppKit.NSFontWeightSemibold)
        )
        self._label.setTextColor_(AppKit.NSColor.whiteColor())
        self._label.setAlignment_(AppKit.NSTextAlignmentLeft)
        self._label.setDrawsBackground_(False)
        self._label.setBezeled_(False)
        self._label.setEditable_(False)
        self._label.setSelectable_(False)
        content.addSubview_(self._label)

        self._meeting_timer = None
        self._hide_timer = None

    def show(self, text="Listening..."):
        if self._hide_timer is not None:
            self._hide_timer.invalidate()
            self._hide_timer = None
        self.update_text(text)
        self._window.setAlphaValue_(0.0)
        self._window.orderFrontRegardless()
        
        # Smooth fade-in
        AppKit.NSAnimationContext.beginGrouping()
        AppKit.NSAnimationContext.currentContext().setDuration_(0.2)
        self._window.animator().setAlphaValue_(1.0)
        AppKit.NSAnimationContext.endGrouping()

    def update_text(self, text):
        clean_text = text.strip()
        self._label.setStringValue_(clean_text)
        
        # Color & Animation logic based on status
        if "Listening" in clean_text:
            self._set_indicator_style(AppKit.NSColor.systemRedColor(), True)
        elif "Warming" in clean_text or "Summarizing" in clean_text or "Processing" in clean_text:
            self._set_indicator_style(AppKit.NSColor.systemOrangeColor(), True)
        elif "Meeting" in clean_text:
            self._set_indicator_style(AppKit.NSColor.systemBlueColor(), False)
        else:
            self._set_indicator_style(AppKit.NSColor.systemGreenColor(), False)

    def _set_indicator_style(self, color, pulse):
        self._indicator.layer().setBackgroundColor_(color.CGColor())
        self._indicator.layer().removeAnimationForKey_("pulse")
        if pulse:
            anim = Quartz.CABasicAnimation.animationWithKeyPath_("opacity")
            anim.setFromValue_(1.0)
            anim.setToValue_(0.3)
            anim.setDuration_(0.8)
            anim.setAutoreverses_(True)
            anim.setRepeatCount_(float('inf'))
            self._indicator.layer().addAnimation_forKey_(anim, "pulse")
        else:
            self._indicator.layer().setOpacity_(1.0)

    def hide(self):
        if self._hide_timer is not None:
            self._hide_timer.invalidate()
            self._hide_timer = None
        self._indicator.layer().removeAnimationForKey_("pulse")
        # Smooth fade-out before hiding
        AppKit.NSAnimationContext.beginGrouping()
        AppKit.NSAnimationContext.currentContext().setDuration_(0.2)
        self._window.animator().setAlphaValue_(0.0)
        AppKit.NSAnimationContext.endGrouping()
        
        # Schedule the actual window removal after animation
        def _hide_final(timer):
            self._window.orderOut_(None)
            self._hide_timer = None
        self._hide_timer = AppKit.NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
            0.2, False, _hide_final
        )

    def set_dictation_style(self):
        """Standard dark HUD pill."""
        self._bg.setTint_withAlpha_(AppKit.NSColor.blackColor(), 0.0)

    def set_meeting_style(self):
        """Blue-tinted pill for meeting mode."""
        self._bg.setTint_withAlpha_(AppKit.NSColor.systemBlueColor(), 0.2)

    def start_meeting_timer(self, get_elapsed):
        """Start a 1-second timer that updates the overlay with elapsed time."""
        self.set_meeting_style()

        def tick(timer):
            secs = int(get_elapsed())
            mins, s = divmod(secs, 60)
            hrs, m = divmod(mins, 60)
            time_str = f"{hrs}:{m:02d}:{s:02d}" if hrs > 0 else f"{m:02d}:{s:02d}"
            self._label.setStringValue_(f"Meeting — {time_str}")
            # Ensure indicator stays blue during meeting
            self._set_indicator_style(AppKit.NSColor.systemBlueColor(), False)

        self._window.setAlphaValue_(1.0)
        self._window.orderFrontRegardless()
        self._label.setStringValue_("Meeting — 00:00")
        self._meeting_timer = AppKit.NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
            1.0, True, tick
        )

    def stop_meeting_timer(self):
        """Stop the meeting timer and reset overlay style."""
        if self._meeting_timer is not None:
            self._meeting_timer.invalidate()
            self._meeting_timer = None
        self.set_dictation_style()


# ---------------------------------------------------------------------------
# Status bar controller
# ---------------------------------------------------------------------------

class _MenuTarget(AppKit.NSObject):
    """NSObject target for menu item actions."""

    _quit_fn = None
    _lang_fn = None
    _formatting_fn = None
    _meeting_fn = None
    _cancel_fn = None
    _copy_fn = None
    _copy_raw_fn = None
    _clear_fn = None
    _toggle_fn = None
    _shortcut_fn = None
    _ai_install_fn = None
    _ai_cancel_fn = None

    @objc.typedSelector(b"v@:@")
    def installAI_(self, sender):
        if self._ai_install_fn:
            self._ai_install_fn()

    @objc.typedSelector(b"v@:@")
    def cancelAI_(self, sender):
        if self._ai_cancel_fn:
            self._ai_cancel_fn()

    @objc.typedSelector(b"v@:@")
    def selectShortcut_(self, sender):
        if self._shortcut_fn:
            self._shortcut_fn(sender.representedObject())

    @objc.typedSelector(b"v@:@")
    def toggleDictation_(self, sender):
        if self._toggle_fn:
            self._toggle_fn()

    @objc.typedSelector(b"v@:@")
    def cancelDictation_(self, sender):
        if self._cancel_fn:
            self._cancel_fn()

    @objc.typedSelector(b"v@:@")
    def copyDictation_(self, sender):
        if self._copy_fn:
            self._copy_fn()

    @objc.typedSelector(b"v@:@")
    def copyOriginal_(self, sender):
        if self._copy_raw_fn:
            self._copy_raw_fn()

    @objc.typedSelector(b"v@:@")
    def clearDictation_(self, sender):
        if self._clear_fn:
            self._clear_fn()

    @objc.typedSelector(b"v@:@")
    def quitApp_(self, sender):
        if self._quit_fn:
            self._quit_fn()

    @objc.typedSelector(b"v@:@")
    def selectLang_(self, sender):
        if self._lang_fn:
            self._lang_fn(sender.representedObject())

    @objc.typedSelector(b"v@:@")
    def selectFormatting_(self, sender):
        if self._formatting_fn:
            self._formatting_fn(sender.representedObject())

    @objc.typedSelector(b"v@:@")
    def toggleMeeting_(self, sender):
        if self._meeting_fn:
            self._meeting_fn()


class StatusBarController:
    """Menu bar icon and dropdown."""

    LANGUAGES = [
        ("de", "Deutsch"),
        ("en", "English"),
    ]

    FORMATTING_MODES = [
        ("fast", "Fast (instant)"),
        ("polished", "Polished (local AI preview)"),
    ]

    def __init__(self, on_quit, config=None):
        self._on_quit = on_quit
        self._config = config or ConfigManager()
        self._language = self._config.get_language()
        self._formatting_mode = self._config.get_formatting_mode()
        self._toggle_shortcut = self._config.get_toggle_shortcut()
        self._session_message = None
        self.on_formatting_change = None
        self._menu_target = _MenuTarget.alloc().init()
        self._menu_target._quit_fn = on_quit
        self._menu_target._lang_fn = self._set_language
        self._menu_target._formatting_fn = self._set_formatting_mode
        self._menu_target._shortcut_fn = self._set_toggle_shortcut

        self._status_item = AppKit.NSStatusBar.systemStatusBar().statusItemWithLength_(
            AppKit.NSVariableStatusItemLength
        )

        # SF Symbol template images — render monochrome white in menu bar
        self._icon_idle = AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
            "mic", "Talky idle"
        )
        self._icon_idle.setTemplate_(True)

        self._icon_recording = AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
            "mic.fill", "Talky recording"
        )
        self._icon_recording.setTemplate_(True)

        self._icon_meeting = AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
            "record.circle", "Meeting in progress"
        )
        self._icon_meeting.setTemplate_(True)

        self._icon_warning = AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
            "exclamationmark.triangle", "Ollama missing"
        )
        self._icon_warning.setTemplate_(True)

        self._meeting_active = False
        self._is_recording = False
        self._ollama_offline = False
        self._setup_required = False

        button = self._status_item.button()
        button.setImage_(self._icon_idle)
        button.setTitle_("")

        self._build_menu()

    def _build_menu(self):
        menu = AppKit.NSMenu.alloc().init()

        self._status_menu_item = (
            AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "Status: Ready", None, ""
            )
        )
        self._status_menu_item.setEnabled_(False)
        menu.addItem_(self._status_menu_item)

        self._dictation_items = {}
        for title, action in (
            ('Start / Finish Dictation', 'toggleDictation:'),
            ('Cancel Dictation (Esc)', 'cancelDictation:'),
            ('Copy Last Dictation', 'copyDictation:'),
            ('Copy Original Transcript', 'copyOriginal:'),
            ('Clear Last Dictation', 'clearDictation:'),
        ):
            item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, '')
            item.setTarget_(self._menu_target)
            item.setEnabled_(False)
            self._dictation_items[action] = item
            menu.addItem_(item)
        menu.setAutoenablesItems_(False)

        self._shortcut_items = {}
        for code, title in (
            ('section', '§ — Start / Finish'),
            ('ctrl_shift_space', '⌃⇧Space — Start / Finish'),
            ('off', 'Fn only'),
        ):
            item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, 'selectShortcut:', '')
            item.setTarget_(self._menu_target)
            item.setRepresentedObject_(code)
            self._shortcut_items[code] = item
        shortcut_menu = AppKit.NSMenu.alloc().init()
        for item in self._shortcut_items.values():
            shortcut_menu.addItem_(item)
        shortcut_parent = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_('Dictation Shortcut', None, '')
        shortcut_parent.setSubmenu_(shortcut_menu)
        menu.addItem_(shortcut_parent)
        self._update_shortcut_checks()

        menu.addItem_(AppKit.NSMenuItem.separatorItem())

        # ---- Stats Dashboard ----
        stats_header = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Productivity Stats", None, ""
        )
        stats_header.setEnabled_(False)
        menu.addItem_(stats_header)

        self._stat_time_saved = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "  ⚡️ Time Saved: 0s", None, ""
        )
        self._stat_time_saved.setEnabled_(False)
        menu.addItem_(self._stat_time_saved)

        self._stat_dictations = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "  🎤 Dictations: 0", None, ""
        )
        self._stat_dictations.setEnabled_(False)
        menu.addItem_(self._stat_dictations)

        self._stat_speed = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "  🚀 Speed: 0 WPM", None, ""
        )
        self._stat_speed.setEnabled_(False)
        menu.addItem_(self._stat_speed)

        self._stat_latency = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "  Last response: --", None, ""
        )
        self._stat_latency.setEnabled_(False)
        menu.addItem_(self._stat_latency)

        menu.addItem_(AppKit.NSMenuItem.separatorItem())

        # ---- Meeting Mode ----
        self._meeting_menu_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Start Meeting", "toggleMeeting:", ""
        )
        self._meeting_menu_item.setTarget_(self._menu_target)
        menu.addItem_(self._meeting_menu_item)

        menu.addItem_(AppKit.NSMenuItem.separatorItem())

        # ---- Language selector ----
        lang_header = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Language", None, ""
        )
        lang_header.setEnabled_(False)
        menu.addItem_(lang_header)

        self._lang_items = {}
        for code, label in self.LANGUAGES:
            item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                f"  {label}", "selectLang:", ""
            )
            item.setTarget_(self._menu_target)
            item.setRepresentedObject_(code)
            self._lang_items[code] = item
            menu.addItem_(item)

        self._update_lang_checks()

        menu.addItem_(AppKit.NSMenuItem.separatorItem())

        # ---- Formatting mode ----
        formatting_header = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Formatting", None, ""
        )
        formatting_header.setEnabled_(False)
        menu.addItem_(formatting_header)

        self._formatting_items = {}
        for code, label in self.FORMATTING_MODES:
            item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                f"  {label}", "selectFormatting:", ""
            )
            item.setTarget_(self._menu_target)
            item.setRepresentedObject_(code)
            self._formatting_items[code] = item
            menu.addItem_(item)

        self._update_formatting_checks()

        self._ai_status_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            'AI: Not loaded (Fast needs no AI model)', None, '')
        self._ai_status_item.setEnabled_(False)
        menu.addItem_(self._ai_status_item)
        self._ai_install_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            'Download / Load AI Model…', 'installAI:', '')
        self._ai_install_item.setTarget_(self._menu_target)
        menu.addItem_(self._ai_install_item)
        self._ai_cancel_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            'Cancel AI Download', 'cancelAI:', '')
        self._ai_cancel_item.setTarget_(self._menu_target)
        self._ai_cancel_item.setEnabled_(False)
        menu.addItem_(self._ai_cancel_item)

        menu.addItem_(AppKit.NSMenuItem.separatorItem())

        quit_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Quit Talky", "quitApp:", "q"
        )
        quit_item.setTarget_(self._menu_target)
        menu.addItem_(quit_item)

        self._status_item.setMenu_(menu)

    def _update_lang_checks(self):
        for code, item in self._lang_items.items():
            if code == self._language:
                item.setState_(AppKit.NSControlStateValueOn)
            else:
                item.setState_(AppKit.NSControlStateValueOff)

    def _set_language(self, code):
        self._language = code
        self._config.set_language(code)
        self._update_lang_checks()
        print(f"[app] Language set to: {code}", flush=True)

    def get_language(self):
        return self._language

    def _update_formatting_checks(self):
        for code, item in self._formatting_items.items():
            state = (
                AppKit.NSControlStateValueOn
                if code == self._formatting_mode
                else AppKit.NSControlStateValueOff
            )
            item.setState_(state)

    def _set_formatting_mode(self, mode, notify=True):
        self._formatting_mode = mode
        self._config.set_formatting_mode(mode)
        self._update_formatting_checks()
        print(f"[app] Formatting mode set to: {mode}", flush=True)
        if notify and self.on_formatting_change:
            self.on_formatting_change(mode)

    def set_ai_status(self, state, message):
        self._ai_status_item.setTitle_('AI: ' + message)
        self._ai_install_item.setEnabled_(state not in ('downloading', 'loading', 'ready'))
        self._ai_cancel_item.setEnabled_(state == 'downloading')

    def get_formatting_mode(self):
        return self._formatting_mode

    def get_toggle_shortcut(self):
        return self._toggle_shortcut

    def _update_shortcut_checks(self):
        for code, item in self._shortcut_items.items():
            item.setState_(AppKit.NSControlStateValueOn if code == self._toggle_shortcut else AppKit.NSControlStateValueOff)

    def _set_toggle_shortcut(self, shortcut):
        self._config.set_toggle_shortcut(shortcut)
        self._toggle_shortcut = shortcut
        self._update_shortcut_checks()

    def update_stats(self, stats: dict):
        self._stat_time_saved.setTitle_(f"  ⚡️ Time Saved: {stats.get('time_saved', '0s')}")
        self._stat_dictations.setTitle_(f"  🎤 Dictations: {stats.get('dictations', '0')}")
        self._stat_speed.setTitle_(f"  🚀 Speed: {stats.get('speed_wpm', '0')} WPM")
        self._stat_latency.setTitle_(
            f"  Last response: {stats.get('last_latency', '--')}"
        )

    def set_recording(self, is_recording):
        self._is_recording = is_recording
        self._update_display()

    def set_session_status(self, state, message, has_result):
        self._session_message = message
        self._is_recording = state == 'recording'
        self._dictation_items['toggleDictation:'].setEnabled_(state in ('ready', 'recording'))
        self._dictation_items['cancelDictation:'].setEnabled_(state in ('recording', 'transcribing', 'formatting'))
        for action in ('copyDictation:', 'copyOriginal:', 'clearDictation:'):
            self._dictation_items[action].setEnabled_(has_result)
        self._meeting_menu_item.setEnabled_(state == 'ready')
        self._update_display()

    def set_meeting_active(self, active):
        self._meeting_active = active
        self._update_display()

    def set_ollama_offline(self, offline):
        self._ollama_offline = offline
        self._update_display()

    def set_setup_required(self, needed: bool):
        self._setup_required = needed
        self._update_display()

    def _update_display(self):
        button = self._status_item.button()
        if self._setup_required:
            button.setImage_(self._icon_warning)
            self._status_menu_item.setTitle_("Status: Setup Required")
        elif self._is_recording:
            button.setImage_(self._icon_recording)
            self._status_menu_item.setTitle_("Status: Recording...")
        elif self._meeting_active:
            button.setImage_(self._icon_meeting)
            self._status_menu_item.setTitle_("Status: Meeting in progress")
            self._meeting_menu_item.setTitle_("Stop Meeting")
        elif self._ollama_offline:
            button.setImage_(self._icon_warning)
            self._status_menu_item.setTitle_("Status: Ollama missing")
            self._meeting_menu_item.setTitle_("Start Meeting")
        else:
            button.setImage_(self._icon_idle)
            self._status_menu_item.setTitle_("Status: Ready")
            self._meeting_menu_item.setTitle_("Start Meeting")
        if self._session_message and not self._meeting_active and not self._setup_required:
            self._status_menu_item.setTitle_(f'Status: {self._session_message}')


# ---------------------------------------------------------------------------
# Setup wizard
# ---------------------------------------------------------------------------

class _SetupTarget(AppKit.NSObject):
    """Action target for setup wizard buttons."""

    _get_started_fn = None
    _install_model_fn = None
    _open_accessibility_fn = None
    _complete_fn = None

    @objc.typedSelector(b"v@:@")
    def getStarted_(self, sender):
        if self._get_started_fn:
            self._get_started_fn()

    @objc.typedSelector(b"v@:@")
    def installModel_(self, sender):
        if self._install_model_fn:
            self._install_model_fn()

    @objc.typedSelector(b"v@:@")
    def openAccessibility_(self, sender):
        if self._open_accessibility_fn:
            self._open_accessibility_fn()

    @objc.typedSelector(b"v@:@")
    def completeSetup_(self, sender):
        if self._complete_fn:
            self._complete_fn()


class SetupWizard:
    """Two-page onboarding wizard: welcome screen then setup checklist."""

    def __init__(self, on_complete):
        """
        on_complete — callable invoked (on main thread) when the user
        clicks 'Complete Setup' and all checks pass.
        """
        self._on_complete = on_complete

        width, height = 480, 400
        screen = AppKit.NSScreen.mainScreen().frame()
        x = (screen.size.width - width) / 2
        y = (screen.size.height - height) / 2

        self._window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            AppKit.NSMakeRect(x, y, width, height),
            AppKit.NSWindowStyleMaskTitled | AppKit.NSWindowStyleMaskClosable,
            AppKit.NSBackingStoreBuffered,
            False,
        )
        self._window.setTitle_("Welcome to Talky")
        self._window.setLevel_(AppKit.NSFloatingWindowLevel)

        self._target = _SetupTarget.alloc().init()
        self._target._get_started_fn = self._go_to_checklist
        self._target._install_model_fn = self._request_microphone
        self._target._open_accessibility_fn = self._open_accessibility
        self._target._complete_fn = self._complete

        self._width = width
        self._height = height
        self._timer = None

        self._build_welcome_page()

    # ---- Page 1: Welcome ----

    def _build_welcome_page(self):
        width, height = self._width, self._height
        content = AppKit.NSView.alloc().initWithFrame_(
            AppKit.NSMakeRect(0, 0, width, height)
        )

        # Logo
        from tools.core_paths import resource_path
        logo_path = resource_path("talky-logo.jpg")
        logo_img = AppKit.NSImage.alloc().initWithContentsOfFile_(logo_path)
        if logo_img:
            logo_view = AppKit.NSImageView.alloc().initWithFrame_(
                AppKit.NSMakeRect((width - 100) / 2, height - 160, 100, 100)
            )
            logo_view.setImage_(logo_img)
            logo_view.setImageScaling_(AppKit.NSImageScaleProportionallyUpOrDown)
            content.addSubview_(logo_view)

        # Title
        title = AppKit.NSTextField.labelWithString_("Welcome to Talky")
        title.setFrame_(AppKit.NSMakeRect(20, height - 200, width - 40, 32))
        title.setFont_(AppKit.NSFont.boldSystemFontOfSize_(26))
        title.setAlignment_(AppKit.NSTextAlignmentCenter)
        content.addSubview_(title)

        # USP
        usp = AppKit.NSTextField.labelWithString_(
            "Fast & accurate speech-to-text that stays on your Mac.\n"
            "Your voice never leaves your machine. 100% local, 100% private."
        )
        usp.setFrame_(AppKit.NSMakeRect(40, height - 265, width - 80, 50))
        usp.setFont_(AppKit.NSFont.systemFontOfSize_(14))
        usp.setAlignment_(AppKit.NSTextAlignmentCenter)
        usp.setTextColor_(AppKit.NSColor.secondaryLabelColor())
        usp.setMaximumNumberOfLines_(2)
        content.addSubview_(usp)

        # Get Started button
        btn = AppKit.NSButton.alloc().initWithFrame_(
            AppKit.NSMakeRect((width - 160) / 2, 40, 160, 36)
        )
        btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        btn.setTitle_("Get Started")
        btn.setTarget_(self._target)
        btn.setAction_("getStarted:")
        btn.setFont_(AppKit.NSFont.systemFontOfSize_weight_(14, AppKit.NSFontWeightMedium))
        content.addSubview_(btn)

        self._window.setContentView_(content)

    # ---- Page 2: Checklist ----

    def _build_checklist_page(self):
        width, height = self._width, self._height
        content = AppKit.NSView.alloc().initWithFrame_(
            AppKit.NSMakeRect(0, 0, width, height)
        )

        # Title
        title = AppKit.NSTextField.labelWithString_("Setup Checklist")
        title.setFrame_(AppKit.NSMakeRect(20, height - 50, width - 40, 30))
        title.setFont_(AppKit.NSFont.boldSystemFontOfSize_(20))
        content.addSubview_(title)

        subtitle = AppKit.NSTextField.labelWithString_(
            "Allow microphone and Accessibility access. No Ollama needed."
        )
        subtitle.setFrame_(AppKit.NSMakeRect(20, height - 75, width - 40, 20))
        subtitle.setFont_(AppKit.NSFont.systemFontOfSize_(13))
        subtitle.setTextColor_(AppKit.NSColor.secondaryLabelColor())
        content.addSubview_(subtitle)

        # ---- Row 1: Ollama + Model ----
        row1_y = height - 130

        self._ollama_spinner = AppKit.NSProgressIndicator.alloc().initWithFrame_(
            AppKit.NSMakeRect(20, row1_y, 20, 20)
        )
        self._ollama_spinner.setStyle_(AppKit.NSProgressIndicatorStyleSpinning)
        self._ollama_spinner.setControlSize_(AppKit.NSControlSizeSmall)
        self._ollama_spinner.startAnimation_(None)
        content.addSubview_(self._ollama_spinner)

        self._ollama_icon = AppKit.NSImageView.alloc().initWithFrame_(
            AppKit.NSMakeRect(20, row1_y, 20, 20)
        )
        self._ollama_icon.setHidden_(True)
        content.addSubview_(self._ollama_icon)

        self._ollama_label = AppKit.NSTextField.labelWithString_("Checking microphone permission…")
        self._ollama_label.setFrame_(AppKit.NSMakeRect(48, row1_y, 260, 20))
        self._ollama_label.setFont_(AppKit.NSFont.systemFontOfSize_(13))
        self._ollama_label.setTextColor_(AppKit.NSColor.secondaryLabelColor())
        content.addSubview_(self._ollama_label)

        self._ollama_button = AppKit.NSButton.alloc().initWithFrame_(
            AppKit.NSMakeRect(340, row1_y - 2, 120, 24)
        )
        self._ollama_button.setBezelStyle_(AppKit.NSBezelStyleRounded)
        self._ollama_button.setTitle_("Allow Microphone")
        self._ollama_button.setTarget_(self._target)
        self._ollama_button.setAction_("installModel:")
        self._ollama_button.setHidden_(True)
        content.addSubview_(self._ollama_button)

        # ---- Row 2: Accessibility ----
        row2_y = height - 180

        self._ax_spinner = AppKit.NSProgressIndicator.alloc().initWithFrame_(
            AppKit.NSMakeRect(20, row2_y, 20, 20)
        )
        self._ax_spinner.setStyle_(AppKit.NSProgressIndicatorStyleSpinning)
        self._ax_spinner.setControlSize_(AppKit.NSControlSizeSmall)
        self._ax_spinner.startAnimation_(None)
        content.addSubview_(self._ax_spinner)

        self._ax_icon = AppKit.NSImageView.alloc().initWithFrame_(
            AppKit.NSMakeRect(20, row2_y, 20, 20)
        )
        self._ax_icon.setHidden_(True)
        content.addSubview_(self._ax_icon)

        self._ax_label = AppKit.NSTextField.labelWithString_("Checking Accessibility...")
        self._ax_label.setFrame_(AppKit.NSMakeRect(48, row2_y, 260, 20))
        self._ax_label.setFont_(AppKit.NSFont.systemFontOfSize_(13))
        self._ax_label.setTextColor_(AppKit.NSColor.secondaryLabelColor())
        content.addSubview_(self._ax_label)

        self._ax_button = AppKit.NSButton.alloc().initWithFrame_(
            AppKit.NSMakeRect(340, row2_y - 2, 120, 24)
        )
        self._ax_button.setBezelStyle_(AppKit.NSBezelStyleRounded)
        self._ax_button.setTitle_("Open Settings")
        self._ax_button.setTarget_(self._target)
        self._ax_button.setAction_("openAccessibility:")
        self._ax_button.setHidden_(True)
        content.addSubview_(self._ax_button)

        # ---- Complete button ----
        self._complete_button = AppKit.NSButton.alloc().initWithFrame_(
            AppKit.NSMakeRect(width - 170, 20, 150, 32)
        )
        self._complete_button.setBezelStyle_(AppKit.NSBezelStyleRounded)
        self._complete_button.setTitle_("Complete Setup")
        self._complete_button.setTarget_(self._target)
        self._complete_button.setAction_("completeSetup:")
        self._complete_button.setEnabled_(False)
        content.addSubview_(self._complete_button)

        self._window.setContentView_(content)

        self._checking = False

        # Run first check in background, then start periodic timer
        self._run_checks_async()
        self._timer = AppKit.NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
            2.0, True, lambda t: self._run_checks_async()
        )

    def _go_to_checklist(self):
        """Transition from welcome page to checklist page."""
        self._build_checklist_page()

    # ---- Permission checks ----

    def _check_accessibility(self) -> bool:
        return ApplicationServices.AXIsProcessTrustedWithOptions(
            {ApplicationServices.kAXTrustedCheckOptionPrompt: False})

    def _run_checks_async(self):
        """Run dependency checks in a background thread to avoid blocking UI."""
        if self._checking:
            return
        self._checking = True

        def _do_checks():
            microphone_ok = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(AVFoundation.AVMediaTypeAudio) == AVFoundation.AVAuthorizationStatusAuthorized
            ax_ok = self._check_accessibility()

            def _update_ui():
                self._checking = False

                self._set_row_status(
                    self._ollama_spinner,
                    self._ollama_icon,
                    self._ollama_label,
                    self._ollama_button,
                    ok=microphone_ok,
                    ok_text="Microphone permission granted",
                    fail_text="Microphone permission required",
                )

                # Update Accessibility row
                self._set_row_status(
                    self._ax_spinner,
                    self._ax_icon,
                    self._ax_label,
                    self._ax_button,
                    ok=ax_ok,
                    ok_text="Accessibility permission granted",
                    fail_text="Accessibility permission required",
                )

                self._complete_button.setEnabled_(microphone_ok and ax_ok)

            _Dispatcher.dispatch_to_main(_update_ui)

        threading.Thread(target=_do_checks, daemon=True).start()

    def _set_row_status(self, spinner, icon_view, label, button, ok, ok_text, fail_text):
        spinner.stopAnimation_(None)
        spinner.setHidden_(True)
        icon_view.setHidden_(False)

        if ok:
            img = AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
                "checkmark.circle.fill", "OK"
            )
            label.setStringValue_(ok_text)
            label.setTextColor_(AppKit.NSColor.labelColor())
            button.setHidden_(True)
        else:
            img = AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
                "xmark.circle.fill", "Missing"
            )
            label.setStringValue_(fail_text)
            label.setTextColor_(AppKit.NSColor.systemRedColor())
            button.setHidden_(False)
        if img:
            img.setTemplate_(False)
            icon_view.setImage_(img)

    # ---- Actions ----

    def _request_microphone(self):
        status = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(AVFoundation.AVMediaTypeAudio)
        if status == AVFoundation.AVAuthorizationStatusNotDetermined:
            AVFoundation.AVCaptureDevice.requestAccessForMediaType_completionHandler_(
                AVFoundation.AVMediaTypeAudio, lambda granted: None)
        else:
            subprocess.Popen(['open', 'x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone'])

    def _open_accessibility(self):
        """Open macOS Accessibility preferences pane."""
        ApplicationServices.AXIsProcessTrustedWithOptions(
            {ApplicationServices.kAXTrustedCheckOptionPrompt: True})
        subprocess.Popen([
            "open",
            "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
        ])

    def _complete(self):
        """User clicked Complete Setup."""
        if self._timer:
            self._timer.invalidate()
            self._timer = None
        self._window.orderOut_(None)
        if self._on_complete:
            self._on_complete()

    # ---- Show / Close ----

    def show(self):
        self._window.makeKeyAndOrderFront_(None)
        AppKit.NSApp.activateIgnoringOtherApps_(True)

    def close(self):
        if self._timer:
            self._timer.invalidate()
            self._timer = None
        self._window.orderOut_(None)


# ---------------------------------------------------------------------------
# TalkyApp — wires everything together
# ---------------------------------------------------------------------------

class TalkyApp:
    """
    Manages the NSApplication lifecycle.

    pipeline_fn(on_record_start, on_record_stop, on_processing, on_idle,
                get_language, get_formatting_mode)
        — a callable that runs the dictation loop in a background thread.
        The four callbacks update the UI (dispatched to main thread automatically).
        get_language returns the currently selected language code.
    """

    def __init__(self, pipeline_fn, on_cleanup=None, needs_setup=False):
        self._pipeline_fn = pipeline_fn
        self._on_cleanup = on_cleanup
        self._needs_setup = needs_setup
        self._config = ConfigManager()
        self._app = AppKit.NSApplication.sharedApplication()
        self._app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)

        self.overlay = OverlayWindow()
        self.status_bar = StatusBarController(on_quit=self._quit, config=self._config)
        self._wizard = None
        self._controller = None
        self._audio = None
        self._output = None
        self._formatter = None
        self._ai_download_prompt_open = False
        self.status_bar.on_formatting_change = self._formatting_changed
        self.status_bar._menu_target._ai_install_fn = self._install_ai
        self.status_bar._menu_target._ai_cancel_fn = self._cancel_ai_download
        self._notice_timer = None
        self._session_state = 'loading'
        self._session_message = 'Loading speech model…'
        self.status_bar._menu_target._cancel_fn = self._cancel_dictation
        self.status_bar._menu_target._copy_fn = lambda: self._copy_dictation(False)
        self.status_bar._menu_target._copy_raw_fn = lambda: self._copy_dictation(True)
        self.status_bar._menu_target._clear_fn = self._clear_dictation
        self.status_bar._menu_target._toggle_fn = self._toggle_dictation

        # Meeting mode callbacks — set by pipeline after init
        self._on_meeting_start = None
        self._on_meeting_stop = None
        self.status_bar._menu_target._meeting_fn = self._toggle_meeting

    def run(self):
        if self._needs_setup:
            self._show_wizard()
            self.status_bar.set_setup_required(True)
        else:
            self._start_pipeline()
        self._app.run()

    def _show_wizard(self):
        self._wizard = SetupWizard(on_complete=self._on_setup_complete)
        self._wizard.show()

    def _on_setup_complete(self):
        """Called on main thread when wizard finishes."""
        self._config.mark_setup_complete()
        self._needs_setup = False
        self._wizard = None
        self.status_bar.set_setup_required(False)
        self._start_pipeline()

    def _start_pipeline(self):
        t = threading.Thread(
            target=self._run_pipeline,
            args=(
                self._on_record_start,
                self._on_record_stop,
                self._on_processing,
                self._on_idle,
                self._on_warmup,
                self._on_ready,
                self.status_bar.get_language,
                self.status_bar.get_formatting_mode,
                self._on_stats_update,
                self,  # app_ref for meeting mode wiring
            ),
            daemon=True,
        )
        t.start()

    def _run_pipeline(self, *args):
        try:
            self._pipeline_fn(*args)
        except Exception:
            if self._audio:
                self._audio.close()
            self._on_session_status('error', 'Speech engine unavailable; restart Talky')

    def _formatting_changed(self, mode):
        if self._formatter:
            self._formatter.set_enabled(mode == 'polished')
            if mode == 'polished' and self._formatter.state == 'not_installed':
                self._install_ai()

    def _install_ai(self):
        if not self._formatter:
            self._show_notice('Wait for the speech engine to start')
            return
        if self._ai_download_prompt_open or self._formatter.state in ('downloading', 'loading'):
            return
        if self._formatter.store.installed() and self._formatter.state != 'failed':
            self.status_bar._set_formatting_mode('polished')
            return
        size = self._formatter.store.download_bytes / 1_000_000_000
        alert = AppKit.NSAlert.alloc().init()
        alert.setMessageText_('Download local AI model?')
        alert.setInformativeText_(
            f'Polished mode downloads approximately {size:.2f} GB from Hugging Face. '
            'After installation, formatting runs on this Mac without Ollama. '
            'Fast dictation stays available during the download. This is a preview.')
        alert.addButtonWithTitle_('Download')
        alert.addButtonWithTitle_('Later')
        self._ai_download_prompt_open = True
        try:
            if alert.runModal() == AppKit.NSAlertFirstButtonReturn:
                # Set the selection without invoking the mode-change handler:
                # a failed/instant download must not recursively reopen this alert.
                self.status_bar._set_formatting_mode('polished', notify=False)
                self._formatter.set_enabled(True)
                self._formatter.install()
        finally:
            self._ai_download_prompt_open = False

    def _cancel_ai_download(self):
        if self._formatter:
            self._formatter.cancel_download()

    def _cancel_dictation(self):
        if self._audio:
            self._audio.cancel()

    def _toggle_dictation(self):
        if self._audio:
            # Let the menu close before capturing the destination field.
            timer = threading.Timer(0.25, self._audio.toggle)
            timer.daemon = True
            timer.start()

    def _copy_dictation(self, original):
        result = self._controller.last_result if self._controller else None
        if result and self._output:
            try:
                self._output.copy(result.raw if original else result.text)
                self._show_notice('Original copied' if original else 'Dictation copied')
            except Exception:
                self._show_notice('Could not copy; try again')

    def _clear_dictation(self):
        if self._controller:
            self._controller.clear()
            self._on_session_status(self._controller.state, self._session_message)
            self._show_notice('Last dictation cleared')

    def _restore_session_overlay(self):
        if self._session_state in ('recording', 'transcribing', 'formatting', 'delivering', 'cancelling', 'loading', 'error'):
            self.overlay.show(self._session_message)
        else:
            self.overlay.hide()

    def _show_notice(self, message):
        def show():
            if self._notice_timer:
                self._notice_timer.invalidate()
            self.overlay.show(message)
            self._notice_timer = AppKit.NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
                3.0, False, lambda timer: self._restore_session_overlay())
        _Dispatcher.dispatch_to_main(show)

    def _on_session_status(self, state, message):
        # Capture availability with the event, rather than reading a later
        # controller state when the main-thread callback eventually runs.
        has_result = bool(self._controller and self._controller.last_result)
        def update():
            self._session_state, self._session_message = state, message
            if self._notice_timer:
                self._notice_timer.invalidate()
                self._notice_timer = None
            self.status_bar.set_session_status(state, message, has_result)
            if state == 'ready':
                self.overlay.show(message)
                self._notice_timer = AppKit.NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
                    3.0, False, lambda timer: self.overlay.hide())
            else:
                self.overlay.show(message)
        _Dispatcher.dispatch_to_main(update)

    # -- callbacks (safe to call from any thread) --

    def _on_record_start(self):
        _Dispatcher.dispatch_to_main(self._main_record_start)

    def _on_record_stop(self):
        _Dispatcher.dispatch_to_main(self._main_record_stop)

    def _on_processing(self, text="Transcribing..."):
        _Dispatcher.dispatch_to_main(lambda: self._main_processing(text))

    def _on_idle(self):
        _Dispatcher.dispatch_to_main(self._main_idle)

    def _on_warmup(self):
        _Dispatcher.dispatch_to_main(self._main_warmup)

    def _on_ready(self):
        _Dispatcher.dispatch_to_main(self._main_idle)

    def _on_stats_update(self, stats: dict):
        """Dispatches an update to the stats UI on the main thread."""
        def update():
            self.status_bar.update_stats(stats)
        _Dispatcher.dispatch_to_main(update)

    # -- main-thread UI mutations --

    def _main_record_start(self):
        self.status_bar.set_recording(True)
        self.overlay.show("Listening...")

    def _main_record_stop(self):
        self.status_bar.set_recording(False)
        self.overlay.update_text("Transcribing...")

    def _main_processing(self, text="Transcribing..."):
        self.overlay.update_text(text)

    def _main_idle(self):
        self._session_state, self._session_message = 'ready', 'Ready'
        self.status_bar.set_recording(False)
        self.status_bar.set_session_status('ready', 'Ready', bool(self._controller and self._controller.last_result))
        self.overlay.hide()

    def _main_warmup(self):
        self._session_state, self._session_message = 'loading', 'Loading speech model…'
        self.status_bar.set_recording(False)
        self.status_bar.set_session_status('loading', 'Loading speech model…', False)
        self.overlay.show("Warming up models...")

    def _toggle_meeting(self):
        """Called from menu bar on main thread."""
        if self.status_bar._meeting_active:
            if self._on_meeting_stop:
                self._on_meeting_stop()
        else:
            if self._on_meeting_start:
                self._on_meeting_start()

    def _quit(self):
        if self._controller:
            self._controller.close()
        if self._audio:
            self._audio.close()
        if self._formatter:
            self._formatter.close()
        if self._on_cleanup:
            self._on_cleanup()
        self._app.terminate_(None)
