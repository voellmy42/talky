from faster_whisper import WhisperModel
import numpy as np

class STTTool:
    def __init__(self, model_size="small", compute_type="int8"):
        """
        Preloads the faster-whisper model into memory.
        Using 'small' and 'int8' for good accuracy with reasonable speed on CPU.
        """
        print(f"[core_stt] Loading WhisperModel '{model_size}' into memory...")
        self.model = WhisperModel(model_size, device="cpu", compute_type=compute_type)
        print("[core_stt] Model loaded.")

    def transcribe(self, audio_buffer: np.ndarray, language: str = "en") -> str:
        """
        Transcribes a 1D float32 numpy array into raw text.
        language: BCP-47 code ('de' or 'en').
        """
        if audio_buffer is None or len(audio_buffer) == 0:
            return ""
            
        print(f"[core_stt] Transcribing audio buffer (lang={language})...")
        segments, info = self.model.transcribe(
            audio_buffer,
            language=language,
            task="transcribe",
            beam_size=5,
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
