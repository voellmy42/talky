# Onboarding Wizard Design

**Date:** 2026-03-11
**Status:** Approved

## Overview

Single-page checklist wizard that guides users through local setup and system permissions before the audio pipeline starts. Replaces the current hard `sys.exit(1)` on missing accessibility permissions.

## Decisions

- **UX**: Single-page checklist (not multi-step wizard)
- **Re-check**: Wizard re-appears on launch if dependencies are missing, even after previous completion
- **Lifecycle**: App stays alive showing wizard; no `sys.exit(1)`. Pipeline starts only after setup is complete.

## Architecture

### New File: `tools/core_config.py` — ConfigManager

- Reads/writes `~/.talky_config.json`
- Fields: `has_completed_setup` (bool), `setup_completed_at` (ISO timestamp)
- Methods: `load()`, `save()`, `is_setup_complete()`, `mark_setup_complete()`

### SetupWizard (in app.py)

- `NSWindow` subclass, centered, ~480x360, titled "Welcome to Talky"
- Checklist items with SF Symbol status indicators:
  1. **Ollama + Model**: Check running + `qwen2.5:3b` installed. "Install Model" button runs `ollama pull` in background.
  2. **Accessibility**: Check `AXIsProcessTrusted()`. "Open Settings" button opens macOS Accessibility prefs.
- "Complete Setup" button enabled only when all checks pass
- Periodic re-check timer (every 2s) for live status updates

### Startup Flow Changes

1. `main.py`: Check config + live deps at startup
2. `TalkyApp`: If setup incomplete → show wizard instead of starting pipeline
3. After wizard completes → start pipeline
4. `core_audio.py`: Remove `sys.exit(1)` accessibility block

### StatusBar Integration

- `set_setup_required(needed)` method
- Warning icon + "Setup Required" menu item when deps missing
- Menu item re-opens wizard

## Files Changed

| File | Change |
|------|--------|
| `tools/core_config.py` | NEW — ConfigManager |
| `app.py` | Add SetupWizard, modify TalkyApp startup |
| `main.py` | Config check, conditional pipeline start |
| `tools/core_audio.py` | Remove sys.exit(1) block |
