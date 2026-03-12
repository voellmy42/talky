<p align="center">
  <img src="talky-logo.jpg" alt="Talky Logo" width="200" />
</p>

# Talky

### **Privacy-First, Local Voice Dictation & Meeting Summarizer**

Talky is a high-performance, zero-cost, and absolute-privacy voice tool for macOS. It turns your speech into perfectly formatted text instantly, injecting it directly into your cursor position, or summarizes entire meetings into structured notes—all without a single byte leaving your machine.

---

## 🚀 Key Features

- 🎙️ **Local Speech-to-Text**: Powered by `faster-whisper` for lightning-fast transcription with auto language detection.
- 🧠 **AI-Powered Formatting**: Seamlessly removes filler words ("um", "uh") and fixes grammar using `Ollama` and `qwen2.5:3b`.
- ⏱️ **Sub-2s Latency**: Optimized for extreme speed—from hotkey release to text injection.
- 🤝 **Meeting Mode**: Record long sessions and get structured Markdown notes (Summary, Key Points, Action Items) saved directly to your Documents.
- 🔒 **Absolute Privacy**: No cloud, no API keys, no data sharing. Everything runs on your local CPU/GPU.
- 🔊 **Audio Feedback**: Subtle chimes provide non-intrusive confirmation of recording states.
- 🖱️ **macOS Integration**: Minimalist menu bar icon and a non-stealing-focus overlay indicator.

---

## 🛠️ Prerequisites

Talky is designed for **macOS** and requires the following:

1.  **Python 3.10+**
2.  **[Ollama](https://ollama.com/)**: Installed and running.
3.  **Model**: Pull the recommended model:
    ```bash
    ollama pull qwen2.5:3b
    ```
4.  **Accessibility Permissions**: Required for text injection (System Settings > Privacy & Security > Accessibility).

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
| **Meeting Mode** | **Menu Bar > Start Meeting** | Records long-form audio. Stop to generate a summary. |

> [!NOTE]
> Meeting notes are stored in `~/Documents/Talky/Meetings/` as Markdown files.

---

## 🏗️ Architecture

Talky follows a **3-Layer Architecture** for robustness and maintainability:

1.  **Layer 1 (SOPs)**: Standard Operating Procedures defined in `architecture/`.
    - [Audio Capture SOP](file:///Users/voellmy/Documents/antigravity/talky/architecture/audio_capture_sop.md)
    - [STT (Speech-to-Text) SOP](file:///Users/voellmy/Documents/antigravity/talky/architecture/stt_sop.md)
    - [LLM Cleaner SOP](file:///Users/voellmy/Documents/antigravity/talky/architecture/llm_cleaner_sop.md)
    - [Text Injection SOP](file:///Users/voellmy/Documents/antigravity/talky/architecture/text_injection_sop.md)
2.  **Layer 2 (Router)**: `main.py` manages the logic loop and state transitions.
3.  **Layer 3 (Deterministic Tools)**: Specialized tools in `tools/` for audio, STT, LLM, and output.

---

## 📜 Project Constitution

Talky is guided by a strict set of behavioral rules and architectural invariants. See [gemini.md](file:///Users/voellmy/Documents/antigravity/talky/gemini.md) for the full project constitution.

---

<p align="center">
  <i>Part of the Maison Voellmy Collection</i><br>
  © 2026 Maison Voellmy. Alle Rechte vorbehalten.
</p>
