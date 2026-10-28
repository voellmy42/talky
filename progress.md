# Progress Log

*(Log of what was done, errors encountered, tests, and results)*

## 2026-10-28
- Built and installed Talky on an Apple M1 MacBook Pro with 16 GB RAM, macOS 26.5.2.
- Shipped the compact native overlay in 2.3.0, with fluid waveform, reduced-motion
  support, clearer onboarding/menu and a speech-free appearance preview.
- Added selectable Standard/Fun appearances in 2.4.0. Fun uses a native illustrated
  walkie-talkie with a green pixel monitor, waveform and state-specific expressions;
  it appears only during activity and brief result feedback.
- Verified 101 tests, native visual/lifecycle checks, packaged Metal/TLS/resources,
  installed version and signature. Desktop automation could not inspect the final
  installed window because its native connection failed.
- User reported the latest app works flawlessly on this M1. Specific speech and
  cross-app delivery scenarios were not enumerated.
- Details: [Quiet native UI](docs/quiet-native-ui.md), [Fun mode](docs/fun-mode.md).

## 2026-03-10
- Initialized Project Memory (`task_plan.md`, `findings.md`, `progress.md`, `gemini.md`)
- Began Phase 1: Discovery
- Defined Layer 1 Architecture SOPs (`audio_capture_sop.md`, `stt_sop.md`, `llm_cleaner_sop.md`, `text_injection_sop.md`)
- Implemented Python Tool logic in `tools/` and router in `main.py`
- Completed Phase 2 Link Verification
  - `faster-whisper` (`tiny` model) passed in-memory initialization and dummy inference.
  - `ollama` (`qwen2.5:3b` model) successfully formatted test phrase locally, required 60s timeout allowance for initial slow model cold-load into RAM.
- Ready for manual end-to-end system testing.
