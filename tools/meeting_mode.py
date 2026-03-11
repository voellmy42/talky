import os
import threading
import time
import subprocess
from datetime import datetime


MEETINGS_DIR = os.path.expanduser("~/Documents/Talky/Meetings")


class MeetingSession:
    """Manages a single meeting recording session."""

    def __init__(self, audio_tool, stt_tool, summarizer, language="en",
                 on_chunk=None, on_summarizing=None, on_done=None, on_error=None):
        """
        audio_tool: AudioCaptureTool instance (for start/stop continuous, drain queue)
        stt_tool: STTTool instance (for transcribing chunks)
        summarizer: MeetingSummarizer instance
        language: BCP-47 code
        on_chunk(chunk_count): called after each chunk is transcribed
        on_summarizing(): called when summarization starts
        on_done(file_path): called when meeting notes are saved
        on_error(msg): called on error
        """
        self._audio = audio_tool
        self._stt = stt_tool
        self._summarizer = summarizer
        self._language = language
        self._on_chunk = on_chunk or (lambda n: None)
        self._on_summarizing = on_summarizing or (lambda: None)
        self._on_done = on_done or (lambda p: None)
        self._on_error = on_error or (lambda m: None)

        self._chunks = []
        self._stop_event = threading.Event()
        self._thread = None
        self._start_time = None

    @property
    def elapsed_seconds(self) -> float:
        if self._start_time is None:
            return 0.0
        return time.time() - self._start_time

    def start(self):
        """Begin recording and chunk processing."""
        self._chunks = []
        self._stop_event.clear()
        self._start_time = time.time()
        self._audio.start_continuous()
        self._thread = threading.Thread(target=self._chunk_loop, daemon=True)
        self._thread.start()
        print("[meeting] Session started.", flush=True)

    def stop(self):
        """Stop recording, process remaining audio, summarize, and save."""
        print("[meeting] Stopping session...", flush=True)
        self._stop_event.set()
        self._audio.stop_continuous()

        # Process any remaining audio in the queue
        self._transcribe_queued()

        if self._thread:
            self._thread.join(timeout=5)

        if not self._chunks:
            self._on_error("No speech detected during meeting.")
            return

        # Summarize
        self._on_summarizing()
        full_transcript = "\n".join(self._chunks)
        print(f"[meeting] Full transcript ({len(self._chunks)} chunks, {len(full_transcript)} chars)", flush=True)

        summary = self._summarizer.summarize(full_transcript, language=self._language)

        # Save to file
        file_path = self._save(summary)
        print(f"[meeting] Saved to {file_path}", flush=True)

        # Open in default editor
        try:
            subprocess.run(["open", file_path])
        except Exception as e:
            print(f"[meeting] Could not open file: {e}", flush=True)

        self._on_done(file_path)

    def _chunk_loop(self):
        """Runs in background thread. Every ~30s, drains audio and transcribes."""
        while not self._stop_event.is_set():
            self._stop_event.wait(30)
            if self._stop_event.is_set():
                break
            self._transcribe_queued()

    def _transcribe_queued(self):
        """Drain the audio queue and transcribe whatever is there."""
        audio = self._audio.drain_audio_queue()
        if len(audio) == 0:
            return
        text = self._stt.transcribe(audio, language=self._language)
        if text:
            self._chunks.append(text)
            self._on_chunk(len(self._chunks))
            print(f"[meeting] Chunk {len(self._chunks)}: '{text[:80]}...'", flush=True)

    def _save(self, content: str) -> str:
        """Save meeting notes to ~/Documents/Talky/Meetings/."""
        os.makedirs(MEETINGS_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename = f"{timestamp}_meeting.md"
        file_path = os.path.join(MEETINGS_DIR, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return file_path
