# Fun Mode Implementation Plan

**Goal:** Add a selectable, activity-only walkie-talkie companion to Talky.

**Architecture:** Keep one OverlayWindow controller and its lifecycle. Add a native
FunCharacter renderer whose layers share that controller's audio smoothing and timer.
Persist the app choice through ConfigManager; preview switches its own renderer
without writing preferences. Standard remains the migration default.

**Tech Stack:** Python 3.12, AppKit, Core Animation layers, existing preference JSON.

The referenced superpowers:executing-plans skill is unavailable; execute the following
tasks directly with the available tooling after @brainstorming approval.

### Task 1: Preferences and emotion mapping
Files: tools/core_config.py, tools/ui_fun.py, test_ui_overlay.py.
Add validated get/set appearance; add a pure emote/hint mapping and regression checks
for default, persistence, bad values, cancellation and recovery.

### Task 2: Native character and style routing
Files: tools/ui_fun.py, tools/ui_overlay.py.
Build bounded gold body, arms, feet, antenna and green pixel display using layers.
Separate label, face, waveform and hint regions. Add set_style while preserving
show/hide/meeting interfaces. Share the existing 30 Hz timer, audio smoothing and
accessibility observer. Success may animate briefly; hidden and reduced states stop.

### Task 3: App and preview controls
Files: app.py, tools/ui_preview.py.
Add Appearance submenu and persistence. Initialize overlay with saved style. Add
Standard/Fun preview buttons with no preference writes. Share onboarding and menu
preview; close it before real activity and cancel stale notice timers when opening.

### Task 4: Verification and delivery
Files: scripts/smoke_ui.py, README.md, talky.spec, docs/fun-mode.md.
Extend native checks to both styles, pixel regions, state transitions, nonactivation,
reduced motion, rapid hide/show and repeated style switches. Render and inspect each
emote. Run unittest test_talky_v2 test_sessions test_delivery test_mlx_formatter
test_selection_editing test_ui_overlay. Build Talky 2.4.0, run packaged --check-build,
install, verify signature and use the actual appearance preview. Commit final work.
