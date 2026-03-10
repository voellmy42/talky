# Talky v2: Menu Bar App + Recording Overlay

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform Talky from a terminal script into a macOS menu bar app with a floating recording overlay and fix the broken Fn key detection.

**Architecture:** NSApplication-based menu bar app using PyObjC. The main thread runs AppKit's event loop (required by macOS). The dictation pipeline runs in a background thread. A floating transparent NSWindow acts as the recording overlay. The Fn key event tap is integrated into the AppKit run loop (fixing the current bug where it runs on the wrong thread).

**Tech Stack:** PyObjC (AppKit, Quartz, ApplicationServices), sounddevice, faster-whisper, Ollama, pyperclip, pyautogui

---

### Task 1: Fix Fn Key Detection in core_audio.py

**The Bug:** Line 143 calls `CFRunLoopGetCurrent()` on the main thread, but `CFRunLoopRun()` executes on a separate daemon thread (line 149-151). The event tap is attached to the main thread's run loop, but nobody runs that run loop — so events never fire.

**The Fix:** Restructure so event tap creation + run loop source + `CFRunLoopRun()` all happen inside the same thread. Also refactor the class to use a persistent event tap (created once in `__init__`) with callback-based state notifications, instead of recreating everything on each `record_while_pressed()` call.

**Files:**
- Modify: `tools/core_audio.py` (full rewrite)

**Step 1: Rewrite core_audio.py**

The new design:
- `__init__`: Creates a persistent Quartz event tap thread that runs for the app's lifetime
- `record_while_pressed()`: Resets events, waits for press/release, captures audio, returns buffer
- Event tap thread: Creates tap, adds to its own run loop, runs `CFRunLoopRun()`
- State callbacks: Optional `on_record_start` / `on_record_stop` callables for UI integration

```python
import sounddevice as sd
import numpy as np
import threading
import queue
import time
import sys

class AudioCaptureTool:
    def __init__(self, sample_rate=16000, hotkey='fn', on_record_start=None, on_record_stop=None):
        self.sample_rate = sample_rate
        self.hotkey = hotkey.lower()
        self.on_record_start = on_record_start
        self.on_record_stop = on_record_stop

        self.q = queue.Queue()
        self.is_recording = False

        # Threading events for synchronization
        self._start_event = threading.Event()
        self._stop_event = threading.Event()

        # State machine
        self._mode = 'IDLE'  # IDLE, HOLDING, WAITING_FOR_DOUBLE, TOGGLED
        self._last_press = 0.0
        self._last_release = 0.0
        self._double_tap_threshold = 0.4

        # Verify accessibility permission on macOS
        if sys.platform == 'darwin':
            import ApplicationServices
            if not ApplicationServices.AXIsProcessTrusted():
                print("\n#########################################################")
                print("MACOS ACCESSIBILITY PERMISSION REQUIRED")
                print("System Settings > Privacy & Security > Accessibility")
                print("Enable your Terminal app, then restart.")
                print("#########################################################\n", flush=True)
                sys.exit(1)

            # Start persistent event tap thread
            self._tap_thread = threading.Thread(target=self._run_event_tap, daemon=True)
            self._tap_thread.start()

    def _handle_press(self, now):
        if self._mode == 'IDLE':
            self._mode = 'HOLDING'
            self._last_press = now
            self._start_event.set()
        elif self._mode == 'WAITING_FOR_DOUBLE':
            if now - self._last_release <= self._double_tap_threshold:
                self._mode = 'TOGGLED'
                print("[core_audio] Double-tap: toggle mode active. Tap again to stop.", flush=True)
            else:
                self._mode = 'HOLDING'
                self._last_press = now
                self._start_event.set()
        # TOGGLED press: ignore (release stops it)

    def _handle_release(self, now):
        if self._mode == 'HOLDING':
            if now - self._last_press <= self._double_tap_threshold:
                self._mode = 'WAITING_FOR_DOUBLE'
                self._last_release = now
                threading.Thread(target=self._check_double_tap_timeout, daemon=True).start()
            else:
                self._mode = 'IDLE'
                self._stop_event.set()
        elif self._mode == 'TOGGLED':
            self._mode = 'IDLE'
            self._stop_event.set()

    def _check_double_tap_timeout(self):
        time.sleep(self._double_tap_threshold)
        if self._mode == 'WAITING_FOR_DOUBLE':
            self._mode = 'IDLE'
            self._stop_event.set()

    def _run_event_tap(self):
        """Runs in a dedicated thread. Creates event tap and its own CFRunLoop."""
        import Quartz

        def callback(proxy, type_, event, refcon):
            now = time.time()
            try:
                if self.hotkey == 'fn' and type_ == Quartz.kCGEventFlagsChanged:
                    keycode = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
                    if keycode == 63:
                        flags = Quartz.CGEventGetFlags(event)
                        pressed = (flags & Quartz.kCGEventFlagMaskSecondaryFn) != 0
                        if pressed:
                            self._handle_press(now)
                        else:
                            self._handle_release(now)
            except Exception as e:
                print(f"[core_audio] Event tap error: {e}", flush=True)
            return event

        tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionListenOnly,
            Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged),
            callback,
            None
        )

        if not tap:
            print("[core_audio] Failed to create event tap. Check accessibility permissions.", flush=True)
            return

        source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
        loop = Quartz.CFRunLoopGetCurrent()
        Quartz.CFRunLoopAddSource(loop, source, Quartz.kCFRunLoopCommonModes)
        Quartz.CGEventTapEnable(tap, True)
        print("[core_audio] Fn key event tap active.", flush=True)

        # This blocks forever — which is what we want for the daemon thread
        Quartz.CFRunLoopRun()

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            print(status, flush=True)
        if self.is_recording:
            self.q.put(indata.copy())

    def record_while_pressed(self) -> np.ndarray:
        """Blocks until Fn pressed, records audio, returns buffer on release."""
        # Reset state for this recording cycle
        self._start_event.clear()
        self._stop_event.clear()
        self._mode = 'IDLE'

        # Drain any leftover audio from previous cycle
        while not self.q.empty():
            self.q.get()

        print(f"[core_audio] Ready. Hold Fn to dictate, double-tap to toggle.", flush=True)

        # Block until Fn pressed
        self._start_event.wait()

        self.is_recording = True
        if self.on_record_start:
            self.on_record_start()
        print("[core_audio] Recording...", flush=True)

        stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype='float32',
            callback=self._audio_callback
        )

        with stream:
            self._stop_event.wait()

        self.is_recording = False
        if self.on_record_stop:
            self.on_record_stop()
        print("[core_audio] Stopped.", flush=True)

        chunks = []
        while not self.q.empty():
            chunks.append(self.q.get())

        if not chunks:
            return np.array([], dtype='float32')

        return np.concatenate(chunks, axis=0).flatten()
```

**Step 2: Verify Fn key works**

Run: `python -c "from tools.core_audio import AudioCaptureTool; a = AudioCaptureTool(); buf = a.record_while_pressed(); print(f'Got {len(buf)} samples')"`

Expected: Press Fn → "Recording..." appears. Release Fn → "Stopped." appears. Buffer has samples.

---

### Task 2: Create the Menu Bar App (app.py)

**Files:**
- Create: `app.py`

**Step 1: Write app.py**

This file contains:
- `TalkyApp`: Sets up NSApplication as a menu bar app (no dock icon)
- `StatusBarController`: NSStatusItem with mic icon, dropdown menu, icon state changes
- `OverlayWindow`: Floating pill at top-center of screen with recording status

```python
import objc
import AppKit
import Quartz
import threading

# --- Overlay Window ---

class OverlayWindow:
    """Floating pill overlay that shows recording/processing state."""

    def __init__(self):
        # Pill dimensions
        width, height = 180, 40
        screen = AppKit.NSScreen.mainScreen().frame()
        x = (screen.size.width - width) / 2
        y = screen.size.height - 80  # near top

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

        # Content view with rounded dark background
        content = AppKit.NSView.alloc().initWithFrame_(AppKit.NSMakeRect(0, 0, width, height))
        self._window.setContentView_(content)

        # Background: dark rounded rect
        self._bg = _RoundedBackgroundView.alloc().initWithFrame_(AppKit.NSMakeRect(0, 0, width, height))
        content.addSubview_(self._bg)

        # Label
        self._label = AppKit.NSTextField.labelWithString_("")
        self._label.setFrame_(AppKit.NSMakeRect(12, 8, width - 24, 24))
        self._label.setFont_(AppKit.NSFont.systemFontOfSize_weight_(14, AppKit.NSFontWeightMedium))
        self._label.setTextColor_(AppKit.NSColor.whiteColor())
        self._label.setAlignment_(AppKit.NSTextAlignmentCenter)
        self._label.setDrawsBackground_(False)
        self._label.setBezeled_(False)
        self._label.setEditable_(False)
        self._label.setSelectable_(False)
        content.addSubview_(self._label)

        # Pulse animation timer
        self._pulse_timer = None
        self._pulse_on = True

    def show(self, text="Listening..."):
        """Show the overlay with given text. Must be called on main thread."""
        self._label.setStringValue_(text)
        self._window.setAlphaValue_(1.0)
        self._window.orderFrontRegardless()
        if "Listening" in text:
            self._start_pulse()

    def update_text(self, text):
        self._label.setStringValue_(text)
        if "Listening" not in text:
            self._stop_pulse()
            self._window.setAlphaValue_(1.0)

    def hide(self):
        """Hide the overlay. Must be called on main thread."""
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
        target = 1.0 if self._pulse_on else 0.5
        self._window.setAlphaValue_(target)

    def _stop_pulse(self):
        if self._pulse_timer is not None:
            self._pulse_timer.invalidate()
            self._pulse_timer = None
        self._window.setAlphaValue_(1.0)


class _RoundedBackgroundView(AppKit.NSView):
    """A view that draws a dark rounded rectangle."""

    def drawRect_(self, rect):
        path = AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            self.bounds(), 12, 12
        )
        AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.1, 0.1, 0.1, 0.88).setFill()
        path.fill()


# --- Status Bar Controller ---

class StatusBarController:
    """Manages the menu bar icon and dropdown."""

    # Unicode characters for menu bar (avoids needing image assets)
    MIC_IDLE = "\U0001F399"      # 🎙 studio microphone
    MIC_RECORDING = "\U0001F534" # 🔴 red circle

    def __init__(self, on_quit):
        self._status_item = AppKit.NSStatusBar.systemStatusBar().statusItemWithLength_(
            AppKit.NSVariableStatusItemLength
        )
        self._on_quit = on_quit

        button = self._status_item.button()
        button.setTitle_(self.MIC_IDLE)
        button.setFont_(AppKit.NSFont.systemFontOfSize_(16))

        self._build_menu()

    def _build_menu(self):
        menu = AppKit.NSMenu.alloc().init()

        self._status_menu_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Status: Ready", None, ""
        )
        self._status_menu_item.setEnabled_(False)
        menu.addItem_(self._status_menu_item)

        menu.addItem_(AppKit.NSMenuItem.separatorItem())

        quit_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Quit Talky", "quitApp:", "q"
        )
        quit_item.setTarget_(self)
        menu.addItem_(quit_item)

        self._status_item.setMenu_(menu)

    def set_recording(self, is_recording):
        button = self._status_item.button()
        if is_recording:
            button.setTitle_(self.MIC_RECORDING)
            self._status_menu_item.setTitle_("Status: Recording...")
        else:
            button.setTitle_(self.MIC_IDLE)
            self._status_menu_item.setTitle_("Status: Ready")

    @objc.typedSelector(b"v@:@")
    def quitApp_(self, sender):
        self._on_quit()


# --- App Lifecycle ---

class TalkyApp:
    """Manages the NSApplication lifecycle and wires everything together."""

    def __init__(self, pipeline_fn):
        """
        pipeline_fn: a callable that runs the dictation pipeline loop.
                      It receives (on_record_start_main, on_record_stop_main, on_processing, on_idle)
                      callbacks that it must call to update the UI (they dispatch to main thread).
        """
        self._pipeline_fn = pipeline_fn
        self._app = AppKit.NSApplication.sharedApplication()

        # Hide dock icon — menu bar only
        self._app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)

        self.overlay = OverlayWindow()
        self.status_bar = StatusBarController(on_quit=self._quit)

    def run(self):
        """Start the pipeline thread and then run the AppKit main loop (blocks forever)."""
        t = threading.Thread(target=self._pipeline_fn, args=(
            self._on_record_start,
            self._on_record_stop,
            self._on_processing,
            self._on_idle,
        ), daemon=True)
        t.start()

        self._app.run()

    # --- UI callbacks (called from background thread, dispatch to main) ---

    def _on_record_start(self):
        self._perform_on_main(self._main_record_start)

    def _on_record_stop(self):
        self._perform_on_main(self._main_record_stop)

    def _on_processing(self):
        self._perform_on_main(self._main_processing)

    def _on_idle(self):
        self._perform_on_main(self._main_idle)

    def _perform_on_main(self, fn):
        """Dispatch a zero-arg function to the main thread."""
        fn()  # will use performSelectorOnMainThread in _MainDispatcher

    # --- Actual UI mutations (must run on main thread) ---

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

    def _quit(self):
        self._app.terminate_(None)
```

**Step 2: Verify menu bar + overlay renders**

Run: `python -c "
from app import TalkyApp
import time, threading
def fake_pipeline(on_start, on_stop, on_proc, on_idle):
    time.sleep(2)
    on_start()
    time.sleep(3)
    on_stop()
    time.sleep(2)
    on_idle()
    time.sleep(1)
    import AppKit; AppKit.NSApplication.sharedApplication().terminate_(None)
app = TalkyApp(fake_pipeline)
app.run()
"`

Expected: Menu bar mic icon appears. After 2s overlay "Listening..." shows (pulsing). After 3s "Processing..." shows. After 2s overlay hides. App quits.

---

### Task 3: Refactor main.py to Use the App

**Files:**
- Modify: `main.py` (full rewrite)

**Step 1: Rewrite main.py**

The new main.py:
1. Defines `pipeline_loop()` that accepts UI callbacks
2. Creates `AudioCaptureTool` wired to the UI callbacks
3. Initializes STT, LLM, output tools
4. Runs the pipeline in a loop
5. Creates `TalkyApp` with the pipeline function and calls `app.run()`

Since `TalkyApp.run()` dispatches UI callbacks from background thread to main thread, we need to use `performSelectorOnMainThread`. We'll refine `app.py`'s `_perform_on_main` to use proper `objc` dispatching.

```python
import time
import sys
from app import TalkyApp
from tools.core_audio import AudioCaptureTool
from tools.core_stt import STTTool
from tools.core_llm import LLMFormatter
from tools.core_output import OutputInjector


def main():
    print("--- Initializing Talky ---", flush=True)

    stt_tool = STTTool(model_size="tiny", compute_type="int8")
    llm_tool = LLMFormatter(host="http://localhost:11434", model="qwen2.5:3b")
    output_tool = OutputInjector()

    print("--- Models loaded. Starting app... ---", flush=True)

    def pipeline_loop(on_record_start, on_record_stop, on_processing, on_idle):
        # Create audio tool with UI callbacks
        audio_tool = AudioCaptureTool(
            hotkey='fn',
            on_record_start=on_record_start,
            on_record_stop=on_record_stop,
        )

        while True:
            try:
                audio_buffer = audio_tool.record_while_pressed()

                if len(audio_buffer) == 0:
                    on_idle()
                    continue

                on_processing()
                start_time = time.time()

                raw_text = stt_tool.transcribe(audio_buffer)
                if not raw_text:
                    print("[pipeline] No speech detected.", flush=True)
                    on_idle()
                    continue

                cleaned_text = llm_tool.format_text(raw_text)
                if not cleaned_text:
                    on_idle()
                    continue

                success = output_tool.inject(cleaned_text)
                elapsed = time.time() - start_time
                print(f"[pipeline] Done in {elapsed:.2f}s", flush=True)

                on_idle()

            except Exception as e:
                print(f"[pipeline] Error: {e}", flush=True)
                on_idle()

    app = TalkyApp(pipeline_loop)
    app.run()


if __name__ == "__main__":
    main()
```

**Step 2: Full integration test**

Run: `python main.py`

Expected:
1. Terminal shows model loading messages
2. Menu bar microphone icon appears
3. Press Fn → overlay "Listening..." appears, icon turns red
4. Release Fn → overlay shows "Processing...", speech is transcribed, text is injected
5. Overlay disappears, icon returns to normal

---

### Task 4: Fix main-thread UI dispatching

**Problem:** AppKit UI mutations MUST happen on the main thread. Our callbacks fire from the pipeline background thread. We need `performSelectorOnMainThread:withObject:waitUntilDone:`.

**Files:**
- Modify: `app.py` (update `_perform_on_main`)

**Step 1: Add an ObjC helper class for main-thread dispatch**

Add a small `NSObject` subclass that can receive `performSelectorOnMainThread` calls:

```python
class _Dispatcher(AppKit.NSObject):
    """NSObject subclass to dispatch blocks to the main thread."""

    _blocks = {}  # class-level dict to prevent GC of the callable
    _counter = 0

    def doBlock_(self, key):
        fn = _Dispatcher._blocks.pop(key, None)
        if fn:
            fn()

    @classmethod
    def dispatch_to_main(cls, fn):
        key = f"block_{cls._counter}"
        cls._counter += 1
        cls._blocks[key] = fn
        inst = cls.alloc().init()
        inst.performSelectorOnMainThread_withObject_waitUntilDone_(
            objc.selector(inst.doBlock_, signature=b"v@:@"),
            key,
            False,
        )
```

Then update `TalkyApp._perform_on_main`:

```python
def _perform_on_main(self, fn):
    _Dispatcher.dispatch_to_main(fn)
```

---

### Implementation Order

1. **Task 1** — Fix `core_audio.py` (Fn key bug). Test standalone.
2. **Task 2** — Create `app.py` (menu bar + overlay). Test with fake pipeline.
3. **Task 4** — Fix main-thread dispatching in `app.py` (integrated into Task 2 write).
4. **Task 3** — Rewrite `main.py` to wire everything together. Full integration test.

Total: 3 files modified/created. ~250 lines of new code. Zero new pip dependencies (PyObjC already installed via Quartz).
