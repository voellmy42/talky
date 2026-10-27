# Embedded MLX-LM preview

Built on 27 October 2026. The dictation backend now runs an optional language model
inside Talky. Ollama remains required only for Meeting summaries. Fast remains the
default and never loads the optional LLM. Semantic rewriting, self-correction and
voice commands are not part of this preview.

## Try the app

Quit other Talky copies, then open `dist/mlx-preview/Talky.app`. The existing
`dist/session-preview/Talky.app` has been preserved. This is an ad-hoc signed
development app using the existing bundle identifier; macOS may require granting
Accessibility again to this exact build. Do not repeatedly rebuild during a
permission diagnosis.

Choose **Polished (local AI preview)**, then confirm the approximately 0.98 GB
model download. Alternatively use **Download / Load AI Model…** from the menu.
The menu shows download progress, cancel/retry, loading and readiness. Fast
cleanup is used while the AI is unavailable. Downloading public model files is
the only network step for embedded dictation; loading and inference use verified
local files and do not send audio or text off the Mac.

The optional model lives in `~/Library/Application Support/Talky/models/`, pinned
to `mlx-community/Qwen3-1.7B-4bit` revision
`3b1b1768f8f8cf8351c712464f906e86c2b8269e`. It unloads when Fast is selected or
after five idle minutes. A later Polished request falls back while the model
reloads asynchronously. Installation retries reuse complete verified staging
files. Incomplete files are never loaded. Model licenses are documented in
[AI-MODELS.md](../packaging/AI-MODELS.md).

## What changed

- One worker owns local model loading, synthetic warmup, generation and unloading.
  A shared GPU lock serializes this work with Whisper, including meeting chunks.
- Thinking is explicitly disabled through the tokenizer chat template. Each
  request has independent context; no previous dictation is supplied to the model.
- Generation streams into an internal buffer, not the destination field. Only a
  complete result that passes the restricted edit policy can be pasted.
- Cancellation reaches the generation loop as well as session delivery. Deadlines
  include queue time and final cleanup; they cannot interrupt a GPU kernel already
  in flight. The app stays busy until that work drains.
- Missing models, failed loads, rejected edits, output limits and deadlines return
  Fast cleanup, with the fallback reason shown after paste. Raw text remains
  recoverable under the existing session rules.
- After the first AI load request, a lightweight available-memory monitor samples
  every ten seconds. Below 1 GiB available it pauses AI, stops generation between
  steps and unloads weights on the worker. Reload is allowed after 2 GiB becomes
  available. This heuristic needs device testing; it is not a hard OOM guarantee.
- The guard now preserves German “um” and technical punctuation in paths, filenames,
  CLI flags and comparison operators. It still cannot prove unchanged meaning.

The preview uses Python 3.12.14, MLX 0.32.4, MLX-LM 0.32.2 and MLX-Whisper 0.4.3.
The resolved MLX wheels require macOS 26 and Apple Silicon. See
`requirements-mlx.in` for direct dependencies and `requirements-mlx.lock.txt` for
the complete tested set. The previous `.venv` and preview app were not upgraded.

## Measured results

One M4 Pro with 24 GB RAM, macOS 26.6.2; Whisper Small resident. These measurements
cover formatting synthetic text, not recognition or release-to-paste latency.

| 60 short cases | Qwen3 1.7B, 4-bit | Qwen3 4B, 4-bit |
| --- | ---: | ---: |
| Median complete-result time | 0.141 s | 0.328 s |
| 95th percentile | 0.179 s | 0.445 s |
| Load, integrity check and warmup | 2.60 s | 2.77 s |
| Accepted by edit guard | 48/60 | 49/60 |
| Fast fallback | 12/60 | 11/60 |
| Output different from Fast | 21/60 | 33/60 |
| Exact reference formatting match | 13/60 | 23/60 |
| Peak MLX allocation, including Whisper | 1.70 GB | 2.99 GB |

Fast's median text-cleanup time was approximately 0.006–0.007 milliseconds.
Six longer smoke cases took approximately 0.76 s median / 1.06 s maximum for 1.7B,
and 1.55 s median / 2.43 s maximum for 4B. The smaller model fell back in four of
those cases; the larger model passed the guard in all six but changed only two
outputs relative to Fast. Long-case timing briefly overlapped packaged verification
and is approximate, not a controlled latency claim.

The 4B model matches more formatting targets, but it also needs more memory and
has not been evaluated on M1. Keep 1.7B as an explicit small-model preview, rather
than promoting either candidate as a production default. Passing the guard or
changing text is not proof of useful formatting. Both models miss punctuation
and sometimes propose edits that the guard rejects. Exact-reference matching is
strict and can reject other valid punctuation. Delivered fixtures showed no
restricted-policy violations; this is not a semantic accuracy guarantee.

The fixture split was inspected during development. A fresh bilingual set and
human correction-effort evaluation are needed for release. Ollama was not running,
so no real Ollama latency comparison was made. Raw synthetic outputs and timings
are in [the benchmark report](benchmarks/m4-pro-2026-10-27.json).

## Validation

65 regression tests, native UI menu-state checks, dependency consistency, shell
syntax and diff checks pass. The packaged app passes Metal/resource checks and
real offline model/tokenizer/generation checks. Both the new app and preserved
session preview pass deep/strict code-signature verification. No microphone
recording or real destination paste was used for these checks.

## Reproduce

```bash
python3.12 -m venv .venv-mlx
.venv-mlx/bin/python -m pip install -r requirements-mlx.lock.txt
.venv-mlx/bin/python -m unittest test_talky_v2 test_sessions test_delivery test_mlx_formatter -v
.venv-mlx/bin/python scripts/smoke_ui.py

# Explicit download into a development-only directory, preserving app preferences.
.venv-mlx/bin/python scripts/install_ai_model.py --root build/mlx-models --model qwen3-1.7b
.venv-mlx/bin/python scripts/install_ai_model.py --root build/mlx-models --model qwen3-4b

# Benchmarks force offline model loading; Whisper must already be cached.
.venv-mlx/bin/python scripts/benchmark_polishing.py --root build/mlx-models --model qwen3-1.7b --with-whisper --output build/benchmarks/qwen3-1.7b.json
.venv-mlx/bin/python scripts/benchmark_polishing.py --root build/mlx-models --model qwen3-4b --with-whisper --output build/benchmarks/qwen3-4b.json

TALKY_DIST_PATH=dist/mlx-preview TALKY_BUILD_PATH=build/mlx-preview ./build.sh
dist/mlx-preview/Talky.app/Contents/MacOS/Talky --check-build
dist/mlx-preview/Talky.app/Contents/MacOS/Talky --check-ai-model --model-root "$PWD/build/mlx-models"
```

Use `--fixtures tests/fixtures/polishing-long-v1.json --budget 4` for the longer
smoke cases. GPU/native UI checks need a logged-in desktop with Metal access.
The offline check uses the installed pinned model and performs real inference
without microphone capture, focus inspection or paste. Weights are outside the
approximately 1.1 GB app bundle. No new preview was launched for actual dictation
during implementation.

## Remaining release gates

M1 and managed-Mac validation, real speech/correction effort, memory pressure,
battery and sleep/wake tests, and real-app delivery checks remain. Deadline checks
and low-memory eviction are cooperative. Available-memory thresholds need validation
under real pressure before broad use.
Developer ID signing, stable permissions across builds and notarization also remain.
Meeting summarization still needs a separate migration before Ollama can be removed
from the entire product. Keep Fast as the default until the quality and device
gates in the implementation plan are met.
