# macOS session preview

Built 27 October 2026 on top of the existing local Talky 2 changes.

## Try it

Open `dist/session-preview/Talky.app` after quitting any other Talky instance.
The existing single-instance lock is shared with older builds. This preview uses
the existing Talky preferences, stats and local model cache.

1. Complete microphone and Accessibility setup if requested. Rebuilding the
   ad-hoc signed app may require granting Accessibility permission again.
2. Wait for speech-model loading/warmup. A missing Whisper model downloads on
   first startup; basic dictation does not require Ollama.
3. Focus an input in Codex, Slack, Chrome, Notes, Raycast or Notion. Hold Fn,
   speak after the start chime and release. Double-tap Fn for toggle recording.
   In version 2.0.2, press § to start/finish or use Menu > Start / Finish Dictation.
   Menu > Dictation Shortcut also offers Control+Shift+Space and Fn only; settings
   apply immediately and are saved. F8 was removed because it can act as a media key.
4. Press Esc to cancel. The key is observed without suppressing its normal action
   in the foreground app. In-flight inference finishes before another recording
   is accepted, and cancelled output is discarded.
5. If the destination changed or is unsupported, choose Copy Last Dictation from
   the Talky menu and paste where wanted. Copy Original Transcript and Clear Last
   Dictation are available in the same menu. No Enter/submit event is sent.

In version 2.0.1 the microphone stays off while idle, opens only for an explicit
recording and is released on stop/cancel. Idle pre-roll is disabled.
Dictation recordings and recovered transcripts are not saved
to disk; explicit clipboard copies may be retained by clipboard managers.

## Implemented

- One session owns destination, language and formatting choice from recording start.
- Cancellation invalidates pending results at recognition, formatting and paste dispatch.
- Delivery checks application PID, Accessibility window and text element, and
  caret/selection where exposed. It rechecks immediately before sending paste.
- Unknown destinations and changed focus retain text without replacing the clipboard.
- Clipboard generation/change checks protect against intervening copies; failed
  paste no longer falls back to simulated character typing.
- Optional AI cleanup uses a 2.5-second HTTP timeout and restricted edit validation.
- Basic setup checks microphone and Accessibility access and never controls Ollama.
- Stage timings include a release/stop timestamp before the double-tap wait.
- Shutdown stops capture and the event tap; startup failures report an error state.
- Source includes a native UI smoke check and a packaged `--check-build` path
  that exercises imports/resources/Metal without recording, models or input injection.

## Verification and remaining limits

40 deterministic tests pass for lifecycle, cancellation races, cleanup guards,
focus/clipboard handling, capture controls, recovery, settings and status feedback.
Tests also verify idle startup never touches input hardware, stopping removes the
input tap, the configured shortcut toggles capture, and the Accessibility-authorized keyboard callback
only queues controls rather than doing focus/audio work. These are regression
checks; real Fn/§ delivery on the user's keyboard still needs verification.
The shortcut regression checks cover Unicode-based layout matching, repeat and
key-up consumption, preserving unrelated/modifier keys, and changing settings live.
Native menu-state checks and setup/HUD rendering also passed without microphone
capture, models or paste.

The final arm64 app built successfully (approximately 702MB), passed deep/strict
code-signature verification, and passed its packaged `--check-build` test for
native imports, resources and Metal shader execution. No recording, model
download or real input injection was used in that packaged check.

This is a development preview. Destination checks depend on app Accessibility
support and cannot make focus changes atomic with an OS input event. Some browser
fields or reused elements may need app-specific handling. Paste dispatch does
not prove acceptance. The fixed clipboard restore delay still needs testing in
real destination apps. The restricted cleanup guard is not a semantic guarantee.

No real speech/latency, battery, headset, sleep/wake or M1/M4 comparison was run.
The current build environment uses Python 3.9.6 and emits an existing
urllib3/LibreSSL compatibility warning; a supported Python/toolchain migration
and dependency/package-size cleanup remain necessary for a distributable release.
Developer ID signing, notarization, fresh-machine model setup and managed-work-Mac
validation remain before sharing this broadly with colleagues.

### Confirmed Accessibility setup failure

macOS TCC diagnostics confirmed that the saved Accessibility approval referenced
an earlier ad-hoc build's code hash, while the running 2.0.1 binary had a different
hash. TCC rejected it with “Failed to match existing code requirement” even though
the Settings entry could appear enabled. No valid code-signing identity was
available on the development machine at diagnosis time.

For the frozen preview, quit Talky, reset only its stale approval with
`tccutil reset Accessibility com.antigravity.talky`, add the exact
`dist/session-preview/Talky.app` in Accessibility, enable it, and relaunch that
same unchanged app. This reset affects Talky copies sharing that identifier.
Do not rebuild during permission diagnosis. A stable signing identity and a
distinct development bundle identifier are needed to avoid repeating this cycle
through future updates and collisions with the older installed Talky.

## Reproduce

```bash
.venv/bin/python -m unittest test_talky_v2 test_sessions test_delivery -v
.venv/bin/python scripts/smoke_ui.py
TALKY_DIST_PATH=dist/session-preview TALKY_BUILD_PATH=build/session-preview ./build.sh
dist/session-preview/Talky.app/Contents/MacOS/Talky --check-build
```

MLX packaging and the packaged Metal check require GPU access. A restricted
sandbox may hide Metal devices and cause MLX's native initialization to abort.
