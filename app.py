import objc
import AppKit
import threading


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

class _RoundedBackgroundView(AppKit.NSView):
    """Draws a rounded rectangle with configurable color."""

    _fill_r = 0.1
    _fill_g = 0.1
    _fill_b = 0.1
    _fill_a = 0.88

    def drawRect_(self, rect):
        path = AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            self.bounds(), 12, 12
        )
        AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(
            self._fill_r, self._fill_g, self._fill_b, self._fill_a
        ).setFill()
        path.fill()


# ---------------------------------------------------------------------------
# Overlay window
# ---------------------------------------------------------------------------

class OverlayWindow:
    """Floating pill that shows recording / processing state."""

    def __init__(self):
        width, height = 180, 40
        screen = AppKit.NSScreen.mainScreen().frame()
        x = (screen.size.width - width) / 2
        y = screen.size.height - 80

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
        self._window.setCollectionBehavior_(
            AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
            | AppKit.NSWindowCollectionBehaviorStationary
        )

        content = AppKit.NSView.alloc().initWithFrame_(
            AppKit.NSMakeRect(0, 0, width, height)
        )
        self._window.setContentView_(content)

        self._bg = _RoundedBackgroundView.alloc().initWithFrame_(
            AppKit.NSMakeRect(0, 0, width, height)
        )
        content.addSubview_(self._bg)

        self._label = AppKit.NSTextField.labelWithString_("")
        self._label.setFrame_(AppKit.NSMakeRect(12, 8, width - 24, 24))
        self._label.setFont_(
            AppKit.NSFont.systemFontOfSize_weight_(14, AppKit.NSFontWeightMedium)
        )
        self._label.setTextColor_(AppKit.NSColor.whiteColor())
        self._label.setAlignment_(AppKit.NSTextAlignmentCenter)
        self._label.setDrawsBackground_(False)
        self._label.setBezeled_(False)
        self._label.setEditable_(False)
        self._label.setSelectable_(False)
        content.addSubview_(self._label)

        self._pulse_timer = None
        self._pulse_on = True
        self._meeting_timer = None

    def show(self, text="Listening..."):
        self._label.setStringValue_(text)
        self._window.setAlphaValue_(1.0)
        self._window.orderFrontRegardless()
        if "Listening" in text or "Warming" in text:
            self._start_pulse()

    def update_text(self, text):
        self._label.setStringValue_(text)
        if "Listening" not in text and "Warming" not in text:
            self._stop_pulse()
            self._window.setAlphaValue_(1.0)

    def hide(self):
        self._stop_pulse()
        self._window.orderOut_(None)

    def _start_pulse(self):
        if self._pulse_timer is not None:
            return
        self._pulse_on = True
        self._pulse_timer = AppKit.NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
            0.7, True, self._pulse_tick
        )

    def _pulse_tick(self, timer):
        self._pulse_on = not self._pulse_on
        self._window.setAlphaValue_(1.0 if self._pulse_on else 0.5)

    def _stop_pulse(self):
        if self._pulse_timer is not None:
            self._pulse_timer.invalidate()
            self._pulse_timer = None
        self._window.setAlphaValue_(1.0)

    def set_dictation_style(self):
        """Dark pill for dictation mode."""
        self._bg._fill_r = 0.1
        self._bg._fill_g = 0.1
        self._bg._fill_b = 0.1
        self._bg.setNeedsDisplay_(True)

    def set_meeting_style(self):
        """Blue-tinted pill for meeting mode."""
        self._bg._fill_r = 0.08
        self._bg._fill_g = 0.15
        self._bg._fill_b = 0.35
        self._bg.setNeedsDisplay_(True)

    def start_meeting_timer(self, get_elapsed):
        """Start a 1-second timer that updates the overlay with elapsed time."""
        self._stop_pulse()
        self.set_meeting_style()

        def tick(timer):
            secs = int(get_elapsed())
            mins, s = divmod(secs, 60)
            hrs, m = divmod(mins, 60)
            if hrs > 0:
                time_str = f"{hrs}:{m:02d}:{s:02d}"
            else:
                time_str = f"{m:02d}:{s:02d}"
            self._label.setStringValue_(f"  Meeting — {time_str}")

        self._window.setAlphaValue_(1.0)
        self._window.orderFrontRegardless()
        self._label.setStringValue_("  Meeting — 00:00")
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
    _meeting_fn = None

    @objc.typedSelector(b"v@:@")
    def quitApp_(self, sender):
        if self._quit_fn:
            self._quit_fn()

    @objc.typedSelector(b"v@:@")
    def selectLang_(self, sender):
        if self._lang_fn:
            self._lang_fn(sender.representedObject())

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

    def __init__(self, on_quit):
        self._on_quit = on_quit
        self._language = "en"  # default
        self._menu_target = _MenuTarget.alloc().init()
        self._menu_target._quit_fn = on_quit
        self._menu_target._lang_fn = self._set_language

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
        self._update_lang_checks()
        print(f"[app] Language set to: {code}", flush=True)

    def get_language(self):
        return self._language

    def update_stats(self, stats: dict):
        self._stat_time_saved.setTitle_(f"  ⚡️ Time Saved: {stats.get('time_saved', '0s')}")
        self._stat_dictations.setTitle_(f"  🎤 Dictations: {stats.get('dictations', '0')}")
        self._stat_speed.setTitle_(f"  🚀 Speed: {stats.get('speed_wpm', '0')} WPM")

    def set_recording(self, is_recording):
        self._is_recording = is_recording
        self._update_display()

    def set_meeting_active(self, active):
        self._meeting_active = active
        self._update_display()

    def set_ollama_offline(self, offline):
        self._ollama_offline = offline
        self._update_display()

    def _update_display(self):
        button = self._status_item.button()
        if self._is_recording:
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


# ---------------------------------------------------------------------------
# TalkyApp — wires everything together
# ---------------------------------------------------------------------------

class TalkyApp:
    """
    Manages the NSApplication lifecycle.

    pipeline_fn(on_record_start, on_record_stop, on_processing, on_idle, get_language)
        — a callable that runs the dictation loop in a background thread.
        The four callbacks update the UI (dispatched to main thread automatically).
        get_language returns the currently selected language code.
    """

    def __init__(self, pipeline_fn, on_cleanup=None):
        self._pipeline_fn = pipeline_fn
        self._on_cleanup = on_cleanup
        self._app = AppKit.NSApplication.sharedApplication()
        self._app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)

        self.overlay = OverlayWindow()
        self.status_bar = StatusBarController(on_quit=self._quit)

        # Meeting mode callbacks — set by pipeline after init
        self._on_meeting_start = None
        self._on_meeting_stop = None
        self.status_bar._menu_target._meeting_fn = self._toggle_meeting

    def run(self):
        t = threading.Thread(
            target=self._pipeline_fn,
            args=(
                self._on_record_start,
                self._on_record_stop,
                self._on_processing,
                self._on_idle,
                self._on_warmup,
                self._on_ready,
                self.status_bar.get_language,
                self._on_stats_update,
                self,  # app_ref for meeting mode wiring
            ),
            daemon=True,
        )
        t.start()
        self._app.run()

    # -- callbacks (safe to call from any thread) --

    def _on_record_start(self):
        _Dispatcher.dispatch_to_main(self._main_record_start)

    def _on_record_stop(self):
        _Dispatcher.dispatch_to_main(self._main_record_stop)

    def _on_processing(self):
        _Dispatcher.dispatch_to_main(self._main_processing)

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
        self.overlay.show("  Listening...")

    def _main_record_stop(self):
        self.status_bar.set_recording(False)
        self.overlay.update_text("  Processing...")

    def _main_processing(self):
        self.overlay.update_text("  Processing...")

    def _main_idle(self):
        self.status_bar.set_recording(False)
        self.overlay.hide()

    def _main_warmup(self):
        self.status_bar.set_recording(False)
        self.overlay.show("  Warming up models...")

    def _toggle_meeting(self):
        """Called from menu bar on main thread."""
        if self.status_bar._meeting_active:
            if self._on_meeting_stop:
                self._on_meeting_stop()
        else:
            if self._on_meeting_start:
                self._on_meeting_start()

    def _quit(self):
        if self._on_cleanup:
            self._on_cleanup()
        self._app.terminate_(None)
