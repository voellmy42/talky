import mlx_whisper
import numpy as np

# Language-matched initial prompts prevent hallucination when the prompt
# language doesn't match the transcription language.
_INITIAL_PROMPTS = {
    "en": "Hello, this is a dictated sentence.",
    "de": "Hallo, das ist ein diktierter Satz.",
    "fr": "Bonjour, ceci est une phrase dictée.",
}


class STTTool:
    def __init__(self, model_size="small", compute_type="int8"):
        """
        Initializes STT via MLX-Whisper for Apple Silicon GPU acceleration.
        Maps the requested model size to an mlx-community repo.
        """
        self.model_size = model_size
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
            rms = np.sqrt(np.mean(audio_buffer**2))
            if rms < 0.01:
                print(f"[core_stt] Audio too quiet (RMS: {rms:.4f}), skipping...", flush=True)
                return ""
            print(f"[core_stt] Transcribing audio buffer (lang={language}) via MLX GPU...", flush=True)

        result = mlx_whisper.transcribe(
            audio_buffer,
            path_or_hf_repo=self.hf_repo,
            language=language,
            initial_prompt=_INITIAL_PROMPTS.get(language),
            condition_on_previous_text=False,
            temperature=0.0,
            hallucination_silence_threshold=2.0,
        )

        transcription = result.get("text", "")
        if not is_warmup:
            print(f"[core_stt] Raw output: '{transcription}'")
            return transcription.strip()
        else:
            print("[core_stt] MLX GPU compilation complete.", flush=True)
            return ""

if __name__ == "__main__":
    stt = STTTool(model_size="small", compute_type="int8")
    # Warmup
    stt.transcribe(np.zeros(16000, dtype=np.float32), is_warmup=True)
    # Silence should be skipped
    res = stt.transcribe(np.zeros(16000, dtype=np.float32))
    print(f"Result for silence: '{res}'")
    # Noise should be skipped (RMS ~0.01)
    noise = np.random.randn(16000).astype(np.float32) * 0.005
    res = stt.transcribe(noise, language="de")
    print(f"Result for noise (de): '{res}'")
