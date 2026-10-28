<p align="center">
  <img src="talky-logo.jpg" alt="Talky Logo" width="220" />
</p>

# Talky 2

### **Privacy-First, Local Voice Dictation & Selection-Aware Voice Editing for macOS**

Talky is a high-performance, zero-cost, and absolute-privacy voice productivity companion built natively for Apple Silicon. It converts spoken thoughts into text with sub-second latency, types directly at your cursor, and lets you rewrite or transform selected text using local Apple Silicon language models—all with zero cloud dependencies, zero subscriptions, and complete data privacy.

---

## 🚀 Key Features

- ⚡ **Instant Dictation (Fast Mode)**: Zero-cloud speech recognition powered by MLX Whisper running natively on Apple Silicon GPU and Neural Engine. Sub-second latency from shortcut release to cursor insertion.
- 🧠 **One-Button Voice Editing**: Highlight any editable text in any application (editor, browser, Slack, email), hold your shortcut, and speak an instruction (e.g., *"Make this concise"*, *"Turn this into bullet points"*, *"Übersetze ins Englische"*). A local Qwen3-4B model safely rewrites the selection in place.
- 🛡️ **Destination & Focus Protection**: Leverages macOS Accessibility APIs to verify the destination window, application, and character range before sending paste keystrokes. Prevents misdirected pastes or stray characters when switching windows.
- 🔒 **Absolute Privacy & Ephemeral Execution**: Audio streams are processed strictly in RAM and discarded immediately upon completion or cancellation. No dictation audio is stored to disk, and not a single byte leaves your machine.
- 🎙️ **On-Demand Microphone**: The microphone hardware activates only while an explicit dictation or meeting recording is active, and is released immediately on finish or cancel—no background listening, no idle pre-rolls.
- 🤝 **Meeting Mode**: Captures extended meeting audio and produces structured Markdown notes (Executive Summary, Key Discussion Points, Action Items) saved directly to `~/Documents/Talky/Meetings/` using local Ollama models.
- ⌨️ **Configurable Global Shortcuts**: Trigger dictation with **§** (default), **Control+Shift+Space**, or **Fn** (hold to record, double-tap for hands-free).
- ⏱️ **Real-Time Latency Metrics**: Every dictation provides timing metrics (transcription, model inference, paste, total latency) to ensure consistent high performance.
- 🔊 **Audio & Visual Feedback**: Subtle audio chimes confirm recording start, completion, and cancellation, paired with a non-stealing-focus overlay indicator.
- ↩️ **Original Text Recovery**: Retains the latest transcript and original selected text in memory. If an edit fails or focus changes, quickly retrieve either via **Menu > Copy Last Result** or **Copy Original Text**.

---

## 🛠️ System Requirements

- **Platform**: Apple Silicon Mac (M1, M2, M3, M4, or later).
- **Operating System**: macOS 14.0+ (Sonoma, Sequoia, or later).
- **Python**: Python 3.12 (included when running the packaged application).
- **Permissions**:
  - **Microphone**: For audio recording.
  - **Accessibility**: Required for global shortcut detection, caret selection verification, and text injection (`System Settings > Privacy & Security > Accessibility`).
- **Optional (Meeting Mode only)**: [Ollama](https://ollama.com) running locally for long-form meeting summaries:
  ```bash
  ollama pull gemma4:latest
  ```

---

## 📦 Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/voellmy42/talky.git
   cd talky
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python3.12 -m venv .venv-mlx
   source .venv-mlx/bin/activate
   ```

3. **Install pinned dependencies**:
   ```bash
   pip install -r requirements-mlx.lock.txt
   ```

4. **Launch Talky**:
   ```bash
   python main.py
   ```
   *Note: On first startup, MLX Whisper automatically downloads and caches its base weights locally. Subsequent startups initialize instantly.*

---

## ⌨️ Controls & Shortcuts

| Action | Shortcut / Control | Behavior |
| :--- | :--- | :--- |
| **Instant Dictation** | **Hold `§` or `Fn`** | Speak naturally. Release to transcribe and inject text directly at your cursor. |
| **Selection Voice Edit** | **Select text + Hold `§` or `Fn`** | Speak how you want to modify the selected text (*"Make this concise"*, *"Fix grammar"*), then release. |
| **Hands-Free Mode** | **Double-tap `Fn`** or toggle **`§`** | Starts hands-free recording without holding. Press again to finish and transcribe. |
| **Cancel Recording** | **`Esc`** or **Menu > Cancel** | Discards current audio or cancels in-flight inference without modifying the target field. |
| **Recover Text** | **Menu > Copy Last Result** | Copies the most recent generated text to your clipboard without re-triggering a paste. |
| **Recover Original** | **Menu > Copy Original Text** | Recovers the unmodified selected text if an AI rewrite did not match your intention. |
| **Meeting Mode** | **Menu Bar > Start Meeting** | Records long-form meeting audio. Click **Stop** to generate and save structured Markdown notes. |

You can customize your preferred shortcut via **Menu > Dictation Shortcut** (**§**, **Control+Shift+Space**, or **Fn only**).

---

## 🧠 One-Button Voice Editing

Talky unifies standard dictation and AI text modification under a single shortcut:

1. **At a cursor (no selection)**: The shortcut performs standard **Fast Dictation** directly through MLX Whisper.
2. **With text selected**: The shortcut automatically switches into **Selection Editing** mode. Speak your instructions:
   - *"Make this shorter and punchier"*
   - *"Turn this into a Markdown bullet list"*
   - *"Übersetze diesen Absatz ins Englische"*
   - *"Draft a friendly response confirming Wednesday at 2pm"*

### Enabling Local AI Editing
1. Open the Talky menu bar icon and select **Set Up / Load AI Editing…**.
2. Talky will download and verify the local 4-bit model weights (~2.28 GB, Qwen3-4B).
3. All model weights are pinned, SHA-256 verified, and cached locally. Inference runs directly on Apple Silicon via MLX-LM.
4. When not in use, the model automatically unloads from memory after 5 minutes of idle time to conserve system resources.

### Safety & Guardrails
- **Exact Destination Matching**: If you switch windows, change tabs, or lose focus while editing, Talky aborts text injection and saves the output in **Copy Last Result**.
- **Factual Integrity**: The editing pipeline conservatively verifies numbers, dates, negation, and key conditions to prevent hallucinated changes to facts.
- **Fail-Safe Operation**: If an edit fails or is cancelled, Talky will **never** accidentally paste your raw spoken instruction into your document.

---

## Appearance Preview

Choose **Appearance → Standard / Fun · Walkie-talkie** in the Talky menu. Standard
is the default; your choice is remembered. Fun mode is a friendly gold walkie-talkie
with a green pixel monitor, live waveform and expressions for listening, voice
editing, thinking, completion, recovery and cancellation. It appears during activity
and brief result feedback, then disappears. Its body stays anchored; only small
antenna movements and pixel expressions animate. Reduce Motion keeps it still.

Choose **Preview Appearance…** in the Talky menu, or **Preview appearance** on
its welcome screen. Compare **Standard** and **Fun**, try every visual state and
**Play all states** without granting
microphone permission. All audio levels in this window are simulated; it does not
record, download models, read selections or paste text. Previewing a style does not
change your saved appearance. Close the preview to stop it.

From source, run `.venv-mlx/bin/python -m tools.ui_preview`. Packaged builds also
support `/Applications/Talky.app/Contents/MacOS/Talky --preview-ui`.

The compact capsule stays above the Dock and never takes keyboard focus. Listening
bars follow input levels; processing uses a gentle traveling wave. Animations stop
when hidden, and follow macOS Reduce Motion and Reduce Transparency preferences.
The preview includes a reduced-motion switch for checking the static presentation.

## 🧪 Testing & Development

### Running the Test Suite
Talky comes with a comprehensive unit test suite covering session lifecycles, MLX inference, selection capture, focus verification, and safety guards:

```bash
.venv-mlx/bin/python -m unittest \
  test_talky_v2 \
  test_sessions \
  test_delivery \
  test_mlx_formatter \
  test_selection_editing -v
```

### Packaging the macOS Application
To build a standalone Apple Silicon `.app` bundle:

```bash
TALKY_DIST_PATH=dist/Talky TALKY_BUILD_PATH=build/Talky ./build.sh
dist/Talky/Talky.app/Contents/MacOS/Talky --check-build
```

---

## 🏗️ Architecture

Talky is designed around a deterministic **3-Layer Architecture**:

1. **Layer 1: Standard Operating Procedures (SOPs)** (in `architecture/`):
   - [Audio Capture SOP](architecture/audio_capture_sop.md) — On-demand CoreAudio streaming and volume normalization.
   - [STT (Speech-to-Text) SOP](architecture/stt_sop.md) — Low-latency Apple Silicon MLX Whisper transcription.
   - [LLM Cleaner & Editor SOP](architecture/llm_cleaner_sop.md) — Prompt templates, safety guards, and memory management.
   - [Text Injection SOP](architecture/text_injection_sop.md) — Quartz event injection and Accessibility API verification.
2. **Layer 2: Router & State Management**:
   - `main.py` / `app.py` — Orchestrates audio state transitions, hotkey listening, UI overlays, and system tray actions.
3. **Layer 3: Deterministic Tools** (in `tools/`):
   - Modular tools for audio, config, focus verification, MLX inference, and session logging.

---

## 📜 Project Constitution

Talky adheres to strict behavioral principles regarding speed, local privacy, and silent execution. See [gemini.md](gemini.md) for the project constitution.

---

<p align="center">
  <i>Part of the Maison Voellmy Collection</i><br>
  © 2026 Maison Voellmy. All rights reserved.
</p>
