# Fun appearance — Talky 2.4.0

Implemented on 28 October 2026, Apple M1 / 16 GB / macOS 26.5.2.

## Choose a style

Use **Talky menu → Appearance → Standard / Fun · Walkie-talkie**. Standard remains
the default for existing and new preferences. The menu choice persists between
launches. Appearance Preview offers independent style buttons; those do not save a
preference. Both preview entry points reuse one controller, and normal activity
closes the preview before showing the real overlay.

## Companion behavior

Fun mode is native AppKit/Core Animation artwork: a warm gold walkie-talkie with
mittens, feet, antenna, speaker grille and a green pixel monitor. Its fixed
260 × 200 point frame includes every limb. Separate monitor rows hold a readable
status, pixel face, waveform and action hint. Text never moves with the antenna.

- Listening: curious eyes, smile and an input-driven waveform.
- Selection editing: concentrated eyes and the same input-driven waveform.
- Processing: thinking eyes, subtle glances and a traveling waveform.
- Success: happy eyes and a smile, green light and a brief antenna celebration.
- Recovery: concerned face, “Saved for you” and “Copy Last Result”.
- Cancellation: calm expression and a cancellation acknowledgment.
- Meeting: attentive expression and elapsed time.

No persistent idle pet, autonomous movement, new sounds or background audio capture.
The existing session/result lifecycle controls visibility. Motion uses the existing
30 Hz visible-only timer; success animation stops after 750 ms. Blink and antenna
movement stay within the character's frame. Reduce Motion freezes decoration and
waveform. The screen is opaque and high contrast. Full original status messages
remain available in the menu and accessibility label.

## Source verification

- All 101 unit/regression tests pass, including appearance default, persistence,
  invalid settings, emotion mapping, audio-level lifecycle and waveform bounds.
- Native checks pass for eight states in each style, waveform bounds, changing
  frames, focus preservation, reduced motion, finite celebration, hidden timer
  cleanup, rapid hide/show, repeated style changes and reopening the preview.
- A temporary preference file verified the app menu → saved choice → actual renderer
  connection; preview switching did not change saved preferences.
- Changing the style of a hidden preview does not show a companion or start its timer.
- Inspected rendered emotes under `build/ui-preview/fun-*.png`.

## Packaged verification

- Built and ad-hoc signed `dist/fun-mode/Talky.app`; packaged `--check-build` passed
  (Metal, native imports, TLS context and resources).
- Installed at `/Applications/Talky.app`, verified the strict/deep signature and
  version 2.4.0. Previous 2.3.0 bundle remains in `dist/quiet-native`.
- Confirmed the installed executable's archive includes the Fun, Standard and preview
  modules. Launched its `--preview-ui` entry point; process remained running without
  an error. This standalone preview intentionally does not start the speech pipeline.
- Installed-window automation could not be completed: the computer-use connection
  returned “Sky Computer Use native pipe startup failed”, including after a reset.
  Actual packaged window inspection and button interaction therefore remain a manual
  check; native source rendering and behavior checks above passed.

Live speech and cross-app paste are outside this visual-only validation.

## User validation

On 28 October 2026, the user reported that the updated app “works flawless on this
new machine” after installation on this M1. This is user-reported validation of the
installed experience; individual microphone, editing and paste scenarios were not
specified. The automated desktop-inspection limitation above remains recorded.
