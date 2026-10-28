# Quiet native UI — Talky 2.3.0

Implemented and verified on 28 October 2026 on an M1 MacBook Pro, 16 GB RAM,
macOS 26.5.2. Installed at `/Applications/Talky.app`; original 2.2.0 build remains
in `dist/m1-preview`.

The HUD is now 344 × 60 points (previously 480 × 64), above the visible Dock area
on the pointer's screen when an interaction begins. Separate text and waveform
areas keep status changes from moving the window or colliding with text. The
nonactivating panel ignores mouse events and does not become the key window.

Eleven bounded bars use a latest-only RMS level while capture is active, with
65 ms attack / 220 ms release smoothing. Silence produces a flat baseline.
Processing has a slower traveling wave; success and recovery use static icons.
The main-thread 30 Hz timer exists only for visible animated states. Text and
window opacity transitions take 160–180 ms. Accessibility preference changes are
observed live; Reduce Motion produces a static presentation and Reduce Transparency
uses an opaque backdrop.

Appearance Preview is available from the welcome screen, menu and `--preview-ui`.
It labels synthetic input explicitly, offers seven states, a finite automatic
sequence and a reduced-motion switch. It does not initialize a dictation pipeline,
open the microphone, download models, read selections or deliver text. Normal voice
input takes priority over the in-app preview. Activity and language use submenus.

Verification:

- 98 unit/regression tests passed, including new RMS lifecycle and waveform bounds.
- Native AppKit checks passed for all states, changing waveform frames, geometry,
  nonactivation, reduced motion, hidden timer cleanup and rapid hide/show behavior.
- Reviewed rendered state previews under `build/ui-preview/`.
- Rebuilt arm64 bundle, verified its ad-hoc signature and passed packaged
  `--check-build` (Metal, native imports, TLS context and resources).
- Verified installed version 2.3.0 and opened the native preview from onboarding.
  Inspected the actual window and exercised state buttons, reduced motion and replay.

Live microphone response, dictation accuracy and cross-app paste were not tested.
Synthetic preview levels demonstrate visuals rather than speech performance.
