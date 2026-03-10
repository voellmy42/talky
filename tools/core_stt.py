from faster_whisper import WhisperModel
import numpy as np

class STTTool:
    def __init__(self, model_size="base", compute_type="int8"):
        """
        Preloads the faster-whisper model into memory.
        Using 'base' and 'int8' for good accuracy with reasonable speed on CPU.
        """
        print(f"[core_stt] Loading WhisperModel '{model_size}' into memory...")
        self.model = WhisperModel(model_size, device="cpu", compute_type=compute_type)
        print("[core_stt] Model loaded.")

    def transcribe(self, audio_buffer: np.ndarray) -> str:
        """
        Transcribes a 1D float32 numpy array into raw text.
        """
        if audio_buffer is None or len(audio_buffer) == 0:
            return ""
            
        print("[core_stt] Transcribing audio buffer...")
        # faster-whisper's transcribe method accepts a numpy array directly if it's 16kHz float32
        # language=None lets Whisper auto-detect (de/en/fr/etc.)
        segments, info = self.model.transcribe(
            audio_buffer,
            language=None,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=300)
        )
        
        # Generator evaluation to reconstruct the full string
        transcription = "".join([segment.text for segment in segments])
        print(f"[core_stt] Raw output: '{transcription}'")
        return transcription.strip()

if __name__ == "__main__":
    # Test execution with dummy empty array
    stt = STTTool()
    dummy_audio = np.zeros(16000, dtype=np.float32) # 1 second of silence
    result = stt.transcribe(dummy_audio)
    print(f"Result for silence: '{result}'")
