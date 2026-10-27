# Talky: review for the next macOS version

Reviewed 27 October 2026. Scope: repository source and existing local changes;
no microphone capture or real-app injection was performed.

## Baselines

- GitHub macOS: `voellmy42/talky`, main `f5bffccc69bd399ff0e646c1213beb87016a5e62`.
- GitHub Omarchy: `voellmy42/talky-omarchy`, main `2983bc4f97c1cf482f32e44902106e7dcccd6603`.
- Local macOS checkout: same HEAD, with substantial uncommitted Talky 2 changes
  across 14 tracked files plus `test_talky_v2.py`. Preserve these changes.

The Omarchy repository is a separate Linux implementation built around Voxtype,
GTK4, Hyprland, Vulkan and llama.cpp. Its interaction design and controller logic
are useful references; its desktop integration is not a macOS drop-in.

## Comparison

| Area | GitHub macOS | Local macOS changes | Omarchy |
| --- | --- | --- | --- |
| Recognition | MLX Whisper small, after release | Same | Resident Voxtype/Whisper; eager processing off by default |
| Cleanup | Ollama on every dictation; 60s request timeout | Fast deterministic default; optional Ollama with 20s request timeout | Resident Qwen cleanup; 2.5s configured timeout; guarded fallback |
| Microphone | Engine starts per dictation | Persistent capture with 500ms rolling pre-roll | Explicit start/stop through engine |
| Destination | Current focus when paste is sent | Current focus when paste is sent | Original window identity checked before paste |
| Cancellation | No dictation cancel path found | No dictation cancel path found | Cancel invalidates pending results |
| Recovery of text | No last-transcript review flow found | Same | Latest raw/final text and preview |
| Language | Manual English/German | Remembered English/German | Auto/English/German and vocabulary hints |
| Measurement | Aggregate processing duration | Stage timings | Stage timings and offline benchmark; offline runs include process startup |

Sources: [Mac pipeline](https://github.com/voellmy42/talky/blob/f5bffccc69bd399ff0e646c1213beb87016a5e62/main.py),
[Omarchy controller](https://github.com/voellmy42/talky-omarchy/blob/2983bc4f97c1cf482f32e44902106e7dcccd6603/src/talky/service.py),
[Omarchy formatter](https://github.com/voellmy42/talky-omarchy/blob/2983bc4f97c1cf482f32e44902106e7dcccd6603/src/talky/formatter.py),
[Omarchy output](https://github.com/voellmy42/talky-omarchy/blob/2983bc4f97c1cf482f32e44902106e7dcccd6603/src/talky/desktop.py).

## Highest-priority findings

1. **Wrong-destination paste is possible on Mac.** Neither Mac pipeline captures
   the starting application/window/field. If focus changes during recognition or
   cleanup, output goes to the newly focused destination. Capture a destination
   at start and recheck immediately before delivery. If identity cannot be
   established, retain text for explicit copy/retry. Window identity alone does
   not protect against switching fields or browser tabs inside a window.

2. **Processing blocks the next Mac dictation.** The pipeline records, transcribes,
   formats and delivers serially. Locally, `_dictation_session_active` is false
   during processing, so new Fn presses are ignored. Use explicit session states
   and cancellation tokens. Either clearly signal busy or support a bounded next
   capture without allowing late output to reach another destination.

3. **AI cleanup can change agent instructions.** Mac polished mode accepts any
   nonempty model output. Omarchy adds useful guards, but its own roadmap documents
   that reordered roles or negation scope can still pass. Default to faithful
   transcription/minimal cleanup, retain raw text, and evaluate numbers, negations,
   technical names and dictated instructions. Regex cleanup also needs evaluation:
   words such as English “Um” in technical material can be meaningful.

4. **Ollama is still coupled to Mac startup.** Local fast mode avoids inference,
   but setup still checks for Gemma and normal startup still launches Ollama.
   Basic dictation should become ready independently. Initialize optional cleanup
   only when needed and avoid controlling a shared Ollama application's lifecycle.

5. **The displayed Mac latency omits part of the interaction.** Local timing starts
   after capture returns and the stop chime is dispatched. It excludes key-release
   handling, including the 400ms double-tap wait on short taps. Injection success
   means paste events were sent, not that the destination accepted text. Measure
   physical release/stop to paste dispatch separately from per-stage work.

6. **Instant capture has an idle-cost tradeoff.** Local pre-roll keeps the microphone
   active and resamples while idle. It may help capture first words, but battery,
   idle CPU, headset behavior and device-switch recovery need measurement. Make
   capture policy visible and deliberate; do not conflate resident models with
   an active microphone.

7. **Failed delivery needs recoverable text.** Current Mac fallback uses simulated
   typing, with no user-facing retained transcript if it fails. Keep the latest
   result in memory and expose Copy/Retry; validate Unicode and multiline prompts.

## Recommended direction

Use the local Mac version as the immediate baseline and bring over the Omarchy
session model: destination tracking, cancellation, preview/recovery, vocabulary,
and clear recording/processing/delivery outcomes. Keep native macOS integration
and the existing MLX recognizer for the first measured iteration. Source review
does not establish that a language rewrite or another model will be faster.

The primary interaction should be: focus an agent input, hold a configurable
shortcut, speak, release, receive faithful text. Offer toggle recording and a
separate cancel shortcut. Keep automatic submission off by default. Expose
optional polishing separately, and keep meeting summarization outside the
critical dictation path.

If voice-driven app switching and action execution are wanted, define those as
an explicit command mode with its own routing and feedback. A dictated sentence
such as “delete the old files” must remain text in ordinary dictation mode.

## Implementation order and acceptance evidence

1. Session controller, destination checks, cancellation and last-result recovery.
2. Remove Ollama from basic setup/readiness; improve microphone/device error states.
3. Measure the current fast path on the target Mac before selecting recognition
   models or investing in incremental recognition during speech.
4. Evaluate optional cleanup and language/vocabulary behavior on representative
   English, German and Swiss German speech.
5. Finish packaging, login startup, shortcut configuration and app compatibility.

Report cold startup and warm p50/p95 release-to-paste-dispatch by utterance length,
plus first-word loss, correction effort, failed delivery, idle CPU/memory and
battery impact. The existing constitution's sub-2s goal is a target, not a result.
Test the actual agent apps, terminals and browser inputs, including switching
windows during processing, rapid successive dictations, cancellation, clipboard
changes, sleep/wake and headset reconnects.

## Validation performed

Ran `.venv/bin/python -m unittest test_talky_v2 -v`: all eight tests passed.
These cover configuration, deterministic cleanup, mocked polished cleanup, ring
buffer behavior, mocked clipboard restoration and stats. They do not establish
speech accuracy, real paste acceptance or latency. The environment also emitted
a urllib3/LibreSSL compatibility warning.

No application source was modified as part of this review.

## Confirmed product scope

- Personal MacBook M1 and work MacBook M4 must both be supported. Use the M1
  as the performance baseline and validate both machines; RAM is not yet known.
- Primary destinations: Codex, Slack, Chrome, Apple Notes, Raycast and Notion.
  Validate native and browser text inputs, multiline prompts, Unicode, app/window
  switching and transient Raycast inputs. Browser tab changes require particular
  attention because window identity alone cannot identify the destination field.
- The primary purpose is dictation into the focused application. Voice-driven
  application control and agent switching are outside the initial scope.
- Sharing with work colleagues is a desired outcome. Plan a self-contained,
  signed and notarized Apple Silicon app, explicit model setup, clear permission
  onboarding, versioned updates and no requirement for colleagues to install
  Python or use a terminal. Work-device installation policies require validation
  on the actual managed machines.
- Preserve local processing as the existing default. Basic dictation should not
  require a separate Ollama installation. Select model defaults only after
  measuring representative speech and memory use on the M1.
