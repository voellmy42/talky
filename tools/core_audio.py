import sounddevice as sd
import numpy as np
import threading
import queue
import time
import sys

if sys.platform == 'darwin':
    import AVFoundation
    import av


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
        self.meeting_active = False

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
                if self.is_recording:
                    try:
                        # Use local references to avoid race conditions during re-config
                        resampler = self.resampler
                        hw_format = self.hw_format
                        if not resampler or not hw_format:
                            return

                        frames = buffer.frameLength()
                        data_ptr = buffer.floatChannelData()
                        if data_ptr:
                            ch0_data = data_ptr[0]
                            audio_np = np.array(ch0_data[:frames], dtype=np.float32)

                            frame = av.AudioFrame.from_ndarray(audio_np.reshape(1, -1), format='flt', layout='mono')
                            frame.sample_rate = int(hw_format.sampleRate())

                            resampled_frames = resampler.resample(frame)
                            if resampled_frames:
                                resampled_np = resampled_frames[0].to_ndarray().flatten()
                                self.q.put(resampled_np.reshape(-1, 1))
                    except Exception as e:
                        print(f"[core_audio] Callback error: {e}", flush=True)

            self._capture_callback = capture_callback
            self._configure_audio_tap()

            # Listen for audio device changes (AirPods, headphones, etc.)
            from Foundation import NSNotificationCenter
            NSNotificationCenter.defaultCenter().addObserverForName_object_queue_usingBlock_(
                "AVAudioEngineConfigurationChangeNotification",
                None,  # Observe from anywhere
                None,
                lambda notification: self._handle_config_change()
            )

            print("[core_audio] AVFoundation Audio engine pre-created (not yet active).", flush=True)
        else:
            self.engine = None
            # Pre-create audio stream
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype='float32',
                callback=self._audio_callback
            )
            print("[core_audio] Audio stream pre-created (not yet active).", flush=True)

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
        print("[core_audio] Audio device change detected.", flush=True)
        was_recording = self.is_recording

        if was_recording:
            self.engine.pause()
            print("[core_audio] Paused engine for reconfiguration.", flush=True)

        self._configure_audio_tap()

        if was_recording:
            success, error = self.engine.startAndReturnError_(None)
            if success:
                print("[core_audio] Engine restarted with new device.", flush=True)
            else:
                print(f"[core_audio] Failed to restart engine: {error}", flush=True)


    def _start_capture(self):
        """Start audio capture immediately (called from event tap thread)."""
        self.is_recording = True
        if sys.platform == 'darwin':
            self.engine.startAndReturnError_(None)
        else:
            self._stream.start()

    def _handle_press(self, now):
        if self.meeting_active:
            return
        if self._mode == 'IDLE':
            self._mode = 'HOLDING'
            self._last_press = now
            self._start_capture()
            self._start_event.set()
        elif self._mode == 'WAITING_FOR_DOUBLE':
            if now - self._last_release <= self._double_tap_threshold:
                self._mode = 'TOGGLED_PRESSED'
                print("[core_audio] Double-tap: toggle mode active. Tap again to stop.", flush=True)
            else:
                self._mode = 'HOLDING'
                self._last_press = now
                self._start_capture()
                self._start_event.set()
        elif self._mode == 'TOGGLED_IDLE':
            self._mode = 'IDLE'
            self._stop_event.set()

    def _handle_release(self, now):
        if self.meeting_active:
            return
        if self._mode == 'HOLDING':
            if now - self._last_press <= self._double_tap_threshold:
                self._mode = 'WAITING_FOR_DOUBLE'
                self._last_release = now
                threading.Thread(target=self._check_double_tap_timeout, daemon=True).start()
            else:
                self._mode = 'IDLE'
                self._stop_event.set()
        elif self._mode == 'TOGGLED_PRESSED':
            self._mode = 'TOGGLED_IDLE'

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

    def start_continuous(self):
        """Start continuous recording for meeting mode. Disables Fn-key dictation."""
        self.meeting_active = True
        while not self.q.empty():
            self.q.get()
        self.is_recording = True
        if sys.platform == 'darwin':
            self.engine.startAndReturnError_(None)
        else:
            self._stream.start()
        print("[core_audio] Continuous recording started (meeting mode).", flush=True)

    def stop_continuous(self):
        """Stop continuous recording and re-enable Fn-key dictation."""
        self.is_recording = False
        if sys.platform == 'darwin':
            self.engine.pause()
        else:
            self._stream.stop()
        self.meeting_active = False
        print("[core_audio] Continuous recording stopped.", flush=True)

    def drain_audio_queue(self) -> np.ndarray:
        """Drain all queued audio chunks and return as a single numpy array."""
        chunks = []
        while not self.q.empty():
            chunks.append(self.q.get())
        if not chunks:
            return np.array([], dtype='float32')
        return np.concatenate(chunks, axis=0).flatten()

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

        # Block until fn released, check for keyboard interrupt
        try:
            while not self._stop_event.is_set():
                self._stop_event.wait(0.1)
        except KeyboardInterrupt:
            self._stop_event.set()

        self.is_recording = False
        
        if sys.platform == 'darwin':
            self.engine.pause()
        else:
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
