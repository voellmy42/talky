# Talky - Local Voice Dictation Pipeline

A zero-cost, privacy-first voice dictation tool that works locally on your desktop.
Talky uses local models for speech-to-text (STT) and text formatting (LLM), enabling hotkey triggers to instantly transcribe and format your speech, injecting it directly into your active application.

## Features
- **Local STT**: Powered by `faster-whisper` with auto language detection (English, German, French, etc.).
- **Local LLM Formatting**: Powered by `ollama` with `qwen2.5:3b` — multilingual-aware, preserves original language.
- **Zero Privacy Risk**: All processing happens entirely on your machine.
- **Fast Injection**: Sub-2s latency.
- **Auto Formatting**: Removes filler words in any language without changing meaning or tone.
- **Audio Feedback**: Subtle chimes on record start/stop.
- **macOS Native UI**: Menu bar icon + floating overlay indicator.

## Prerequisites
- macOS (Accessibility permission required)
- Python 3.10+
- [Ollama](https://ollama.com/) running locally with the `qwen2.5:3b` model installed (`ollama run qwen2.5:3b`).

## Installation
1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install sounddevice numpy requests pyautogui pyperclip faster-whisper pyobjc
   ```

## Usage
Run the main script:
```bash
python main.py
```
- **Hold `Fn`** to speak — release to inject formatted text into your active window.
- **Double-tap `Fn`** to toggle hands-free mode (tap again to stop).

## Architecture
- **Layer 1 (SOPs)**: See `architecture/` for standard operating procedures.
- **Layer 2 (Router)**: `main.py` handles the logic loop.
- **Layer 3 (Deterministic Tools)**: `tools/` contains STT, LLM, Audio, Output, and Feedback components.
