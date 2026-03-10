"""
Synthesises short audio chimes and plays them without blocking.
No external .wav files needed — pure numpy + sounddevice.
"""

import numpy as np
import sounddevice as sd
import threading

# Pre-generate chime buffers at import time
_SR = 44100

def _make_chime(freq: float, duration: float = 0.12, volume: float = 0.25) -> np.ndarray:
    """Generate a soft sine-wave chime with a fast exponential decay."""
    t = np.linspace(0, duration, int(_SR * duration), dtype=np.float32)
    envelope = np.exp(-t * 25)  # fast fade-out
    return (np.sin(2 * np.pi * freq * t) * envelope * volume).astype(np.float32)

# Two-tone ascending = start, single descending = stop
_START_TONE = np.concatenate([
    _make_chime(880, 0.08, 0.20),
    _make_chime(1320, 0.10, 0.22),
])

_STOP_TONE = _make_chime(660, 0.12, 0.18)


def play_start() -> None:
    """Non-blocking start chime (ascending two-tone)."""
    threading.Thread(target=lambda: sd.play(_START_TONE, _SR, blocking=True), daemon=True).start()


def play_stop() -> None:
    """Non-blocking stop chime (single descending tone)."""
    threading.Thread(target=lambda: sd.play(_STOP_TONE, _SR, blocking=True), daemon=True).start()
