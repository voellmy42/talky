# Talky Improvements Design

**Date:** 2026-03-10
**Status:** Approved

## Problem Statement

Three user-reported issues:
1. **Unwanted translation**: Speaking English with English selected produces German output. The LLM formatter doesn't receive the language context and translates freely.
2. **Slow response on fn press**: Audio stream opens after fn key press, causing ~300-500ms delay.
3. **First words lost**: Same root cause as #2 — audio capture starts too late, missing the beginning of speech.

## Design

### Fix 1: Language-aware LLM prompt

**Change**: Pass the selected language code from the pipeline through to `LLMFormatter.format_text()` and inject it into the prompt.

**Details**:
- `format_text(raw_transcription, language)` receives the BCP-47 code ("de" or "en")
- The system prompt is augmented with an explicit language constraint: "The user is speaking {language}. Your output MUST be in {language}."
- This gives the model an unambiguous instruction rather than the current generic "preserve original language" rule

**Files changed**: `tools/core_llm.py`, `main.py`

### Fix 2+3: Always-on audio stream with ring buffer

**Change**: Keep `sd.InputStream` open permanently. Maintain a circular buffer of the last ~500ms of audio. On fn press, prepend the ring buffer contents to the recording.

**Details**:
- Stream opens once at `__init__` time, stays open for the lifetime of the app
- A numpy ring buffer (collections.deque of chunks) continuously stores the last 500ms of audio
- `_audio_callback` always writes to the ring buffer; when `is_recording=True`, also writes to the capture queue
- On fn press: immediately copy ring buffer contents into the capture queue, then continue normal capture
- On fn release: stop writing to capture queue (stream stays open)
- Memory cost: ~32KB (16kHz * 1ch * 4 bytes * 0.5s)

**Files changed**: `tools/core_audio.py`

## Out of Scope
- Changing the Whisper model size or STT engine
- Adding new languages beyond de/en
- UI changes
