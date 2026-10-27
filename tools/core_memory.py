"""Low available-memory admission/eviction; no MLX import and no hardware capture."""
import threading

GIB = 1024 ** 3


def available_memory():
    import psutil
    return psutil.virtual_memory().available


class MemoryMonitor:
    def __init__(self, on_change, probe=available_memory, interval=10):
        self.on_change, self.probe, self.interval = on_change, probe, interval
        self.low = False
        self._stop = threading.Event()
        self._thread = None

    def sample(self):
        try:
            available = self.probe()
        except (OSError, RuntimeError):
            return  # Unsupported probes must not break dictation.
        # Hysteresis avoids immediate reload/eviction loops around one threshold.
        low = available < (2 * GIB if self.low else GIB)
        if low != self.low:
            self.low = low
            self.on_change(low)

    def start(self):
        if self._thread is None:
            self.sample()
            self._thread = threading.Thread(target=self._run, daemon=True, name='talky-memory')
            self._thread.start()

    def _run(self):
        while not self._stop.wait(self.interval):
            self.sample()

    def close(self):
        self._stop.set()
