# Meeting Mode — Design Document

**Date:** 2026-03-11
**Status:** Approved

## Overview

Add a "Meeting Mode" to Talky — a long-form recording mode that captures extended speech and produces structured summary documents. Strictly separated from the existing dictation mode to prevent mixing word-for-word transcription with summarization.

## Core Concept

| | Dictation Mode (existing) | Meeting Mode (new) |
|---|---|---|
| **Purpose** | Word-for-word text injection at cursor | Summarize long-form speech into a document |
| **Activation** | Fn hold / double-tap | Menu bar → "Start Meeting" |
| **Duration** | Seconds to a few minutes | Minutes to hours |
| **Output** | Text injected at cursor | Markdown file saved to disk |
| **LLM role** | Clean/format raw transcription | Summarize and structure content |

## Mode Separation

- Dictation Mode and Meeting Mode are **mutually exclusive**
- While Meeting Mode is active, Fn-key dictation is **disabled**
- Each mode has distinct visual indicators (overlay color, menu bar icon, status text)

## Activation & UI

### Menu Bar Changes
- New menu item: **"Start Meeting"** / **"Stop Meeting"** (toggles based on state)
- When meeting active: menu bar icon changes to red record dot (SF Symbol `record.circle`)
- Status text shows "Meeting in progress" with elapsed time

### Overlay Changes
- Meeting mode overlay: distinct blue-tinted pill (vs. current dark pill for dictation)
- Shows running timer: "Meeting — 03:42"
- Pulsing animation continues to indicate active recording

### Language
- Reuses the existing menu bar language selector (German/English)
- Selected language at meeting start applies to both STT and LLM summarization

## Audio & Transcription Pipeline

1. User clicks **"Start Meeting"** in menu bar
2. AVFoundation audio engine starts (reusing existing infrastructure)
3. Audio captured continuously, chunked into ~30-second segments
4. Each chunk transcribed via faster-whisper in background thread
5. Raw transcript text appended to in-memory list
6. Timer updates in overlay every second
7. User clicks **"Stop Meeting"** in menu bar
8. All transcript chunks concatenated → sent to Ollama for summarization
9. LLM produces structured markdown document
10. File saved to `~/Documents/Talky/Meetings/YYYY-MM-DD_HH-MM_meeting.md`
11. File auto-opens in default macOS editor

## Document Output Format

```markdown
# Meeting Notes — March 11, 2026

## Summary
[2-3 sentence overview of what was discussed]

## Key Points
- [Bullet point organized by topic/theme]
- [...]

## Action Items
- [ ] [Action item if detected]
- [ ] [...]
```

## File Architecture

### New Files
| File | Responsibility |
|------|---------------|
| `tools/meeting_mode.py` | Meeting session lifecycle: start, chunk management, stop, save |
| `tools/meeting_llm.py` | Meeting-specific LLM prompts for summarization |

### Modified Files
| File | Changes |
|------|---------|
| `app.py` | Add Start/Stop Meeting menu item, meeting overlay state, timer display, mode-aware menu |
| `main.py` | Mode routing — disable dictation pipeline when meeting mode is active |
| `tools/core_audio.py` | Expose `record_continuous()` method that yields ~30s chunks |

## Storage

- **Location:** `~/Documents/Talky/Meetings/`
- **Naming:** `YYYY-MM-DD_HH-MM_meeting.md`
- **Auto-created:** Directory created on first meeting if it doesn't exist
- **Post-save:** File auto-opens in system default editor

## Deferred to v2

- **Speaker diarization** — identify and label different speakers (requires pyannote-audio)
- **Pause/resume** — v1 is start-or-stop only
- **Live summary preview** — only timer/chunk count shown during recording
- **Meeting-specific stats** — no separate stats tracking for meetings
- **Configurable save location** — hardcoded to ~/Documents/Talky/Meetings/
- **Audio file saving** — only text output, no .wav/.m4a saved
