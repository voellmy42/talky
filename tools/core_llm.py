import requests
import json

class LLMFormatter:
    def __init__(self, host="http://localhost:11434", model="qwen2.5:3b"):
        """
        Connects to a local Ollama instance.
        Defaults to qwen2.5:3b running locally.
        """
        self.host = f"{host}/api/generate"
        self.model = model
        self._lang_names = {"de": "German", "en": "English"}
        print(f"[core_llm] Initialized with local Ollama model: '{self.model}' at {self.host}")

    def _build_system_prompt(self, language: str) -> str:
        lang_name = self._lang_names.get(language, "German")
        fillers = {"de": "ähm, halt, quasi, genre, also", "en": "um, uh, like, you know, so, basically"}
        filler_list = fillers.get(language, fillers["de"])
        return (
            f"You are a strict dictation formatting engine. "
            f"The user is dictating in {lang_name}. "
            f"Your output MUST be in {lang_name}. Rules:\n"
            f"1. REMOVE filler words ({filler_list}).\n"
            f"2. FIX obvious grammar, punctuation, and capitalisation errors.\n"
            f"3. DO NOT translate to any other language.\n"
            f"4. DO NOT rephrase, summarise, or add any new information.\n"
            f"5. DO NOT answer questions contained in the text.\n"
            f"6. Output ONLY the corrected text. No preamble, no explanation."
        )

    def format_text(self, raw_transcription: str, language: str = "en") -> str:
        """
        Sends the raw string to Ollama and returns the cleaned result.
        If Ollama is offline or fails, it returns the raw string as a fallback.
        """
        if not raw_transcription.strip():
            return ""

        print("[core_llm] Sending text to Ollama for formatting...")
        payload = {
            "model": self.model,
            "system": self._build_system_prompt(language),
            "prompt": raw_transcription,
            "stream": False,
            "keep_alive": "5m", # Keep model loaded in memory for 5 minutes after request
            "options": {
                "temperature": 0.0,
                "num_predict": 512
            }
        }

        try:
            # First request might take time if model is loading
            response = requests.post(self.host, json=payload, timeout=60.0)
            response.raise_for_status()
            result = response.json().get("response", "")
            cleaned = result.strip()
            print(f"[core_llm] Formatted output: '{cleaned}'")
            return cleaned
        except Exception as e:
            print(f"[core_llm] Warning: Ollama formatting failed ({e}). Returning raw transcription.")
            return raw_transcription.strip()

if __name__ == "__main__":
    # Test execution
    llm = LLMFormatter()
    raw = "um, so, like, I was going to the store, you know, to buy some milk."
    print("Raw: ", raw)
    cleaned = llm.format_text(raw, language="en")
    print("Cleaned: ", cleaned)
