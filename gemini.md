# Project Constitution (gemini.md)

## 1. Data Schemas

### Input
- `audio_buffer`: In-memory audio stream captured on hotkey press (stateless).
- `local_config` (Optional - JSON/YAML): User preferences (custom dictionaries, language selection).

### Intermediate
- `raw_transcription` (String): Output text from local Whisper / faster-whisper STT.

### Output (Delivery Payload)
- `cleaned_text` (String): Text cleaned by local LLM (Ollama), injected directly into active cursor position or copied to OS clipboard as fallback.

## 2. Behavioral Rules
- **Speed over perfection:** Sub-2s latency from release of hotkey to text appearing.
- **Silent removal:** Remove filler words (um, uh, you know).
- **Format only:** Fix grammar & punctuation without changing meaning or tone. Do NOT rephrase, summarize, or shorten.
- **Privacy absolute:** Do NOT send any audio or text outside the local machine.
- **Stateless execution:** Do NOT store recordings — buffer is wiped after each use.
- **Language:** Default German/English (Swiss context), configurable.

## 3. Architectural Invariants
- **3-Layer Architecture:** Layer 1 (SOPs in `architecture/`), Layer 2 (Navigation/Reasoning), Layer 3 (Deterministic `tools/`).
- **Data-First Rule:** Define JSON schema before tool building.
- **Self-Annealing Loop:** Analyze, Patch, Test, Update SOP.
- **Storage:** Ephemeral `.tmp/` vs Global Payload (OS Clipboard/Input Injection).
- **Core Dependencies:** Ollama (LLM) and Whisper/faster-whisper (STT). No external API keys. No cloud dependency.

## 4. Maintenance Log
*(To be updated during Trigger phase)*
