# One-button editing preview — Talky 2.2.0

This milestone adds selection editing using the existing hold/toggle shortcut.
Meeting hardening and migration remain separate work. Previous preview apps are
preserved; this build is `dist/one-button-preview/Talky.app`.

## Try it

Quit other Talky copies and open the new app. Existing ad-hoc signatures cannot
provide stable Accessibility approval across rebuilds; macOS may require granting
access to this exact build again. This preview targets Apple Silicon / macOS 26+.

1. Choose **Set Up / Load AI Editing…**, approve the approximately 2.28 GB download,
   and wait for **Local AI ready**. The 4B model is separate from the 1.7B polishing
   model; the smaller model was weak at German edits. No Ollama is needed for this.
2. In an editable Apple Notes document, type a disposable paragraph:
   “I wanted to reach out to ask whether you could possibly review these changes.”
3. Select the paragraph. Hold Fn, say “Make this shorter,” then release. The same
   § or Control+Shift+Space toggle also uses the selection-aware route.
4. Check **Editing selection · EN** before speaking. The edit replaces only the
   original selection if its app, window, field, UTF-16 range and text still match.
5. Clear the selection and hold the same button: **Dictating · EN** uses Fast
   dictation with no LLM generation.
6. Use **Copy Original Text** to recover the selected source or the destination's
   normal Undo after a replacement. **Copy Last Result** recovers an edit when
   focus changes. Neither recovery action auto-submits text.

Use **Speech Language** for recognition of the spoken request. Try “Mach das kürzer”
with German selected and an English source paragraph: the replacement should stay
English. Ask “Übersetze das ins Deutsche” to request translation explicitly. Try the
same flows in Codex's editable prompt input after Apple Notes.

## Behavior and limits

- No Fast/Polished choice in the main menu. No selection means Fast dictation;
  selected editable text means a voice-editing request.
- The mode/language overlay is larger, wraps longer status messages and uses a
  distinct editing color. AI editing has a persistent enable/disable control.
- Reading uses only explicitly selected text, never the full field or a simulated
  clipboard Copy. Secure, read-only or unreadable selections are not edited.
- A failed, cancelled, unchanged or incomplete edit does not paste anything.
  In particular, a spoken edit instruction cannot become a dictation fallback.
- The editor retains original and replacement text only in the existing in-memory
  recovery lifecycle. It never runs app actions described by the spoken request.
- Numeric values, weekdays, negation and time conditions have conservative bilingual
  guards. Some valid edits are rejected. Intentional factual changes are outside
  this preview. These guards cannot verify roles, tone, scope or complete meaning.
- The model can still produce poor translations or alter nuance. Inspect the result
  and recover the original when needed. This is not a production quality sign-off.
- Ordinary dictation statistics exclude edits. Meeting mode is unchanged: microphone
  capture and Ollama summaries. System audio, meeting lifecycle hardening and embedded
  summarization are not implemented in this milestone.

## Verification

94 deterministic tests pass across existing dictation/delivery regressions and new
selection/editing cases. They cover UTF-16 emoji ranges, secure/read-only/unreadable
fields, changed text at the same range, same-span AX values, original recovery,
cancellation, unchanged output, AI disable, factual guards and quote cleanup.

Native UI rendering and menu-state checks pass. A disposable native NSTextView
confirmed UTF-16 selection behavior and selected-text writability. External
Accessibility access from the execution host was not authorized, so live Notes
and Codex selection reading/replacement still requires manual validation with the
approved packaged app. Do not confuse mocked delivery checks with real app acceptance.

Real model checks include bilingual shortening, lists, translations, adversarial
selected text and system-generated English/German speech through persisted language
settings -> Whisper -> editor. No microphone recording or user-document paste was
used. Synthetic results and limitations are saved in [the benchmark report](benchmarks/one-button-2026-10-27.json).
The final 14-case run met 12 sets of basic fixture checks; two rewrites were rejected
by the protected-detail guard. Median model generation was approximately 0.59 seconds
on the M4 Pro. This excludes recognition and actual app delivery. Some accepted
translations remain awkward and can change nuance.
Basic fixture checks are not a measure of semantic accuracy.

## Reproduce

```bash
.venv-mlx/bin/python -m unittest test_talky_v2 test_sessions test_delivery test_mlx_formatter test_selection_editing -v
.venv-mlx/bin/python scripts/smoke_ui.py
.venv-mlx/bin/python scripts/install_ai_model.py --model qwen3-4b --root build/mlx-models
.venv-mlx/bin/python scripts/check_editing.py --model qwen3-4b --with-speech --output build/benchmarks/one-button-final.json
TALKY_DIST_PATH=dist/one-button-preview TALKY_BUILD_PATH=build/one-button-preview ./build.sh
dist/one-button-preview/Talky.app/Contents/MacOS/Talky --check-build
dist/one-button-preview/Talky.app/Contents/MacOS/Talky --check-ai-model --model-root "$PWD/build/mlx-models"
dist/one-button-preview/Talky.app/Contents/MacOS/Talky --check-ai-download --model-root "$PWD/build/one-button-download-check"
```

The packaged checks exercise Metal/TLS/resources, real offline formatting/editing
and a tiny verified HTTPS config download. Weights are not bundled in the app.
M1 memory/latency, real voices, mixed-language speech, live app delivery, sleep/wake
and managed-Mac validation remain release gates alongside stable signing/notarization.
