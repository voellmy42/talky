# Audio Capture Standard Operating Procedure (SOP)

## Purpose
Capture raw audio clearly from the user's default microphone into memory while a designated global hotkey is pressed and held, stopping when the hotkey is released.

## Tool Execution Context
- **Script path**: `tools/core_audio.py`
- **Dependencies**: `sounddevice`, `numpy`, `keyboard`

## Input Data Shape
- Real-time hardware microphone signal (e.g., sample rate 16000).
- Windows global OS hotkey state (PRESSED -> RELEASED).

## Output Data Shape
- Returns a 1D `numpy.ndarray` (`audio_buffer`) of `float32` representing the full recording segment safely encoded.

## Execution Rules
- **No Disk Writing**: The recording must be held in memory entirely. Do not yield a temporary `.wav` file to `.tmp/` unless debugging necessitates it.
- **Latency Requirement**: The recording must start immediately upon KEYDOWN and end immediately upon KEYUP to minimize user wait time.
- **Sample Rate**: Dictated by `faster-whisper`'s optimal input setting (usually 16kHz).

## Error States & Handling
- *Microphone unavailable / Permissions denied* -> Fail fast, log error to console, abort pipeline gracefully.
- *Keybinding clash* -> Log warning and ensure graceful exit if hotkey is completely overridden.
