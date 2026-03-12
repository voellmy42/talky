# Production Hardening — Design

**Date:** 2026-03-12
**Status:** Pending approval

## Goal

Move Talky from prototype to production-ready by addressing three areas: Ollama lifecycle management, dependency formalization with architecture detection, and production logging with correct resource paths.

---

## Task A: Robust Ollama Lifecycle Management

### Problem
Launching Ollama.app causes a brief window flash before the current AppleScript polling loop can close it.

### Solution
Prefer the headless `ollama serve` CLI over Ollama.app.

**Startup sequence:**
1. `pgrep -x ollama` — if already running, do nothing (existing behavior)
2. Check for CLI binary: `shutil.which("ollama")` or `/usr/local/bin/ollama`
3. If CLI exists → `subprocess.Popen(["ollama", "serve"])`, store the Popen reference
4. Else if `/Applications/Ollama.app` exists → `open -g -j -a Ollama` (current fallback)
5. Set `_talky_started_ollama = True` and `_ollama_start_method = "serve" | "app"`

**Cleanup (`stop_ollama`):**
- If `_talky_started_ollama` is False → return
- If `_ollama_start_method == "serve"` → `_ollama_process.terminate()`, then `.wait(timeout=5)`, then `.kill()` if needed
- If `_ollama_start_method == "app"` → `osascript 'quit app "Ollama"'` (existing)

**Removal:**
- Delete the `_launch_ollama_app_icon_only()` function and its AppleScript polling thread entirely
- The `_close_ollama_windows` AppleScript logic is no longer needed

### Files changed
- `main.py` — `ensure_ollama_running()`, `stop_ollama()`, remove `_launch_ollama_app_icon_only()`

---

## Task B: Formal Dependency Management + Architecture Detection

### pyproject.toml
Create `pyproject.toml` at project root with:
- `[project]` metadata (name, version, description, python requirement)
- `[project.dependencies]` — common deps: `sounddevice`, `numpy`, `requests`, `pyautogui`, `pyperclip`, `pyobjc-framework-Cocoa`, `pyobjc-framework-Quartz`, `pyobjc-framework-AVFoundation`, `faster-whisper`
- `[project.optional-dependencies]` — `silicon = ["mlx-whisper"]` for Apple Silicon only

### Architecture detection in core_stt.py
- At `__init__` time, check `platform.machine()`
- `arm64` → import and use `mlx_whisper` (current path)
- `x86_64` → import and use `faster_whisper` with `WhisperModel(size, device="cpu", compute_type="int8")`
- Same `transcribe()` interface for both backends
- Lazy import: each backend imported only when selected

### Files changed
- New: `pyproject.toml`
- `tools/core_stt.py` — add platform check, faster-whisper fallback path

---

## Task C: Production Logging & Resource Paths

### Logging
New file `tools/core_logging.py`:
- Configure `logging.getLogger("talky")` with:
  - `RotatingFileHandler` → `~/Library/Logs/Talky/talky.log` (5 MB, 3 backups)
  - `StreamHandler` → stderr (for dev/console)
  - Format: `%(asctime)s [%(name)s] %(levelname)s %(message)s`
- Auto-creates the log directory on import
- Each module gets a child logger: `logging.getLogger("talky.stt")`, `logging.getLogger("talky.audio")`, etc.

Replace all `print(f"[tag] ...", flush=True)` calls across:
- `main.py`
- `app.py`
- `tools/core_stt.py`
- `tools/core_llm.py`
- `tools/core_audio.py`
- `tools/core_output.py`
- `tools/core_config.py`
- `tools/core_stats.py`
- `tools/meeting_mode.py`
- `tools/meeting_llm.py`

### Resource paths
Add a helper in `app.py`:
```python
def _resource_path(filename):
    """Resolve resource path — NSBundle for .app, __file__ for dev."""
    bundle = NSBundle.mainBundle()
    bundle_path = bundle.resourcePath()
    candidate = os.path.join(bundle_path, filename)
    if os.path.exists(candidate):
        return candidate
    return os.path.join(os.path.dirname(__file__), filename)
```
Use this for logo loading in `SetupWizard`.

### Files changed
- New: `tools/core_logging.py`
- All files listed above — replace `print()` with `logger.*`
- `app.py` — add `_resource_path()`, use it for logo

---

## Out of scope
- Task 1 (Onboarding Wizard v2) — already implemented
- Changes to the audio engine, STT model selection, or LLM prompt
- CI/CD or .app bundling (PyInstaller/py2app) setup
- Unit tests (future task)
