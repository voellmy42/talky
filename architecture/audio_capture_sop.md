# Audio Capture Standard Operating Procedure (SOP)

## Purpose
Capture raw audio clearly from the user's default microphone into memory while a designated global hotkey is pressed and held, stopping when the hotkey is released.

## Tool Execution Context
- **Script path**: `tools/core_audio.py`
- **Dependencies**: `AVFoundation`, `PyAV`, `Quartz`, `sounddevice`, `numpy`

## Input Data Shape
- Real-time hardware microphone signal (e.g., sample rate 16000).
- macOS global Fn-key state (PRESSED -> RELEASED).

## Output Data Shape
- Returns a 1D `numpy.ndarray` (`audio_buffer`) of `float32` representing the full recording segment safely encoded.

## Execution Rules
- **No Disk Writing**: The recording must be held in memory entirely. Do not yield a temporary `.wav` file to `.tmp/` unless debugging necessitates it.
- **Latency Requirement**: The recording must start immediately upon KEYDOWN and end immediately upon KEYUP to minimize user wait time.
- **Idle Microphone**: Keep models loaded but do not start input hardware at launch. Open the microphone on a recording request; stop the engine and remove its input tap on stop/cancel.
- **Pre-Roll**: Disabled by default so idle Talky does not keep the microphone active. Signal capture readiness with the start chime.
- **Hotkeys**: Fn hold/double-tap, configurable §/Control+Shift+Space toggle, and menu start/finish. Use an Accessibility-authorized event tap. Consume only both edges/repeats of the selected toggle; forward unrelated keys and Escape normally. Match § using event Unicode, not a physical keycode. The event callback only queues controls; focus queries and audio startup run on a separate worker. Shortcut settings apply immediately without a rebuild.
- **Sample Rate**: Resample the default hardware input to mono 16kHz float32 for Whisper.
- **Mode Isolation**: During processing, report busy on new Fn presses. Ignore dictation hotkeys in Meeting Mode. Escape/menu cancellation must still invalidate a pending dictation result during processing.
- **Session Identity**: Capture destination, language and formatting mode at recording start, not after recognition completes.
- **Cancellation**: Stop capture and discard its buffer. Running inference may finish, but its invalidated result must never be delivered. Do not start another inference concurrently.
- **Release Timing**: Record the release/stop timestamp before any double-tap timeout so latency includes that delay.
- **Device Changes**: Reconfigure after a hardware change during recording. Device notifications must not open the microphone while idle.

## Error States & Handling
- *Microphone unavailable / Permissions denied* -> Fail fast, log error to console, abort pipeline gracefully.
- *Keybinding clash* -> Log warning and ensure graceful exit if hotkey is completely overridden.
