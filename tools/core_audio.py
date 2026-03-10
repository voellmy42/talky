import sounddevice as sd
import numpy as np
import keyboard
import threading
import queue

class AudioCaptureTool:
    def __init__(self, sample_rate=16000, hotkey='f8'):
        self.sample_rate = sample_rate
        self.hotkey = hotkey
        self.q = queue.Queue()
        self.is_recording = False
        
    def _audio_callback(self, indata, frames, time, status):
        """This is called (from a separate thread) for each audio block."""
        if status:
            print(status, flush=True)
        if self.is_recording:
            # Copy data so the array doesn't get overwritten
            self.q.put(indata.copy())

    def record_while_pressed(self) -> np.ndarray:
        """
        Blocks until the hotkey is pressed, records into memory while held,
        and returns the unified float32 numpy array upon release.
        """
        print(f"[core_audio] Ready. Press and hold '{self.hotkey}' to dictate.", flush=True)
        keyboard.wait(self.hotkey) # Blocks until key down
        
        self.is_recording = True
        print(f"[core_audio] Recording started...", flush=True)
        
        # Start the stream
        stream = sd.InputStream(
            samplerate=self.sample_rate, 
            channels=1, 
            dtype='float32', 
            callback=self._audio_callback
        )
        
        with stream:
            # Wait until the hotkey is released
            while keyboard.is_pressed(self.hotkey):
                sd.sleep(10) # Small sleep to prevent CPU spinning
        
        self.is_recording = False
        print(f"[core_audio] Recording stopped.", flush=True)
        
        # Collect all chunks from the queue
        chunks = []
        while not self.q.empty():
            chunks.append(self.q.get())
            
        if not chunks:
            print("[core_audio] Warning: No audio data captured.")
            return np.array([], dtype='float32')

        # Concatenate into one continuous float32 array
        audio_buffer = np.concatenate(chunks, axis=0).flatten()
        return audio_buffer

if __name__ == "__main__":
    # Test execution
    capture = AudioCaptureTool()
    buffer = capture.record_while_pressed()
    print(f"Captured {len(buffer)} samples at {capture.sample_rate}Hz.")
