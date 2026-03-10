# Talky - Local Voice Dictation Pipeline

A zero-cost, privacy-first voice dictation tool that works locally on your desktop.
Talky uses local models for speech-to-text (STT) and text formatting (LLM), enabling hotkey triggers to instantly transcribe and format your speech, injecting it directly into your active application.

## Features
- **Local STT**: Powered by `faster-whisper`.
- **Local LLM Formatting**: Powered by `ollama` with `qwen2.5:3b`.
- **Zero Privacy Risk**: All processing happens entirely on your machine.
- **Fast Injection**: Sub-2s latency.
- **Auto Formatting**: Removes filler words without changing meaning or tone.

## Prerequisites
- Python 3.10+
- [Ollama](https://ollama.com/) running locally with the `qwen2.5:3b` model installed (`ollama run qwen2.5:3b`).

## Installation
1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install sounddevice numpy keyboard requests pyautogui pyperclip faster-whisper
   ```
3. Initialize a `.env` file (copied from `.env.example` if applicable).

## Usage
Run the main router script:
```bash
python main.py
```
Press and hold `F8` (default) to speak. Release to inject formatted text into your currently active window.

## Architecture
- **Layer 1 (SOPs)**: See `architecture/` for standard operating procedures.
- **Layer 2 (Router)**: `main.py` handles the logic loop.
- **Layer 3 (Deterministic Tools)**: `tools/` contains STT, LLM, Audio, and Output components.
