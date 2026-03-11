import mlx_whisper
import numpy as np

class STTTool:
    def __init__(self, model_size="small", compute_type="int8"):
        """
        Initializes STT via MLX-Whisper for Apple Silicon GPU acceleration.
        Maps the requested model size to an mlx-community repo.
        """
        self.model_size = model_size
        # Map generic "small" to the MLX weights repo on Hugging Face
        self.hf_repo = f"mlx-community/whisper-{model_size}-mlx-8bit" if compute_type == "int8" else f"mlx-community/whisper-{model_size}-mlx"
        print(f"[core_stt] Will use MLX-Whisper repo '{self.hf_repo}'.")

    def transcribe(self, audio_buffer: np.ndarray, language: str = "en", is_warmup: bool = False) -> str:
        """
        Transcribes a 1D float32 numpy array into raw text.
        language: BCP-47 code ('de' or 'en').
        """
        if audio_buffer is None or len(audio_buffer) == 0:
            return ""
            
        if not is_warmup:
            # Check for silence to prevent Whisper hallucination and save compute
            rms = np.sqrt(np.mean(audio_buffer**2))
            if rms < 0.001:
                print(f"[core_stt] Audio too quiet (RMS: {rms:.4f}), skipping...", flush=True)
                return ""
            print(f"[core_stt] Transcribing audio buffer (lang={language}) via MLX GPU...", flush=True)
        
        # MLX whisper transcribe
        result = mlx_whisper.transcribe(
            audio_buffer,
            path_or_hf_repo=self.hf_repo,
            language=language,
            initial_prompt="Hello, this is a dictated sentence.",
            condition_on_previous_text=False
        )
        
        transcription = result.get("text", "")
        if not is_warmup:
            print(f"[core_stt] Raw output: '{transcription}'")
            return transcription.strip()
        else:
            print("[core_stt] MLX GPU compilation complete.", flush=True)
            return ""

if __name__ == "__main__":
    # Test execution with dummy empty array
    stt = STTTool(compute_type="fp16") # test full precision for speed
    dummy_audio = np.zeros(16000, dtype=np.float32) # 1 second of silence
    res = stt.transcribe(dummy_audio)
    print(f"Result for silence: '{res}'")
