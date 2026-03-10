# Speech-to-Text (STT) Standard Operating Procedure (SOP)

## Purpose
Transcribe the raw audio buffer into a string of text rapidly using `faster-whisper`.

## Tool Execution Context
- **Script path**: `tools/core_stt.py`
- **Dependencies**: `faster-whisper`

## Input Data Shape
- `audio_buffer`: A 1D `numpy.ndarray` (`float32`) passed from `core_audio.py`.

## Output Data Shape
- Returns `raw_transcription` (String).

## Execution Rules
- **Pre-loading**: The `WhisperModel` must be initialized on program startup in `main.py` and kept in memory to eliminate cold start times during the dictation loop.
- **Model Size**: Use `base` or `small` with `float16` or `int8` quantization (depending on GPU/CPU availability) to ensure transcription takes < 1 second.
- **VAD (Voice Activity Detection)**: Enable VAD filters in `faster-whisper` to skip silent frames.

## Error States & Handling
- *Model Failed to Load* -> Hard crash on init.
- *Empty Transcription / Silent Audio* -> Return empty string. The pipeline should abort early rather than passing empty strings to Ollama.
