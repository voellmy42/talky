# Embed MLX-LM in Talky

Date: 27 October 2026. Status: embedded preview implemented; release validation remains.

Implementation results and remaining gates: [MLX preview](../mlx-preview.md).
The implementation stays opt-in and labeled as a preview. M1, managed-device,
real speech/correction-effort and distribution validation are not complete.

Baseline: [Talky PR #1](https://github.com/voellmy42/talky/pull/1), commit
`7711f920df135745720534155e39e4c3c354b0a1`.

## Outcome and scope

Make Polished dictation work inside Talky without a separate Ollama installation
or service. Keep Fast mode independent of the language model. All inference stays
local; only explicit model installation needs network access. First release:
punctuation, paragraph/list formatting and conservative hesitation removal.
Semantic self-correction, grammar rewriting and voice transformations follow only
after separate evaluation and an explicit editing policy.

This first migration does not remove Ollama from Meeting mode. Its long-context
summarization needs a separate migration and evaluation. Do not describe the whole
app as Ollama-free until that work is complete.

## Findings in the current implementation

- `tools/core_llm.py` calls Ollama with `gemma4:latest`, a 2.5-second HTTP timeout,
  no explicit thinking switch, and a 2,048-token Gemma budget. A maximum token
  budget is not a fixed amount of work, and an HTTP timeout does not prove server
  inference stopped.
- `preserves_dictation` accepts only source-order words, case/punctuation changes
  and a limited set of hesitation deletions. It rejects grammar rewrites and
  semantic corrections. Keep that policy initially; change the UI description to
  match it. Existing README claims of deeper grammar cleanup overstate this policy.
- `DictationController` already owns session identity, cancellation and recovery.
  Preserve its checks before formatting and delivery.
- The existing environment is Python 3.9.6 / MLX 0.29.3. Current MLX-LM main declares
  Python >=3.11 and MLX >=0.32.3 on macOS. Resolve a released, compatible dependency
  set in an isolated environment, rather than upgrading the working preview in place.

## Architecture

Keep the existing path: capture -> Whisper -> formatter -> destination checks -> paste.

Introduce a formatter service with deterministic Fast cleanup and an optional
embedded MLX backend. The backend uses MLX-LM's Python API; no localhost HTTP server
or externally installed CLI. One dedicated inference worker owns model loading,
warmup, generation and unloading. Initially serialize Whisper and LLM work to
avoid unmeasured GPU/memory contention. Never load or generate on the Cocoa thread
or keyboard callback. Concurrent meeting work needs the same inference scheduling
or an explicit busy state.

Proposed internal request/result schema, defined before implementation:

```text
FormatRequest:
  session_generation: int
  text: str
  language: "en" | "de"
  policy: "faithful"
  deadline_monotonic: float
FormatResult:
  text: str
  outcome: "formatted" | "fallback" | "cancelled"
  reason: "accepted" | "not_ready" | "deadline" | "length_limit" |
          "validation" | "model_error" | "cancelled"
  model_revision: str | null
  load_seconds: float
  generation_seconds: float
```

Requests and results remain in memory. Cancellation is an in-process token tied
to the session generation. Logs contain timings, model identity and reason codes,
not transcripts. Adapt the existing `format_text` entry point while moving result
metadata into the controller; retain its destination and last-result behavior.

## Model selection and benchmark

Initial candidates, not final product defaults:

- `mlx-community/Qwen3-1.7B-4bit`: smaller candidate.
- `mlx-community/Qwen3-4B-4bit`: quality comparison if memory permits.

Use `enable_thinking=False` in the model's chat template and verify the resulting
prompt and output. Pin the chosen model revision and runtime versions. Verify
license/attribution and tokenizer support before shipping. Do not select by model
size or token throughput alone. The candidates are starting points, not a claim
that they are the best current models.

Create a versioned evaluation set of at least 60 synthetic or explicitly approved
transcripts spanning English, German and mixed technical speech. Include questions,
negations, numbers/dates, filenames, identifiers, lists, corrections and text that
looks like instructions to the formatter. Use a held-out portion for the final
comparison. Track both useful formatting accepted and unwanted meaning changes;
a formatter that always returns the original must not appear to win.

Measure cold load, first-token and full-result time, p50/p95 by utterance length,
fallback rate, peak process/Metal memory and memory pressure with Whisper resident.
Compare against Fast and current Ollama. To isolate runtime effects, compare an
equivalent model/quantization through Ollama where feasible, with thinking off.
Record M1/M4 RAM and macOS versions; test with normal work apps open. Select the
smallest model that meets quality and latency goals. No download or benchmark has
been performed as part of this plan.

## Loading, installation and memory

- Fast startup never imports/loads the optional LLM or downloads its weights.
- Selecting Polished offers a one-time model download with size, progress, cancel
  and retry. Store verified weights under `~/Library/Application Support/Talky/models/`.
  Stage incomplete downloads separately and activate atomically. Use an explicit
  pinned manifest; loading an installed model must not silently contact the Hub.
- States: not installed, downloading, loading, ready, failed. When unavailable,
  deliver deterministic Fast cleanup and show a brief reason; do not silently
  wait through a download during dictation.
- Load and warm once when Polished is enabled. Keep weights warm while in use,
  with a configurable-in-code idle eviction interval selected after measurement.
  Unload when disabled or under supported memory-pressure handling, after active
  work stops. Release request-specific caches; retain at most the static prompt
  prefix cache in memory, never previous dictation context.
- The packaged app includes the runtime. Model weights are installed separately
  on first opt-in; a single app installation still has a model setup step.

## Generation, fallback and cancellation

Use `stream_generate` internally to inspect cancellation/deadline between output
steps. Buffer output until complete and validated; never stream partial edits
into the user's field. Set token limits from input token count and a bounded
formatting allowance. If the input plus output cannot fit, fall back without
truncating. A token-limit finish is not a completed successful edit.

Start with a proposed warm-generation deadline of 1.5 seconds for short inputs
(up to 80 words), evaluated separately from speech recognition. Tune only against
the benchmark; it is a goal, not a measured promise. Longer dictation needs its own
budget and latency reporting. Cold model loading is shown as readiness work.

On deadline, incomplete output, load failure or rejected edit, use Fast cleanup.
Retain the original transcript. On Escape, discard both candidate and session
output. Check cancellation again before delivery. Closing the generator must
release per-request state. A deadline cannot interrupt an already running GPU
kernel: remain busy until work has actually stopped, with no overlapping retries.
If experiments show unbounded stalls, move this worker into a bundled helper
process for termination/restart; that still requires no separate user tool.

Keep the current restricted validator for the first migration, including tests
for misleading punctuation, identifiers and numbers. It is not proof of unchanged
meaning. Future self-correction needs a distinct policy and corpus; future
Transform mode needs a separate explicit shortcut and permits rewriting. A model
adapter alone does not implement those capabilities.

## Implementation sequence and acceptance

1. **Dependency baseline.** Create an isolated Python 3.11+ environment, resolve
   released MLX/MLX-Whisper/MLX-LM/PyObjC/PyInstaller versions, and lock the tested
   set. Verify current 40 tests, native UI, speech-model warmup and packaged Metal
   execution. Document minimum macOS support. Preserve the existing preview binary.
2. **Model experiment.** Add a benchmark script and evaluation fixtures, then run
   the two candidates on M1 and M4. Report quality, full-result latency, fallbacks
   and memory. If neither is useful within the budget, revise model/policy before
   product integration. Do not weaken validation just to improve acceptance rate.
3. **Backend and lifecycle.** Add `tools/core_mlx_llm.py`, adapt `core_llm.py`,
   `core_session.py` and `main.py`, and add install/readiness settings in
   `core_config.py` and `app.py`. Fast remains default. Keep Ollama temporarily as
   a developer comparison backend; expose embedded MLX as the normal Polished path
   only once acceptance criteria pass.
4. **Packaging and regression.** Update `talky.spec`, dependency metadata, build
   checks, README and cleaner SOP. Verify tokenizer/model loading from local paths
   in a packaged app with network disconnected. Cover missing/corrupt downloads,
   deadlines, length limits, cancellation, shutdown, worker errors, focus changes
   and clipboard races with meaningful tests. Use real models for quality claims.
5. **Rollout.** Validate real dictation into Codex, Slack, Chrome, Notes, Raycast
   and Notion; test sleep/wake and memory pressure. Compare release-to-paste latency
   and correction effort with the current preview. Ship as a separate PR; handle
   stable signing/notarization before distributing to colleagues.

Required gates: existing lifecycle/delivery tests pass; cancelled/partial output
is never pasted; no critical number/negation/role changes in the held-out corpus;
useful formatting succeeds often enough to justify AI (report numerator and
denominator); Fast has no meaningful startup/latency regression; warm Polished
meets its agreed latency budget on M1 without sustained memory pressure. Corpus
success is evidence, not a general semantic guarantee. Exact memory and acceptance
thresholds are set from the baseline experiment before choosing a default.

## Sources checked on 27 October 2026

- [MLX-LM Python generation and caching](https://github.com/ml-explore/mlx-lm/blob/main/README.md).
- [Current upstream dependency requirements](https://github.com/ml-explore/mlx-lm/blob/main/pyproject.toml).
- [MLX-LM streaming implementation](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/generate.py).
- [Qwen3 thinking controls](https://huggingface.co/Qwen/Qwen3-1.7B).
- [1.7B MLX model card](https://huggingface.co/mlx-community/Qwen3-1.7B-4bit)
  and [4B MLX model card](https://huggingface.co/mlx-community/Qwen3-4B-4bit).

Upstream main is mutable; implementation must pin and recheck released versions.
