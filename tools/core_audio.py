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
        self._mode = 'IDLE'
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

        # Pre-create audio stream (device enumeration done once, fast start/stop later)
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype='float32',
            callback=self._audio_callback
        )
        print("[core_audio] Audio stream pre-created (not yet active).", flush=True)

    def _start_capture(self):
        """Start audio capture immediately (called from event tap thread)."""
        self.is_recording = True
        self._stream.start()

    def _handle_press(self, now):
        if self._mode == 'IDLE':
            self._mode = 'HOLDING'
            self._last_press = now
            self._start_capture()
            self._start_event.set()
        elif self._mode == 'WAITING_FOR_DOUBLE':
            if now - self._last_release <= self._double_tap_threshold:
                self._mode = 'TOGGLED'
                print("[core_audio] Double-tap: toggle mode active. Tap again to stop.", flush=True)
            else:
                self._mode = 'HOLDING'
                self._last_press = now
                self._start_capture()
                self._start_event.set()

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

        Quartz.CFRunLoopRun()

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            print(status, flush=True)
        if self.is_recording:
            self.q.put(indata.copy())

    def record_while_pressed(self) -> np.ndarray:
        """Blocks until Fn pressed, records audio, returns buffer on release."""
        self._start_event.clear()
        self._stop_event.clear()
        self._mode = 'IDLE'

        # Drain any leftover chunks from previous recording
        while not self.q.empty():
            self.q.get()

        print("[core_audio] Ready. Hold Fn to dictate, double-tap to toggle.", flush=True)

        # Block until fn pressed (stream already started by _handle_press)
        self._start_event.wait()

        if self.on_record_start:
            self.on_record_start()
        print("[core_audio] Recording...", flush=True)

        # Block until fn released
        self._stop_event.wait()

        self.is_recording = False
        self._stream.stop()
        if self.on_record_stop:
            self.on_record_stop()
        print("[core_audio] Stopped.", flush=True)

        chunks = []
        while not self.q.empty():
            chunks.append(self.q.get())

        if not chunks:
            return np.array([], dtype='float32')

        return np.concatenate(chunks, axis=0).flatten()
