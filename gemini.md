# Project Constitution (gemini.md)

## 1. Data Schemas

### Input
- `audio_buffer`: In-memory audio stream captured on hotkey press (stateless).
- `local_config` (Optional - JSON): User preferences (language and formatting mode).

### Intermediate
- `raw_transcription` (String): Output text from local Whisper / faster-whisper STT.

### Output (Delivery Payload)
- `cleaned_text` (String): Text cleaned deterministically in Fast mode or by embedded MLX-LM in Polished preview, then delivered to the checked destination.

## 2. Behavioral Rules
- **Speed over perfection:** Sub-2s latency from release of hotkey to text appearing.
- **Silent removal:** Remove filler words (um, uh, you know).
- **Format only:** Fix grammar & punctuation without changing meaning or tone. Do NOT rephrase, summarize, or shorten.
- **Privacy absolute:** Do NOT send any audio or text outside the local machine.
- **Ephemeral execution:** Do NOT store dictation recordings. Keep only the latest raw/final transcript in memory for explicit recovery; clear it on cancellation, Clear Last Dictation or quit. Meeting notes remain an intentional saved output.
- **Language:** Default German/English (Swiss context), configurable.

## 3. Architectural Invariants
- **3-Layer Architecture:** Layer 1 (SOPs in `architecture/`), Layer 2 (Navigation/Reasoning), Layer 3 (Deterministic `tools/`).
- **Data-First Rule:** Define JSON schema before tool building.
- **Self-Annealing Loop:** Analyze, Patch, Test, Update SOP.
- **Storage:** Ephemeral `.tmp/` vs Global Payload (OS Clipboard/Input Injection).
- **Core Dependencies:** MLX Whisper (STT), optional embedded MLX-LM for Polished preview, and optional Ollama for Meeting summaries. No external API keys or cloud inference. Explicit model installation may download public weights.

## 4. Maintenance Log
- **2.1.0 preview**: Embedded MLX-LM dictation backend, pinned/verified opt-in model installation, cooperative generation cancellation/deadlines, low-memory/idle eviction and offline packaged inference checks. Fast remains default; Meeting summaries still use Ollama.
- **Talky 2**: Added Fast/Polished formatting modes, persistent 500 ms audio pre-roll, native Quartz paste, clipboard race protection, and per-stage latency measurement.
- **2.0.1 preview**: Replaced idle pre-roll with on-demand microphone capture. Moved controls off the event-tap callback, aligned shortcut authorization with Accessibility, and added F8/menu start/finish.
- **2.0.2 preview**: Replaced F8 with configurable §/Control+Shift+Space toggles, persisted in settings and changeable from the menu without rebuilding. Consume only shortcut keydown/up/repeats to avoid stray typed characters.
