<p align="center">
  <img src="talky-logo.jpg" alt="Talky Logo" width="200" />
</p>

# Talky 2

### **Privacy-First, Local Voice Dictation & Meeting Summarizer**

Talky is a high-performance, zero-cost, and absolute-privacy voice tool for macOS. It turns your speech into perfectly formatted text instantly, injecting it directly into your cursor position, or summarizes entire meetings into structured notes—all without a single byte leaving your machine.

---

## 🚀 Key Features

- 🎙️ **Local Speech-to-Text**: Powered by MLX Whisper on Apple Silicon.
- ⚡️ **Fast Mode**: The default path formats locally without waiting for an LLM.
- 🧠 **One-Button Editing**: Select text, hold your usual key and say how to change it. Local AI handles the edit.
- ⏱️ **Measured Latency**: Every dictation reports transcription, formatting, paste, and total response time.
- 🎧 **On-Demand Capture**: Models stay ready, while the microphone opens only for recording and is released on stop/cancel.
- 🤝 **Meeting Mode**: Record long sessions and get structured Markdown notes (Summary, Key Points, Action Items) saved directly to your Documents.
- 🔒 **Absolute Privacy**: No cloud, no API keys, no data sharing. Everything runs on your local CPU/GPU.
- 🔊 **Audio Feedback**: Subtle chimes provide non-intrusive confirmation of recording states.
- 🖱️ **macOS Integration**: Minimalist menu bar icon and a non-stealing-focus overlay indicator.
- **Destination checks**: Checks the original app, window, text field and available caret selection before sending paste. If the destination changes or cannot be identified, use **Copy Last Result** from the menu.
- **Cancellation**: Press **Esc** or choose **Cancel** to discard a recording or prevent a processing result from being pasted.
- **Recovery**: Copy the latest dictation or original transcript from the menu, or clear them. Text stays in memory until cleared, cancelled, replaced or quit.

---

## 🛠️ Prerequisites

This embedded MLX preview targets **Apple Silicon and macOS 26+** with the pinned runtime. The older session preview remains separate.

1.  **Python 3.12** for development (included in the packaged app).
2.  **Microphone and Accessibility permissions**: Granted during setup.
3.  **Optional Ollama for Meeting summaries only**: Install and run Ollama separately for Meeting mode:
    ```bash
    ollama pull gemma4:latest
    ```
4.  **Speech model**: MLX Whisper downloads its model on first use, then inference runs locally. First startup may take longer while this model is downloaded and warmed up.

---

## 📦 Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/voellmy42/talky.git
    cd talky
    ```

2.  **Setup Virtual Environment**:
    ```bash
    python3.12 -m venv .venv-mlx
    source .venv-mlx/bin/activate
    ```

3.  **Install Dependencies**:
    ```bash
    pip install -r requirements-mlx.lock.txt
    ```

---

## ⌨️ Usage

Run the application:
```bash
python main.py
```

### **Controls**

| Action | Control | Result |
| :--- | :--- | :--- |
| **Voice Input** | **Hold `Fn`** | No selection: Fast dictation. Selected editable text: speak an edit request, then release. |
| **Hands-Free Mode** | **Double-tap `Fn`** | Toggles recording on/off without holding. |
| **Start / Finish** | **§** or **Menu > Start / Finish Voice Input** | Toggles hands-free recording. The shortcut press is consumed so § is not typed into your prompt. |
| **Cancel** | **Esc** or menu | Discards capture or blocks late paste. If inference has started, wait for it to finish before recording again. |
| **Recover Text** | **Menu > Copy Last Result / Copy Original Text** | Copies retained text without attempting another paste. |
| **Meeting Mode** | **Menu Bar > Start Meeting** | Records long-form audio. Stop to generate a summary. |

### **One-button voice editing**

With a cursor and no selection, your usual shortcut always uses Fast dictation.
With selected editable text, the same shortcut records an instruction such as
“Make this shorter,” “Turn this into a bullet list,” or “Übersetze das ins Englische.”
The overlay shows **Dictating · EN** or **Editing selection · DE** before you speak.
The Fast/Polished choice is retired from the menu.

Choose **Set Up / Load AI Editing…** to download the optional local editing model
(approximately 2.28 GB, Qwen3-4B in 4-bit form). This is a larger model than the
previous polishing preview; its weights are installed separately. Turn **AI
selection editing** off to unload it. Model files are pinned and hash-verified;
loading, source-language detection and inference stay on your Mac. Ordinary
utterances do not run through the language model.

**Speech Language** selects recognition of your dictation or editing instruction.
The edited text keeps the selection's language unless you explicitly request
translation. An English selection with “Mach das kürzer” should stay English.
English and German settings persist between launches. They have been checked with
synthetic speech; real voices, accents and mixed-language speech still need testing.

The selection must remain in the original app, window and field, with the same
range and content, for replacement. Changed focus keeps the edit for **Copy Last
Result**; **Copy Original Text** recovers the selected source. Failed, cancelled,
truncated or unchanged edits do not paste anything. A failed edit never falls back
to inserting the spoken instruction. The editor conservatively rejects changes
to written numbers, weekdays, negation and time conditions; this can reject valid
edits and does not prove unchanged meaning. Changing factual values is outside
this first preview. Review AI rewrites and use the destination's normal Undo or
recover the original when needed.

Editing has a cooperative 12-second operation budget, including model preparation;
a running GPU kernel cannot be interrupted immediately. Weights unload after five
idle minutes or when AI editing is disabled. Low-memory handling remains heuristic.
Long passages can be rejected without changing the original selection.

Choose **Menu > Dictation Shortcut** to use **§** (default), **Control+Shift+Space**,
or **Fn only**. Each uses the same selection-aware route. Changes persist and apply
immediately. § is matched by its keyboard-layout character, not a fixed physical key.

The microphone opens only for an explicit dictation or meeting recording and is released on stop/cancel. Idle pre-roll is disabled. Speak after the start chime so the microphone has time to open. No dictation audio is written to disk. Meeting mode intentionally saves notes to disk. Recognition or model work may still be running after cancellation, but the cancelled result will not be pasted.

Destination checks depend on each application's Accessibility support. Unsupported fields, changed selections and uncertain destinations retain text for explicit copying. A sent paste shortcut does not prove the destination accepted the text. Enter is never sent automatically.

### Development build

```bash
.venv-mlx/bin/python -m unittest test_talky_v2 test_sessions test_delivery test_mlx_formatter test_selection_editing -v
TALKY_DIST_PATH=dist/one-button-preview TALKY_BUILD_PATH=build/one-button-preview ./build.sh
dist/one-button-preview/Talky.app/Contents/MacOS/Talky --check-build
```

This creates an ad-hoc signed Apple Silicon development app alongside the existing build. `TALKY_VENV` overrides the build environment if needed. Distribution to colleagues still requires Developer ID signing, notarization and validation on both M1 and M4, including managed work Macs. Rebuilding an ad-hoc signed app can invalidate its saved Accessibility approval; quit other Talky copies before trying a preview.

See [one-button editing and verification](docs/one-button-preview.md) for offline model checks, benchmark reproduction and quality limitations. Legacy polishing APIs remain available to development scripts. Meeting summaries still use Ollama; meeting capture is microphone-only in this milestone.

> [!NOTE]
> Meeting notes are stored in `~/Documents/Talky/Meetings/` as Markdown files.

---

## 🏗️ Architecture

Talky follows a **3-Layer Architecture** for robustness and maintainability:

1.  **Layer 1 (SOPs)**: Standard Operating Procedures defined in `architecture/`.
    - [Audio Capture SOP](architecture/audio_capture_sop.md)
    - [STT (Speech-to-Text) SOP](architecture/stt_sop.md)
    - [LLM Cleaner SOP](architecture/llm_cleaner_sop.md)
    - [Text Injection SOP](architecture/text_injection_sop.md)
2.  **Layer 2 (Router)**: `main.py` manages the logic loop and state transitions.
3.  **Layer 3 (Deterministic Tools)**: Specialized tools in `tools/` for audio, STT, LLM, and output.

---

## 📜 Project Constitution

Talky is guided by a strict set of behavioral rules and architectural invariants. See [gemini.md](gemini.md) for the full project constitution.

---

<p align="center">
  <i>Part of the Maison Voellmy Collection</i><br>
  © 2026 Maison Voellmy. Alle Rechte vorbehalten.
</p>
