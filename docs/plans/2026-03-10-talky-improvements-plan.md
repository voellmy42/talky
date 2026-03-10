# Talky Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix unwanted translation, slow fn-key response, and lost first words in the Talky voice dictation app.

**Architecture:** Two independent changes: (1) pass language code to the LLM formatter so it outputs in the correct language, (2) keep the audio stream always-on with a 500ms ring buffer so recording starts instantly and captures pre-press audio.

**Tech Stack:** Python, faster-whisper, Ollama, sounddevice, numpy, collections.deque

---

### Task 1: Language-aware LLM formatter

**Files:**
- Modify: `tools/core_llm.py` (lines 12-22 system_prompt, line 25 format_text signature, lines 34-37 payload)

**Step 1: Update `format_text` to accept a `language` parameter**

Replace the static `self.system_prompt` with a method that builds the prompt dynamically.
Replace `format_text(self, raw_transcription)` with `format_text(self, raw_transcription, language="de")`.

In `tools/core_llm.py`, make these changes:

1. Remove the static `self.system_prompt` from `__init__` (lines 12-22). Replace with a `_build_system_prompt(language)` method.

2. Change the `format_text` signature and payload:

```python
# In __init__, remove self.system_prompt entirely. Replace with:
self._lang_names = {"de": "German", "en": "English"}

# Add this new method:
def _build_system_prompt(self, language: str) -> str:
    lang_name = self._lang_names.get(language, "German")
    return (
        f"You are a strict dictation formatting engine. "
        f"The user is dictating in {lang_name}. "
        f"Your output MUST be in {lang_name}. Rules:\n"
        f"1. REMOVE filler words ({{'de': 'ähm, halt, quasi, genre, also', 'en': 'um, uh, like, you know, so, basically'}[language]}).\n"
        f"2. FIX obvious grammar, punctuation, and capitalisation errors.\n"
        f"3. DO NOT translate to any other language.\n"
        f"4. DO NOT rephrase, summarise, or add any new information.\n"
        f"5. DO NOT answer questions contained in the text.\n"
        f"6. Output ONLY the corrected text. No preamble, no explanation."
    )

# Change format_text signature:
def format_text(self, raw_transcription: str, language: str = "de") -> str:

# In the payload dict, change "system" value:
"system": self._build_system_prompt(language),
```

**Step 2: Verify the `__main__` test block still works**

Update the test block at the bottom to pass a language:
```python
cleaned = llm.format_text(raw, language="en")
```

**Step 3: Commit**

```bash
git add tools/core_llm.py
git commit -m "fix: pass language to LLM formatter to prevent translation"
```

---

### Task 2: Wire language through the pipeline

**Files:**
- Modify: `main.py` (line 50)

**Step 1: Pass `lang` to `format_text`**

Change line 50 from:
```python
cleaned_text = llm_tool.format_text(raw_text)
```
to:
```python
cleaned_text = llm_tool.format_text(raw_text, language=lang)
```

(`lang` is already defined on line 43.)

**Step 2: Commit**

```bash
git add main.py
git commit -m "fix: pass selected language from pipeline to LLM formatter"
```

---

### Task 3: Always-on audio stream with ring buffer

**Files:**
- Modify: `tools/core_audio.py` (major refactor of `__init__`, `_audio_callback`, `record_while_pressed`)

**Step 1: Add `collections.deque` import**

Add at top of file:
```python
from collections import deque
```

**Step 2: Refactor `__init__` — add ring buffer and start persistent stream**

After line 16 (`self.q = queue.Queue()`), add ring buffer setup:

```python
# Ring buffer: stores last ~500ms of audio for instant capture
# At 16kHz, 500ms = 8000 samples. Each chunk from sounddevice is ~512-1024 frames.
# We store chunks in a deque with maxlen to auto-evict old data.
self._ring_buffer = deque(maxlen=16)  # ~16 chunks ≈ 500ms at typical chunk sizes
```

At the end of `__init__`, after the event tap thread start (after line 42), open the persistent stream:

```python
# Start always-on audio stream (captures to ring buffer continuously)
self._stream = sd.InputStream(
    samplerate=self.sample_rate,
    channels=1,
    dtype='float32',
    callback=self._audio_callback
)
self._stream.start()
print("[core_audio] Always-on audio stream started.", flush=True)
```

**Step 3: Update `_audio_callback` to always write ring buffer**

Replace the current `_audio_callback` (lines 118-122):

```python
def _audio_callback(self, indata, frames, time_info, status):
    if status:
        print(status, flush=True)
    chunk = indata.copy()
    self._ring_buffer.append(chunk)
    if self.is_recording:
        self.q.put(chunk)
```

This always feeds the ring buffer. When recording, it also feeds the capture queue.

**Step 4: Refactor `record_while_pressed` — remove stream open/close, add ring buffer flush**

Replace the entire `record_while_pressed` method (lines 124-164):

```python
def record_while_pressed(self) -> np.ndarray:
    """Blocks until Fn pressed, records audio, returns buffer on release."""
    self._start_event.clear()
    self._stop_event.clear()
    self._mode = 'IDLE'

    # Drain any leftover chunks from previous recording
    while not self.q.empty():
        self.q.get()

    print("[core_audio] Ready. Hold Fn to dictate, double-tap to toggle.", flush=True)

    # Block until fn pressed
    self._start_event.wait()

    # Flush ring buffer into capture queue (pre-press audio)
    for chunk in self._ring_buffer:
        self.q.put(chunk)

    self.is_recording = True
    if self.on_record_start:
        self.on_record_start()
    print("[core_audio] Recording...", flush=True)

    # Block until fn released (stream is already running, _audio_callback feeds q)
    self._stop_event.wait()

    self.is_recording = False
    if self.on_record_stop:
        self.on_record_stop()
    print("[core_audio] Stopped.", flush=True)

    chunks = []
    while not self.q.empty():
        chunks.append(self.q.get())

    if not chunks:
        return np.array([], dtype='float32')

    return np.concatenate(chunks, axis=0).flatten()
```

Key differences from the old version:
- No `sd.InputStream()` created here — stream is already running from `__init__`
- Ring buffer contents flushed into queue immediately on fn press (captures ~500ms of pre-press audio)
- `is_recording = True` gates `_audio_callback` to write to capture queue
- `_stop_event.wait()` blocks until release; stream stays open after

**Step 5: Commit**

```bash
git add tools/core_audio.py
git commit -m "fix: always-on audio stream with ring buffer for instant capture"
```

---

### Task 4: Manual end-to-end test

**Step 1: Start Ollama**

```bash
ollama serve &
```

**Step 2: Run Talky**

```bash
cd /Users/voellmy/Documents/antigravity/talky && python main.py
```

**Step 3: Verify all three fixes**

1. **Ring buffer / instant capture**: Press fn, immediately say "Hello world". Verify the word "Hello" is captured (not cut off).
2. **No latency**: Confirm there is no noticeable delay between fn press and the "Listening..." overlay appearing.
3. **No translation**: Set language to English, speak English. Verify output is English (not German). Then set to Deutsch, speak German, verify output is German.

**Step 4: Final commit if any adjustments needed**

```bash
git add -A
git commit -m "chore: final adjustments after manual testing"
```
