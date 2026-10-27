# Dictation formatting SOP

Fast mode uses `LLMFormatter.fast_cleanup` in `tools/core_llm.py`. It is the default
and must not load an LLM or make a network request.

Polished preview uses `EmbeddedFormatter` in `tools/core_mlx_llm.py`, with pinned
models installed by `tools/core_model_store.py`. `FormatRequest` and `FormatResult`
define the in-memory request/result schema. One worker owns model loading,
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
never load it for Fast startup. Model setup is separate from speech readiness.
After AI is first requested, sample available memory every ten seconds. Below
1 GiB, pause generation and queue weight eviction on the worker; allow a later
reload after 2 GiB becomes available. These thresholds are a development heuristic,
not proof against memory exhaustion. Stop the monitor on shutdown.

Buffer streaming generation internally until completion. Apply deterministic
cleanup, then validate source-order words and protected technical tokens with the
dictation language. German “um” must not be deleted. Only faithful punctuation,
case/layout edits and limited hesitation removal are allowed. This validator does
not prove semantic equivalence; grammar rewriting and semantic self-correction
need a separate editing policy and evaluation.

Use a 1.5-second warm-generation budget for <=80 words and 4 seconds otherwise,
including worker queue time and final GPU cleanup. Check cancellation/deadline
between steps and again after completion. Running GPU kernels cannot be forcibly
interrupted; keep the pipeline busy until they drain. Never paste partial,
length-limited, cancelled or rejected output. On non-cancellation failure, return
Fast cleanup and a reason code; preserve the original in the session controller.
Cancellation invalidates the session and discards its text before delivery.

The legacy Ollama `LLMFormatter` remains for development comparison. It is not the
dictation backend. Meeting summarization still uses `tools/meeting_llm.py` and
Ollama; migrating it is outside this change.
