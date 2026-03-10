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
        self.system_prompt = (
            "You are a strict dictation formatting engine. "
            "Your ONLY job is to take the user's spoken text, remove filler words (um, uh, like), "
            "and fix obvious grammar/punctuation errors. "
            "DO NOT add new information, DO NOT summarize, DO NOT answer questions in the text. "
            "Output ONLY the corrected text and nothing else whatsoever. Do not prefix with 'Here is the text:'"
        )
        print(f"[core_llm] Initialized with local Ollama model: '{self.model}' at {self.host}")

    def format_text(self, raw_transcription: str) -> str:
        """
        Sends the raw string to Ollama and returns the cleaned result.
        If Ollama is offline or fails, it returns the raw string as a fallback.
        """
        if not raw_transcription.strip():
            return ""

        print("[core_llm] Sending text to Ollama for formatting...")
        payload = {
            "model": self.model,
            "system": self.system_prompt,
            "prompt": raw_transcription,
            "stream": False,
            "keep_alive": "5m" # Keep model loaded in memory for 5 minutes after request
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
    cleaned = llm.format_text(raw)
    print("Cleaned: ", cleaned)
