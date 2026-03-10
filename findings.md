# Research, Discoveries, and Constraints

## 2026-03-10
### Dependency Research for Local STT Pipeline
1. **Audio Capture**: `sounddevice` combined with `numpy` is the standard, low-latency approach for real-time audio streams in Python. It avoids the complex C-bindings issues occasionally seen with `pyaudio` on Windows.
2. **STT Engine**: `faster-whisper` (CTranslate2 backend) is highly optimized. Loading the model once into RAM allows for instant transcription upon hotkey release. It accepts numpy arrays directly.
3. **Hotkey Binding**: For global hotkeys on Windows without focus switching, the `keyboard` library is robust.
4. **Text Injection**: `pyautogui` for keystroke simulation and `pyperclip` for clipboard manipulation are reliable across OSes.
5. **LLM Formatting**: `ollama` running locally with the `llama3` or `phi3` or `qwen2.5:3b` model communicates via simple local HTTP requests, providing fast text formatting with predictable latency if the model is kept loaded in memory. Wait times can be >20s on first load for larger models.

### Optimization & UI Ideas (Phase 4/5)
- **Sound Effects**: Playing a tiny `.wav` file (like a click or soft chime) when the recording starts and stops will give the user confidence without needing a UI.
- **System Tray Icon**: `pystray` could be used to put a minimalist icon in the Windows taskbar, allowing the user to quit the script cleanly or change the hotkey without opening the terminal.
- **Latency Refinement**: Modifying the VAD sensitivity in `faster-whisper`, or switching to an even smaller quantized LLM (like `qwen2.5:0.5b` or `llama3.2:1b`) could shave off more milliseconds from the response time.
