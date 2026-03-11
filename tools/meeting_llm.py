import requests
from datetime import datetime


class MeetingSummarizer:
    def __init__(self, host="http://localhost:11434", model="qwen2.5:3b"):
        self.host = f"{host}/api/generate"
        self.model = model
        self._lang_names = {"de": "German", "en": "English"}
        print(f"[meeting_llm] Initialized with model: '{self.model}'")

    def _build_system_prompt(self, language: str) -> str:
        lang_name = self._lang_names.get(language, "English")
        today = datetime.now().strftime("%B %d, %Y")
        return (
            f"You are a meeting notes assistant. "
            f"The user will provide a raw transcript of a meeting or spoken thoughts in {lang_name}. "
            f"Your output MUST be in {lang_name}. Rules:\n"
            f"1. Write a Markdown document with this exact structure:\n"
            f"   # Meeting Notes — {today}\n"
            f"   ## Summary\n"
            f"   [2-3 sentences summarising what was discussed]\n"
            f"   ## Key Points\n"
            f"   - [Bullet points organised by topic/theme]\n"
            f"   ## Action Items\n"
            f"   - [ ] [Any action items, tasks, or next steps mentioned]\n"
            f"2. If no action items are found, write '- No action items identified.'\n"
            f"3. Organise key points by topic/theme, not chronologically.\n"
            f"4. Remove filler words, repetitions, and tangents.\n"
            f"5. Keep the summary concise but preserve all substantive ideas.\n"
            f"6. DO NOT invent information not present in the transcript.\n"
            f"7. Output ONLY the Markdown document. No preamble."
        )

    def summarize(self, full_transcript: str, language: str = "en") -> str:
        """Send the full meeting transcript to Ollama and return structured notes."""
        if not full_transcript.strip():
            return ""

        print("[meeting_llm] Sending transcript to Ollama for summarization...", flush=True)
        payload = {
            "model": self.model,
            "system": self._build_system_prompt(language),
            "prompt": f"Meeting Transcript:\n\n{full_transcript}",
            "stream": False,
            "keep_alive": "5m",
            "options": {
                "temperature": 0.3,
                "num_predict": 4096
            }
        }

        try:
            response = requests.post(self.host, json=payload, timeout=120.0)
            response.raise_for_status()
            result = response.json().get("response", "")
            print("[meeting_llm] Summarization complete.", flush=True)
            return result.strip()
        except Exception as e:
            print(f"[meeting_llm] Summarization failed ({e}). Returning raw transcript.", flush=True)
            return f"# Meeting Transcript — Raw\n\n{full_transcript}"
