# Onboarding Wizard v2 — Design

## Status: Pending approval

## Goal
Replace the current single-page checklist wizard with a two-page onboarding flow that introduces the app, highlights the privacy USP, and then guides setup.

## Architecture

### Page 1 — Welcome + USP
- **Window size:** 480×420 (taller than current 480×320 to fit logo)
- **Layout (top to bottom):**
  - Logo image (`talky-logo.jpg`, scaled to ~120×120, centered)
  - Title: "Welcome to Talky"
  - Subtitle: "Fast & accurate speech-to-text for your Mac."
  - USP block: brief privacy pitch — "Your voice never leaves your Mac. Talky uses a local AI model (Ollama) so your data stays 100% private."
  - "Get Started →" button (bottom-right)

### Page 2 — Setup Checklist
- Same window, content swapped (no new window created)
- **Layout (top to bottom):**
  - Title: "Setup Checklist"
  - Subtitle: "Talky needs a few things before it can run."
  - Row 1: Ollama + model check (existing logic)
  - Row 2: Accessibility permission check (existing logic)
  - "← Back" button (bottom-left) — returns to page 1
  - "Complete Setup" button (bottom-right, enabled when all checks pass)

### Implementation approach
- Keep `SetupWizard` class, refactor to manage two "pages" via showing/hiding NSView containers
- Page 1: `_welcome_view` (NSView containing logo, text, button)
- Page 2: `_checklist_view` (NSView containing existing checklist rows + buttons)
- Navigation: `_show_page(1)` / `_show_page(2)` toggles visibility
- Timer only starts when page 2 is visible, pauses on page 1
- Logo loaded via `NSImage.alloc().initWithContentsOfFile_()` with path resolved relative to `__file__`

## Files changed
- `app.py` — `SetupWizard` class rewrite (~lines 436-662)

## What stays the same
- `_SetupTarget` action target class
- All check logic (`_check_ollama`, `_check_accessibility`)
- All action logic (`_install_model`, `_open_accessibility`, `_complete`)
- `ConfigManager` integration
- Timer-based re-check mechanism
- Window properties (floating level, title bar style)
