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
- 🧠 **Polished Mode**: Optional deeper cleanup using local Ollama and `gemma4:latest`.
- ⏱️ **Measured Latency**: Every dictation reports transcription, formatting, paste, and total response time.
- 🎧 **On-Demand Capture**: Models stay ready, while the microphone opens only for recording and is released on stop/cancel.
- 🤝 **Meeting Mode**: Record long sessions and get structured Markdown notes (Summary, Key Points, Action Items) saved directly to your Documents.
- 🔒 **Absolute Privacy**: No cloud, no API keys, no data sharing. Everything runs on your local CPU/GPU.
- 🔊 **Audio Feedback**: Subtle chimes provide non-intrusive confirmation of recording states.
- 🖱️ **macOS Integration**: Minimalist menu bar icon and a non-stealing-focus overlay indicator.
- **Destination checks**: Checks the original app, window, text field and available caret selection before sending paste. If the destination changes or cannot be identified, use **Copy Last Dictation** from the menu.
- **Cancellation**: Press **Esc** or choose **Cancel Dictation** to discard a recording or prevent a processing result from being pasted.
- **Recovery**: Copy the latest dictation or original transcript from the menu, or clear them. Text stays in memory until cleared, cancelled, replaced or quit.

---

## 🛠️ Prerequisites

Talky is designed for **macOS** and requires the following:

1.  **Python 3.10+**
2.  **Microphone and Accessibility permissions**: Granted during setup.
3.  **Optional Ollama**: Only Polished and Meeting modes use a separately running local Ollama service. Basic Fast dictation does not require it. For those optional modes, install Ollama and pull:
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
    python -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
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
| **Instant Dictation** | **Hold `Fn`** | Records while held. Releases to transcribing and inject. |
| **Hands-Free Mode** | **Double-tap `Fn`** | Toggles recording on/off without holding. |
| **Start / Finish** | **§** or **Menu > Start / Finish Dictation** | Toggles hands-free recording. The shortcut press is consumed so § is not typed into your prompt. |
| **Cancel Dictation** | **Esc** or menu | Discards capture or blocks late paste. If inference has started, wait for it to finish before recording again. |
| **Recover Text** | **Menu > Copy Last Dictation / Copy Original Transcript** | Copies retained text without attempting another paste. |
| **Meeting Mode** | **Menu Bar > Start Meeting** | Records long-form audio. Stop to generate a summary. |

### **Formatting Modes**

| Mode | Best for | Behavior |
| :--- | :--- | :--- |
| **Fast (default)** | Everyday dictation | Removes hesitation sounds and tidies spacing locally, then pastes immediately. |
| **Polished (AI)** | Important messages | Uses local Gemma for deeper grammar and punctuation cleanup, with raw text as a timeout fallback. |

Choose the mode from **Menu Bar > Formatting**. Talky remembers both formatting mode and language between launches. The Productivity Stats menu shows the response time of the latest dictation.

Choose **Menu > Dictation Shortcut** to use **§** (default), **Control+Shift+Space**, or **Fn only**. Changes apply immediately and persist across launches. § is matched by the character produced by the keyboard layout, rather than a fixed physical key. Command/Control/Option combinations with § retain their ordinary behavior. F8 is no longer a Talky shortcut.

Polished mode uses a 2.5-second HTTP timeout and rejects edits that add/reorder words, remove substantive words or change numbers/negations under its restricted edit policy. It falls back to the original transcript. These guards do not prove semantic equivalence; polishing may reject useful edits. Talky never starts or quits your Ollama service.

The microphone opens only for an explicit dictation or meeting recording and is released on stop/cancel. Idle pre-roll is disabled. Speak after the start chime so the microphone has time to open. No dictation audio is written to disk. Meeting mode intentionally saves notes to disk. Recognition and polishing may still be running after cancellation, but the cancelled result will not be pasted.

Destination checks depend on each application's Accessibility support. Unsupported fields, changed selections and uncertain destinations retain text for explicit copying. A sent paste shortcut does not prove the destination accepted the text. Enter is never sent automatically.

### Development build

```bash
.venv/bin/python -m unittest test_talky_v2 test_sessions test_delivery -v
TALKY_DIST_PATH=dist/session-preview TALKY_BUILD_PATH=build/session-preview ./build.sh
```

This creates an ad-hoc signed Apple Silicon development app alongside the existing build. Distribution to colleagues still requires Developer ID signing, notarization and validation on both M1 and M4, including managed work Macs.

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
