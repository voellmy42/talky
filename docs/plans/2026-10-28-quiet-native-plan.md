# Quiet Native UI Implementation Plan

> Execute each task in order using the available native Python/AppKit tooling. The
> referenced superpowers:executing-plans skill is not installed in this workspace.

**Goal:** Make Talky compact and fluid, with a safe speech-free appearance preview.

**Architecture:** Move the overlay into tools/ui_overlay.py, preserving its existing
public entry points. Poll a latest-only audio level from a main-thread animation
timer; never queue per-buffer UI callbacks. A separate preview controller drives an
independent overlay with simulated levels and never starts the dictation pipeline.

**Tech Stack:** Python 3.12, PyObjC/AppKit, Core Animation, existing numpy audio path.

### Task 1: Meter and overlay (tools/core_audio.py, tools/ui_overlay.py, app.py)
1. Add bounded RMS level state while capture is active and reset on stop.
2. Replace the old overlay with fixed lanes, native material, semantic icons,
   compact labels, waveform and a visible-only timer. Preserve meeting entry points.
3. Wire the level getter in main.py without changing capture/session behavior.
4. Add focused tests for inactive input, active input and stop/reset behavior.

### Task 2: Appearance preview (tools/ui_preview.py, app.py, main.py)
1. Build native state controls and simulated-level playback on a separate overlay.
2. Add the menu action and --preview-ui entry point; allow preview before setup.
3. Provide reduced-motion simulation and teardown timers/windows on close.
4. Exercise transitions, layout bounds, nonactivation and hidden timer cleanup.

### Task 3: Menu and welcome (app.py)
1. Group existing statistics and language items into native submenus.
2. Shorten welcome text, enable wrapping, refine spacing and add preview access.
3. Retain all setup permissions and current menu enabled-state behavior.

### Task 4: Verify and deliver
1. Run .venv-mlx/bin/python -m unittest test_talky_v2 test_sessions test_delivery
   test_mlx_formatter test_selection_editing test_ui_overlay -v (all pass).
2. Run scripts/smoke_ui.py, inspect native screenshots and preview transitions.
3. Build via TALKY_DIST_PATH=dist/quiet-native TALKY_BUILD_PATH=build/quiet-native
   ./build.sh; run packaged --check-build and preview before installation.
4. Install the verified app, launch appearance preview and document speech limits.
