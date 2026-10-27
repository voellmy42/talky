# Voice input and editing SOP

Fast mode uses `LLMFormatter.fast_cleanup` in `tools/core_llm.py`. It is the default
and must not load an LLM or make a network request.

The product uses `EmbeddedFormatter` for selection editing in `tools/core_mlx_llm.py`, with pinned
models installed by `tools/core_model_store.py`. `FormatRequest` and `FormatResult`
define the legacy polishing schema. `EditRequest` and `EditResult` define the separate editing schema. One worker owns model loading,
generation and unloading. Whisper and MLX-LM share `GPU_LOCK`; no model work runs
on Cocoa or shortcut callback threads.

Installation requires an explicit user action. Show size, progress, cancel and
retry. Verify hashes against the bundled manifest, stage incomplete files, and
activate only a verified complete model. Loading must use an existing local path,
local tokenizer files and no remote custom code. Never send dictation to a remote
service or log transcript content. Installation network traffic contains only
public model file requests.

Use the model chat template with thinking explicitly disabled. Keep prompts
independent between dictations; retain no per-request prompt cache. Warm the model
on synthetic input, release it when disabled and after five idle minutes, and
never load it solely for ordinary dictation. An explicitly enabled editor may
warm on startup. Model setup is separate from speech readiness.
After AI is first requested, sample available memory every ten seconds. Below
1 GiB, pause generation and queue weight eviction on the worker; allow a later
reload after 2 GiB becomes available. These thresholds are a development heuristic,
not proof against memory exhaustion. Stop the monitor on shutdown.

Ordinary voice input always uses deterministic Fast cleanup. The main UI no
longer offers Fast/Polished. AI selection editing is a persisted opt-in, migrating
the earlier explicit Polished preference. When enabled, its model can warm separately
from speech readiness. AI inference is used only for a selected-text edit.

Capture only AXSelectedText and its UTF-16 range from an editable non-secure field;
never read the entire field or simulate Copy to fetch it. Unreadable nonempty
selections must not silently become dictation. Bind source, destination and speech
language at recording start. Recheck the selected range AND exact text before paste.

Use the pinned 4-bit Qwen3-4B model for the editing preview. The smaller model was
not reliable enough for German editing. Separate quoted selection data from the
final editing instruction. Native local language identification gives an English
or German source-language hint; keep that language unless translation is requested.
The speech-language setting controls recognition, not the edit's output language.
Do not execute actions described by either input; return replacement text only.

Buffer model generation internally. Do not paste partial, length-limited, empty,
cancelled or invalid output. Accidental answer quotes may be removed, preserving
quoted source text and explicit quote requests. `core_edit_policy.py` conservatively
checks written numbers, named weekdays, negation and time conditions. These checks
can reject valid rewrites and cannot prove semantic equivalence. Factual changes
are outside this first editing policy. The original selected source is recoverable
in memory; failure must never paste the transcribed instruction as a fallback.
Unchanged edits leave the selection intact without a redundant paste.

Use a 12-second cooperative edit budget including readiness and final cleanup.
Check cancellation, disable and deadline between steps and after GPU cleanup.
Running kernels cannot be forcibly interrupted. Preserve a single model worker.
No user selection or spoken instruction is logged or saved to disk. Clear recovery
on cancellation, explicit Clear or shutdown, and replace it with the next result.
Legacy polishing APIs retain their restricted faithful-word validator and Fast
fallback for development comparisons; they are not the product's edit path.

The legacy Ollama `LLMFormatter` remains for development comparison. It is not the
dictation backend. Meeting summarization still uses `tools/meeting_llm.py` and
Ollama; migrating it is outside this change.
