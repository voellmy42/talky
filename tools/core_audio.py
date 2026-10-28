import sounddevice as sd
import numpy as np
import threading
import queue
import time
import sys
from collections import deque

if sys.platform == 'darwin':
    import AVFoundation
    import av


class AudioRingBuffer:
    """Keeps an exact-duration tail of mono float32 audio."""

    def __init__(self, max_samples):
        self.max_samples = max(0, int(max_samples))
        self._chunks = deque()
        self._sample_count = 0

    def append(self, chunk):
        audio = np.asarray(chunk, dtype=np.float32).reshape(-1)
        if not self.max_samples or audio.size == 0:
            return
        self._chunks.append(audio)
        self._sample_count += audio.size

        excess = self._sample_count - self.max_samples
        while excess > 0 and self._chunks:
            first = self._chunks[0]
            if excess >= first.size:
                self._chunks.popleft()
                self._sample_count -= first.size
                excess -= first.size
            else:
                self._chunks[0] = first[excess:].copy()
                self._sample_count -= excess
                excess = 0

    def snapshot(self):
        if not self._chunks:
            return np.array([], dtype=np.float32)
        return np.concatenate(tuple(self._chunks)).astype(np.float32, copy=False)


class AudioCaptureTool:
    def __init__(self, sample_rate=16000, hotkey='fn', on_record_start=None,
                 on_record_stop=None, pre_roll_seconds=0,
                 on_capture_request=None, on_cancel=None, on_busy=None,
                 get_toggle_shortcut=lambda: 'section'):
        self.sample_rate = sample_rate
        self.hotkey = hotkey.lower()
        self.on_record_start = on_record_start
        self.on_record_stop = on_record_stop
        self.on_capture_request = on_capture_request
        self.on_cancel = on_cancel
        self.on_busy = on_busy
        self.get_toggle_shortcut = get_toggle_shortcut
        self._control_lock = threading.RLock()
        self._cancelled = False
        self.released_at = None
        self._closed = False
        self._tap_ready = threading.Event()
        self._tap_error = None
        self._controls = queue.Queue()

        self.q = queue.Queue()
        self.is_recording = False
        self.input_level = 0.0
        self._audio_lock = threading.Lock()
        self._ring_buffer = AudioRingBuffer(sample_rate * pre_roll_seconds)
        self._engine_running = False

        # Threading events for synchronization
        self._start_event = threading.Event()
        self._stop_event = threading.Event()

        # State machine
        self._mode = 'IDLE'
        self._last_press = 0.0
        self._last_release = 0.0
        self._double_tap_threshold = 0.4
        self.meeting_active = False
        self._dictation_session_active = False

        # State for macOS audio engine
        self.input_node = None
        self.hw_format = None
        self.resampler = None

        # Accessibility permission is enforced by the setup wizard before
        # AudioCaptureTool is ever instantiated.
        if sys.platform == 'darwin':
            # Start persistent event tap thread
            self._tap_thread = threading.Thread(target=self._run_event_tap, daemon=True)
            self._tap_thread.start()
            
            # Setup AVAudioEngine
            self.engine = AVFoundation.AVAudioEngine.alloc().init()

            def capture_callback(buffer, time_info):
                try:
                    # Use local references to avoid races during device changes.
                    resampler = self.resampler
                    hw_format = self.hw_format
                    if not resampler or not hw_format:
                        return

                    frames = buffer.frameLength()
                    data_ptr = buffer.floatChannelData()
                    if not data_ptr:
                        return

                    audio_np = np.array(data_ptr[0][:frames], dtype=np.float32)
                    frame = av.AudioFrame.from_ndarray(
                        audio_np.reshape(1, -1), format='flt', layout='mono'
                    )
                    frame.sample_rate = int(hw_format.sampleRate())

                    for resampled in resampler.resample(frame) or []:
                        self._route_audio_chunk(resampled.to_ndarray().flatten())
                except Exception as e:
                    print(f"[core_audio] Callback error: {e}", flush=True)

            self._capture_callback = capture_callback
            if not self._tap_ready.wait(2) or self._tap_error:
                self.close()
                raise RuntimeError('Global shortcut could not start')

            # Listen for audio device changes (AirPods, headphones, etc.)
            from Foundation import NSNotificationCenter
            NSNotificationCenter.defaultCenter().addObserverForName_object_queue_usingBlock_(
                "AVAudioEngineConfigurationChangeNotification",
                None,  # Observe from anywhere
                None,
                lambda notification: self._controls.put(('device_change', time.monotonic()))
            )

            print("[core_audio] Microphone idle; Fn hold or configured toggle to record.", flush=True)
        else:
            self.engine = None
            # Pre-create audio stream
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype='float32',
                callback=self._audio_callback
            )
            print("[core_audio] Audio stream prepared; microphone idle.", flush=True)

        self._control_thread = threading.Thread(target=self._run_controls, daemon=True)
        self._control_thread.start()

    def _configure_audio_tap(self):
        """Configure (or reconfigure) the audio tap for the current default input device."""
        try:
            if self.input_node:
                self.input_node.removeTapOnBus_(0)
        except Exception:
            pass

        self.input_node = self.engine.inputNode()
        self.hw_format = self.input_node.inputFormatForBus_(0)

        print(f"[core_audio] Configuring tap: {self.hw_format.sampleRate()} Hz, "
              f"{self.hw_format.channelCount()} ch", flush=True)

        self.resampler = av.AudioResampler(
            format='flt',
            layout='mono',
            rate=self.sample_rate,
        )

        self.input_node.installTapOnBus_bufferSize_format_block_(
            0, 1024, self.hw_format, self._capture_callback
        )
        self.engine.prepare()

    def _handle_config_change(self):
        """Handle audio hardware configuration change (device connected/disconnected)."""
        if self._closed or not self.is_recording:
            return
        # AVAudioEngine stops itself on a real hardware configuration change.
        # Ignore notifications caused by our own start/stop while it is running.
        if self.engine.isRunning():
            return
        print("[core_audio] Audio device change detected.", flush=True)
        if self._engine_running:
            self.engine.pause()
            self._engine_running = False
            print("[core_audio] Paused engine for reconfiguration.", flush=True)

        self._engine_running = False
        self._configure_audio_tap()

        if self._ensure_audio_running():
            print("[core_audio] Engine restarted with new device.", flush=True)


    def _ensure_audio_running(self):
        """Start the persistent input engine, retrying after device failures."""
        if self._engine_running:
            return True
        if sys.platform != 'darwin':
            self._stream.start()
            self._engine_running = True
            return True

        if self.input_node is None:
            self._configure_audio_tap()

        result = self.engine.startAndReturnError_(None)
        if isinstance(result, tuple):
            success, error = result
        else:
            success, error = bool(result), None
        self._engine_running = bool(success)
        if not success:
            print(f"[core_audio] Failed to start audio engine: {error}", flush=True)
        return self._engine_running

    def _clear_audio_queue(self):
        while not self.q.empty():
            try:
                self.q.get_nowait()
            except queue.Empty:
                break

    def _route_audio_chunk(self, chunk):
        audio = np.asarray(chunk, dtype=np.float32).reshape(-1)
        if audio.size == 0:
            return
        with self._audio_lock:
            self._ring_buffer.append(audio)
            if self.is_recording:
                rms = float(np.sqrt(np.mean(audio * audio)))
                # Latest scalar only: no raw audio or UI work crosses threads.
                self.input_level = min(1.0, max(0.0, (rms - .003) / .12)) if np.isfinite(rms) else 0.0
                self.q.put(audio)
            else:
                self.input_level = 0.0

    def _start_capture(self, include_pre_roll=True):
        """Open the microphone only after an explicit recording request."""
        if self.on_capture_request and not self.on_capture_request():
            return False
        self._cancelled = False
        self.released_at = None
        with self._audio_lock:
            self._clear_audio_queue()
            if include_pre_roll:
                pre_roll = self._ring_buffer.snapshot()
                if pre_roll.size:
                    self.q.put(pre_roll)
            self.is_recording = True
        if not self._ensure_audio_running():
            self._stop_capture()
            if self.on_cancel:
                self.on_cancel()
            return False
        return True

    def _stop_capture(self):
        with self._audio_lock:
            self.is_recording = False
            self.input_level = 0.0
            self._ring_buffer = AudioRingBuffer(self._ring_buffer.max_samples)
        # stop(), unlike a warm persistent engine, releases input hardware.
        self._engine_running = False
        if sys.platform == 'darwin':
            self.engine.stop()
            if self.input_node is not None:
                self.input_node.removeTapOnBus_(0)
            self.input_node = None
            self.hw_format = None
            self.resampler = None
        else:
            self._stream.stop()

    def toggle(self):
        self._controls.put(('toggle', time.monotonic()))

    def _toggle_capture(self, now):
        with self._control_lock:
            if self._closed or self.meeting_active:
                return
            if self.is_recording:
                self.released_at = time.perf_counter()
                self._mode = 'IDLE'
                self._stop_capture()
                self._stop_event.set()
            elif self._dictation_session_active and self._start_capture():
                self._mode = 'TOGGLED_IDLE'
                self._start_event.set()
            elif not self._dictation_session_active and self.on_busy:
                self.on_busy()

    def _run_controls(self):
        while True:
            action, timestamp = self._controls.get()
            if action == 'close' or self._closed:
                return
            try:
                if action == 'press':
                    self._handle_press(timestamp)
                elif action == 'release':
                    self._handle_release(timestamp)
                elif action == 'toggle':
                    self._toggle_capture(timestamp)
                elif action == 'cancel':
                    self.cancel()
                elif action == 'device_change':
                    with self._control_lock:
                        self._handle_config_change()
            except Exception as error:
                print(f'[core_audio] Control failed: {type(error).__name__}', flush=True)
                self.cancel()

    def _handle_press(self, now):
        with self._control_lock:
            self._handle_press_locked(now)

    def _handle_press_locked(self, now):
        if self._closed or self.meeting_active:
            return
        if not self._dictation_session_active:
            if self.on_busy:
                self.on_busy()
            return
        if self._mode == 'IDLE':
            if not self._start_capture():
                return
            self._mode = 'HOLDING'
            self._last_press = now
            self._start_event.set()
        elif self._mode == 'WAITING_FOR_DOUBLE':
            if now - self._last_release <= self._double_tap_threshold:
                self._mode = 'TOGGLED_PRESSED'
                self.released_at = None
                print("[core_audio] Double-tap: toggle mode active. Tap again to stop.", flush=True)
            else:
                # The timeout thread may still be scheduled. Finish the
                # existing short recording rather than clearing its buffer.
                self._stop_event.set()
                return
        elif self._mode == 'TOGGLED_IDLE':
            self._mode = 'IDLE'
            self.released_at = time.perf_counter()
            self._stop_capture()
            self._stop_event.set()

    def _handle_release(self, now):
        with self._control_lock:
            self._handle_release_locked(now)

    def _handle_release_locked(self, now):
        if self.meeting_active or not self._dictation_session_active:
            return
        if self._mode == 'HOLDING':
            self.released_at = time.perf_counter()
            if now - self._last_press <= self._double_tap_threshold:
                self._mode = 'WAITING_FOR_DOUBLE'
                self._last_release = now
                threading.Thread(target=self._check_double_tap_timeout,
                                 args=(now,), daemon=True).start()
            else:
                self._mode = 'IDLE'
                self._stop_capture()
                self._stop_event.set()
        elif self._mode == 'TOGGLED_PRESSED':
            self._mode = 'TOGGLED_IDLE'

    def _check_double_tap_timeout(self, released):
        time.sleep(self._double_tap_threshold)
        with self._control_lock:
            if self._mode == 'WAITING_FOR_DOUBLE' and self._last_release == released:
                self._mode = 'IDLE'
                self._stop_capture()
                self._stop_event.set()

    def cancel(self):
        with self._control_lock:
            if self.meeting_active:
                return False
            active = self._mode != 'IDLE' or self.is_recording
            if self.on_cancel:
                active = bool(self.on_cancel()) or active
            if active:
                self._cancelled = True
                self._mode = 'IDLE'
                self._stop_capture()
                if self._start_event.is_set():
                    self._stop_event.set()
            return active

    def close(self):
        self.cancel()
        self._closed = True
        self._controls.put(('close', time.monotonic()))
        self._start_event.set()
        self._stop_event.set()
        if sys.platform == 'darwin':
            self._stop_capture()
            if getattr(self, '_tap_loop', None):
                import Quartz
                Quartz.CFRunLoopStop(self._tap_loop)
        else:
            self._stream.stop()
            self._stream.close()

    def _run_event_tap(self):
        """Runs in a dedicated thread. Creates event tap and its own CFRunLoop."""
        import Quartz
        fn_down = False
        consumed_keys = set()

        def callback(proxy, type_, event, refcon):
            nonlocal fn_down
            now = time.monotonic()
            try:
                if type_ in (Quartz.kCGEventTapDisabledByTimeout, Quartz.kCGEventTapDisabledByUserInput):
                    Quartz.CGEventTapEnable(tap, True)
                    fn_down = False
                    consumed_keys.clear()
                    self._controls.put(('cancel', now))
                    return event
                if type_ == Quartz.kCGEventKeyUp:
                    keycode = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
                    if keycode in consumed_keys:
                        consumed_keys.discard(keycode)
                        return None
                if type_ == Quartz.kCGEventKeyDown:
                    keycode = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
                    # Own both edges of a reserved shortcut, including repeats.
                    if keycode in consumed_keys:
                        return None
                    if keycode == 53:
                        self._controls.put(('cancel', now))
                    elif not self.meeting_active and not self._closed:
                        flags = Quartz.CGEventGetFlags(event)
                        shortcut = self.get_toggle_shortcut()
                        command_or_option = flags & (Quartz.kCGEventFlagMaskCommand | Quartz.kCGEventFlagMaskAlternate)
                        control = bool(flags & Quartz.kCGEventFlagMaskControl)
                        shift = bool(flags & Quartz.kCGEventFlagMaskShift)
                        matches = False
                        if shortcut == 'section' and not command_or_option and not control:
                            _, characters = Quartz.CGEventKeyboardGetUnicodeString(event, 4, None, None)
                            matches = characters == '§'
                        elif shortcut == 'ctrl_shift_space':
                            matches = keycode == 49 and control and shift and not command_or_option
                        if matches:
                            consumed_keys.add(keycode)
                            if not Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventAutorepeat):
                                self._controls.put(('toggle', now))
                            return None
                if self.hotkey == 'fn' and type_ == Quartz.kCGEventFlagsChanged:
                    flags = Quartz.CGEventGetFlags(event)
                    pressed = bool(flags & Quartz.kCGEventFlagMaskSecondaryFn)
                    if pressed != fn_down:
                        fn_down = pressed
                        self._controls.put(('press' if pressed else 'release', now))
            except Exception as e:
                print(f"[core_audio] Event tap error: {e}", flush=True)
            return event

        tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            # An Accessibility-authorized tap. Consume only the selected toggle
            # shortcut; all other keys keep their normal behavior.
            # A listen-only keyboard tap instead requires Input Monitoring.
            Quartz.kCGEventTapOptionDefault,
            Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged) | Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown) | Quartz.CGEventMaskBit(Quartz.kCGEventKeyUp),
            callback,
            None
        )

        if not tap:
            self._tap_error = 'Global shortcut unavailable'
            self._tap_ready.set()
            print("[core_audio] Failed to create event tap. Check accessibility permissions.", flush=True)
            return

        source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
        loop = Quartz.CFRunLoopGetCurrent()
        self._tap_loop = loop
        if self._closed:
            return
        Quartz.CFRunLoopAddSource(loop, source, Quartz.kCFRunLoopCommonModes)
        Quartz.CGEventTapEnable(tap, True)
        self._tap_ready.set()
        print("[core_audio] Fn key event tap active.", flush=True)

        Quartz.CFRunLoopRun()

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            print(status, flush=True)
        self._route_audio_chunk(indata.copy())

    def start_continuous(self):
        """Start continuous recording for meeting mode. Disables Fn-key dictation."""
        self.meeting_active = True
        with self._audio_lock:
            self._clear_audio_queue()
            self.is_recording = True
        if not self._ensure_audio_running():
            self._stop_capture()
            self.meeting_active = False
            raise RuntimeError('Microphone could not start')
        print("[core_audio] Continuous recording started (meeting mode).", flush=True)

    def stop_continuous(self):
        """Stop continuous recording and re-enable Fn-key dictation."""
        self._stop_capture()
        self.meeting_active = False
        print("[core_audio] Continuous recording stopped.", flush=True)

    def drain_audio_queue(self) -> np.ndarray:
        """Drain all queued audio chunks and return as a single numpy array."""
        with self._audio_lock:
            chunks = []
            while not self.q.empty():
                chunks.append(self.q.get())
        if not chunks:
            return np.array([], dtype='float32')
        return np.concatenate(chunks, axis=0).flatten()

    def record_while_pressed(self) -> np.ndarray:
        """Blocks until Fn pressed, records audio, returns buffer on release."""
        with self._control_lock:
            self._start_event.clear()
            self._stop_event.clear()
            self._mode = 'IDLE'
            self._dictation_session_active = True

        print("[core_audio] Ready. Hold Fn to dictate, double-tap to toggle.", flush=True)

        # Block until fn pressed (stream already started by _handle_press)
        self._start_event.wait()

        if self._closed:
            return np.array([], dtype='float32')

        if self.on_record_start:
            self.on_record_start()
        print("[core_audio] Recording...", flush=True)

        # Block until fn released, check for keyboard interrupt
        try:
            while not self._stop_event.is_set():
                self._stop_event.wait(0.1)
        except KeyboardInterrupt:
            self._stop_event.set()

        with self._control_lock:
            self._stop_capture()
            self._dictation_session_active = False
            
        if self.on_record_stop and not self._cancelled:
            self.on_record_stop()
        print("[core_audio] Stopped.", flush=True)

        with self._audio_lock:
            chunks = []
            while not self.q.empty():
                chunks.append(self.q.get())

        if self._cancelled or not chunks:
            return np.array([], dtype='float32')

        return np.concatenate(chunks, axis=0).flatten()
