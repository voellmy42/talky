# Meeting Mode Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a long-form "Meeting Mode" to Talky that records continuously, transcribes in rolling 30-second chunks, and produces a structured summary document — strictly separated from the existing dictation mode.

**Architecture:** Meeting mode runs in its own dedicated thread, separate from the dictation pipeline thread. When meeting mode is active, the Fn-key event tap ignores presses (dictation disabled). Audio capture reuses the existing AVFoundation engine. Chunk transcription reuses the existing STT tool. A new meeting-specific LLM prompt handles summarization. The UI switches between dictation and meeting visual states.

**Tech Stack:** Same as existing (Python, PyObjC/AppKit, AVFoundation, faster-whisper, Ollama/qwen2.5:3b). No new dependencies.

---

### Task 1: Add continuous recording support to core_audio.py

**Files:**
- Modify: `tools/core_audio.py`

**Context:** The existing `AudioCaptureTool` only supports press-to-record via `record_while_pressed()`. Meeting mode needs to start/stop recording programmatically and drain audio in chunks. The AVFoundation engine and capture callback are already set up — we just need new methods to control them.

**Step 1: Add `meeting_active` flag and guard Fn key handling**

At the end of `__init__`, after `self._double_tap_threshold = 0.4` (line 31), add:

```python
self.meeting_active = False
```

At the top of `_handle_press`, add early return:

```python
def _handle_press(self, now):
    if self.meeting_active:
        return
    # ... existing code ...
```

At the top of `_handle_release`, add early return:

```python
def _handle_release(self, now):
    if self.meeting_active:
        return
    # ... existing code ...
```

**Step 2: Add `start_continuous()` method**

Add after `_audio_callback` method (before `record_while_pressed`):

```python
def start_continuous(self):
    """Start continuous recording for meeting mode. Disables Fn-key dictation."""
    self.meeting_active = True
    # Drain any leftover chunks
    while not self.q.empty():
        self.q.get()
    self.is_recording = True
    if sys.platform == 'darwin':
        self.engine.startAndReturnError_(None)
    else:
        self._stream.start()
    print("[core_audio] Continuous recording started (meeting mode).", flush=True)
```

**Step 3: Add `stop_continuous()` method**

```python
def stop_continuous(self):
    """Stop continuous recording and re-enable Fn-key dictation."""
    self.is_recording = False
    if sys.platform == 'darwin':
        self.engine.pause()
    else:
        self._stream.stop()
    self.meeting_active = False
    print("[core_audio] Continuous recording stopped.", flush=True)
```

**Step 4: Add `drain_audio_queue()` method**

```python
def drain_audio_queue(self) -> np.ndarray:
    """Drain all queued audio chunks and return as a single numpy array."""
    chunks = []
    while not self.q.empty():
        chunks.append(self.q.get())
    if not chunks:
        return np.array([], dtype='float32')
    return np.concatenate(chunks, axis=0).flatten()
```

**Step 5: Verify**

Run: `python -c "from tools.core_audio import AudioCaptureTool; print('Import OK')"` from project root.
Expected: "Import OK" (no syntax errors).

**Step 6: Commit**

```bash
git add tools/core_audio.py
git commit -m "feat: add continuous recording methods for meeting mode"
```

---

### Task 2: Create meeting LLM summarization module

**Files:**
- Create: `tools/meeting_llm.py`

**Context:** This module provides the meeting-specific LLM prompt and summarization call. It talks to the same Ollama instance as `core_llm.py` but with a completely different system prompt designed for summarization rather than dictation formatting.

**Step 1: Create `tools/meeting_llm.py`**

```python
import requests
from datetime import datetime


class MeetingSummarizer:
    def __init__(self, host="http://localhost:11434", model="qwen2.5:3b"):
        self.host = f"{host}/api/generate"
        self.model = model
        self._lang_names = {"de": "German", "en": "English"}

    def _build_system_prompt(self, language: str) -> str:
        lang_name = self._lang_names.get(language, "English")
        today = datetime.now().strftime("%B %d, %Y")
        return (
            f"You are a meeting notes assistant. "
            f"The user will provide a raw transcript of a meeting or spoken thoughts in {lang_name}. "
            f"Your output MUST be in {lang_name}. Rules:\n"
            f"1. Write a Markdown document with this exact structure:\n"
            f"   # Meeting Notes — {today}\n"
            f"   ## Summary\n"
            f"   [2-3 sentences summarising what was discussed]\n"
            f"   ## Key Points\n"
            f"   - [Bullet points organised by topic/theme]\n"
            f"   ## Action Items\n"
            f"   - [ ] [Any action items, tasks, or next steps mentioned]\n"
            f"2. If no action items are found, write '- No action items identified.'\n"
            f"3. Organise key points by topic/theme, not chronologically.\n"
            f"4. Remove filler words, repetitions, and tangents.\n"
            f"5. Keep the summary concise but preserve all substantive ideas.\n"
            f"6. DO NOT invent information not present in the transcript.\n"
            f"7. Output ONLY the Markdown document. No preamble."
        )

    def summarize(self, full_transcript: str, language: str = "en") -> str:
        """Send the full meeting transcript to Ollama and return structured notes."""
        if not full_transcript.strip():
            return ""

        print("[meeting_llm] Sending transcript to Ollama for summarization...", flush=True)
        payload = {
            "model": self.model,
            "system": self._build_system_prompt(language),
            "prompt": full_transcript,
            "stream": False,
            "keep_alive": "5m",
            "options": {
                "temperature": 0.3,
                "num_predict": 4096
            }
        }

        try:
            response = requests.post(self.host, json=payload, timeout=120.0)
            response.raise_for_status()
            result = response.json().get("response", "")
            print("[meeting_llm] Summarization complete.", flush=True)
            return result.strip()
        except Exception as e:
            print(f"[meeting_llm] Summarization failed ({e}). Returning raw transcript.", flush=True)
            return f"# Meeting Transcript — Raw\n\n{full_transcript}"
```

**Step 2: Verify**

Run: `python -c "from tools.meeting_llm import MeetingSummarizer; print('Import OK')"`
Expected: "Import OK"

**Step 3: Commit**

```bash
git add tools/meeting_llm.py
git commit -m "feat: add meeting summarization LLM module"
```

---

### Task 3: Create meeting session lifecycle module

**Files:**
- Create: `tools/meeting_mode.py`

**Context:** This module orchestrates the entire meeting session: starts continuous recording, transcribes audio in ~30-second chunks on a background thread, and when stopped, summarizes everything and saves to disk. It depends on `core_audio` (continuous recording), `core_stt` (transcription), and `meeting_llm` (summarization).

**Step 1: Create `tools/meeting_mode.py`**

```python
import os
import threading
import time
import subprocess
from datetime import datetime


MEETINGS_DIR = os.path.expanduser("~/Documents/Talky/Meetings")


class MeetingSession:
    """Manages a single meeting recording session."""

    def __init__(self, audio_tool, stt_tool, summarizer, language="en",
                 on_chunk=None, on_summarizing=None, on_done=None, on_error=None):
        """
        audio_tool: AudioCaptureTool instance (for start/stop continuous, drain queue)
        stt_tool: STTTool instance (for transcribing chunks)
        summarizer: MeetingSummarizer instance
        language: BCP-47 code
        on_chunk(chunk_count): called after each chunk is transcribed
        on_summarizing(): called when summarization starts
        on_done(file_path): called when meeting notes are saved
        on_error(msg): called on error
        """
        self._audio = audio_tool
        self._stt = stt_tool
        self._summarizer = summarizer
        self._language = language
        self._on_chunk = on_chunk or (lambda n: None)
        self._on_summarizing = on_summarizing or (lambda: None)
        self._on_done = on_done or (lambda p: None)
        self._on_error = on_error or (lambda m: None)

        self._chunks = []
        self._stop_event = threading.Event()
        self._thread = None
        self._start_time = None

    @property
    def elapsed_seconds(self) -> float:
        if self._start_time is None:
            return 0.0
        return time.time() - self._start_time

    def start(self):
        """Begin recording and chunk processing."""
        self._chunks = []
        self._stop_event.clear()
        self._start_time = time.time()
        self._audio.start_continuous()
        self._thread = threading.Thread(target=self._chunk_loop, daemon=True)
        self._thread.start()
        print("[meeting] Session started.", flush=True)

    def stop(self):
        """Stop recording, process remaining audio, summarize, and save."""
        print("[meeting] Stopping session...", flush=True)
        self._stop_event.set()
        self._audio.stop_continuous()

        # Process any remaining audio in the queue
        self._transcribe_remaining()

        if self._thread:
            self._thread.join(timeout=5)

        if not self._chunks:
            self._on_error("No speech detected during meeting.")
            return

        # Summarize
        self._on_summarizing()
        full_transcript = "\n".join(self._chunks)
        print(f"[meeting] Full transcript ({len(self._chunks)} chunks, {len(full_transcript)} chars)", flush=True)

        summary = self._summarizer.summarize(full_transcript, language=self._language)

        # Save to file
        file_path = self._save(summary)
        print(f"[meeting] Saved to {file_path}", flush=True)

        # Open in default editor
        try:
            subprocess.run(["open", file_path])
        except Exception as e:
            print(f"[meeting] Could not open file: {e}", flush=True)

        self._on_done(file_path)

    def _chunk_loop(self):
        """Runs in background thread. Every ~30s, drains audio and transcribes."""
        while not self._stop_event.is_set():
            self._stop_event.wait(30)
            if self._stop_event.is_set():
                break
            self._transcribe_queued()

    def _transcribe_queued(self):
        """Drain the audio queue and transcribe whatever is there."""
        audio = self._audio.drain_audio_queue()
        if len(audio) == 0:
            return
        text = self._stt.transcribe(audio, language=self._language)
        if text:
            self._chunks.append(text)
            self._on_chunk(len(self._chunks))
            print(f"[meeting] Chunk {len(self._chunks)}: '{text[:80]}...'", flush=True)

    def _transcribe_remaining(self):
        """Final drain after recording stops."""
        self._transcribe_queued()

    def _save(self, content: str) -> str:
        """Save meeting notes to ~/Documents/Talky/Meetings/."""
        os.makedirs(MEETINGS_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename = f"{timestamp}_meeting.md"
        file_path = os.path.join(MEETINGS_DIR, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return file_path
```

**Step 2: Verify**

Run: `python -c "from tools.meeting_mode import MeetingSession, MEETINGS_DIR; print('Import OK,', MEETINGS_DIR)"`
Expected: "Import OK, /Users/.../Documents/Talky/Meetings"

**Step 3: Commit**

```bash
git add tools/meeting_mode.py
git commit -m "feat: add meeting session lifecycle module"
```

---

### Task 4: Add meeting mode UI to app.py

**Files:**
- Modify: `app.py`

**Context:** The UI needs: (1) a "Start Meeting" / "Stop Meeting" menu item in the status bar menu, (2) a distinct meeting overlay with a running timer, (3) a different menu bar icon during meeting mode, and (4) callbacks to wire into the meeting session. The overlay background color changes to blue-tinted during meeting mode.

**Step 1: Make `_RoundedBackgroundView` support dynamic colors**

Add an instance variable for fill color. Replace the `drawRect_` method:

```python
class _RoundedBackgroundView(AppKit.NSView):
    """Draws a dark rounded rectangle with configurable color."""

    _fill_r = 0.1
    _fill_g = 0.1
    _fill_b = 0.1
    _fill_a = 0.88

    def drawRect_(self, rect):
        path = AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            self.bounds(), 12, 12
        )
        AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(
            self._fill_r, self._fill_g, self._fill_b, self._fill_a
        ).setFill()
        path.fill()
```

**Step 2: Add color switching methods to `OverlayWindow`**

Add methods to switch between dictation (dark) and meeting (blue) appearance:

```python
def set_dictation_style(self):
    """Dark pill for dictation mode."""
    self._bg._fill_r = 0.1
    self._bg._fill_g = 0.1
    self._bg._fill_b = 0.1
    self._bg.setNeedsDisplay_(True)

def set_meeting_style(self):
    """Blue-tinted pill for meeting mode."""
    self._bg._fill_r = 0.08
    self._bg._fill_g = 0.15
    self._bg._fill_b = 0.35
    self._bg.setNeedsDisplay_(True)
```

This requires storing `self._bg = bg` in `__init__` (line 85-88 area).

**Step 3: Add meeting timer to `OverlayWindow`**

```python
def start_meeting_timer(self, get_elapsed):
    """Start a 1-second timer that updates the overlay with elapsed time."""
    self._stop_pulse()
    self.set_meeting_style()

    def tick(timer):
        secs = int(get_elapsed())
        mins, s = divmod(secs, 60)
        hrs, m = divmod(mins, 60)
        if hrs > 0:
            time_str = f"{hrs}:{m:02d}:{s:02d}"
        else:
            time_str = f"{m:02d}:{s:02d}"
        self._label.setStringValue_(f"  Meeting — {time_str}")

    self._window.setAlphaValue_(1.0)
    self._window.orderFrontRegardless()
    self._label.setStringValue_("  Meeting — 00:00")
    self._meeting_timer = AppKit.NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
        1.0, True, tick
    )

def stop_meeting_timer(self):
    """Stop the meeting timer and reset overlay style."""
    if hasattr(self, '_meeting_timer') and self._meeting_timer:
        self._meeting_timer.invalidate()
        self._meeting_timer = None
    self.set_dictation_style()
```

Initialize `self._meeting_timer = None` in `__init__`.

**Step 4: Add meeting menu item and icon to `StatusBarController`**

In `__init__`, after the existing icons, add:

```python
self._icon_meeting = AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
    "record.circle", "Meeting in progress"
)
self._icon_meeting.setTemplate_(True)

self._meeting_active = False
self._on_meeting_start = None
self._on_meeting_stop = None
```

Add `_meeting_fn` to `_MenuTarget`:

```python
class _MenuTarget(AppKit.NSObject):
    _quit_fn = None
    _lang_fn = None
    _meeting_fn = None

    # ... existing methods ...

    @objc.typedSelector(b"v@:@")
    def toggleMeeting_(self, sender):
        if self._meeting_fn:
            self._meeting_fn()
```

In `_build_menu`, add the meeting item **before** the Language section separator:

```python
# ---- Meeting Mode ----
menu.addItem_(AppKit.NSMenuItem.separatorItem())

self._meeting_menu_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
    "Start Meeting", "toggleMeeting:", ""
)
self._meeting_menu_item.setTarget_(self._menu_target)
menu.addItem_(self._meeting_menu_item)
```

Add methods to toggle meeting state in `StatusBarController`:

```python
def set_meeting_active(self, active):
    self._meeting_active = active
    button = self._status_item.button()
    if active:
        button.setImage_(self._icon_meeting)
        self._status_menu_item.setTitle_("Status: Meeting in progress")
        self._meeting_menu_item.setTitle_("Stop Meeting")
    else:
        button.setImage_(self._icon_idle)
        self._status_menu_item.setTitle_("Status: Ready")
        self._meeting_menu_item.setTitle_("Start Meeting")
```

**Step 5: Add meeting callbacks to `TalkyApp`**

Add meeting state and callbacks:

```python
def __init__(self, pipeline_fn):
    # ... existing code ...
    self._meeting_session = None

    # Wire up meeting toggle
    self.status_bar._menu_target._meeting_fn = self._toggle_meeting
```

```python
def _toggle_meeting(self):
    """Called from menu bar on main thread."""
    if self._meeting_session is None:
        self._start_meeting()
    else:
        self._stop_meeting()

def _start_meeting(self):
    """Called on main thread. Delegates actual work to the on_meeting_start callback."""
    if self._on_meeting_start:
        self._on_meeting_start()

def _stop_meeting(self):
    """Called on main thread. Delegates actual work to the on_meeting_stop callback."""
    if self._on_meeting_stop:
        self._on_meeting_stop()
```

Add main-thread UI mutations for meeting:

```python
def _main_meeting_start(self):
    self.status_bar.set_meeting_active(True)

def _main_meeting_summarizing(self):
    self.overlay.stop_meeting_timer()
    self.overlay.show("  Summarizing...")

def _main_meeting_done(self):
    self.status_bar.set_meeting_active(False)
    self.overlay.hide()

def _main_meeting_error(self, msg):
    self.status_bar.set_meeting_active(False)
    self.overlay.hide()
    print(f"[app] Meeting error: {msg}", flush=True)
```

Expose `_on_meeting_start` and `_on_meeting_stop` callbacks so `main.py` can set them.

**Step 6: Verify**

Run: `python -c "from app import TalkyApp; print('Import OK')"`
Expected: "Import OK"

**Step 7: Commit**

```bash
git add app.py
git commit -m "feat: add meeting mode UI (menu item, timer overlay, icon)"
```

---

### Task 5: Wire meeting mode into main.py

**Files:**
- Modify: `main.py`

**Context:** `main.py` owns the pipeline orchestration. We need to: (1) create the meeting tools (MeetingSummarizer), (2) set up meeting start/stop callbacks that create/destroy MeetingSession instances, (3) ensure meeting start/stop is thread-safe.

**Step 1: Add meeting imports**

```python
from tools.meeting_mode import MeetingSession
from tools.meeting_llm import MeetingSummarizer
```

**Step 2: Create MeetingSummarizer alongside existing tools**

After `stats_store = StatsStore()`:

```python
meeting_summarizer = MeetingSummarizer(host="http://localhost:11434", model="qwen2.5:3b")
```

**Step 3: Add meeting start/stop logic inside `pipeline_loop`**

After the AudioCaptureTool is created and before the while loop, add meeting management:

```python
meeting_session = None

def start_meeting():
    nonlocal meeting_session
    lang = get_language()

    def on_chunk(count):
        print(f"[pipeline] Meeting chunk #{count} transcribed.", flush=True)

    def on_summarizing():
        _Dispatcher.dispatch_to_main(lambda: app_ref.overlay.stop_meeting_timer())
        _Dispatcher.dispatch_to_main(lambda: app_ref.overlay.set_meeting_style())
        _Dispatcher.dispatch_to_main(lambda: app_ref.overlay.show("  Summarizing..."))

    def on_done(file_path):
        nonlocal meeting_session
        meeting_session = None
        _Dispatcher.dispatch_to_main(lambda: app_ref.status_bar.set_meeting_active(False))
        _Dispatcher.dispatch_to_main(lambda: app_ref.overlay.set_dictation_style())
        _Dispatcher.dispatch_to_main(lambda: app_ref.overlay.hide())
        print(f"[pipeline] Meeting saved: {file_path}", flush=True)

    def on_error(msg):
        nonlocal meeting_session
        meeting_session = None
        _Dispatcher.dispatch_to_main(lambda: app_ref.status_bar.set_meeting_active(False))
        _Dispatcher.dispatch_to_main(lambda: app_ref.overlay.set_dictation_style())
        _Dispatcher.dispatch_to_main(lambda: app_ref.overlay.hide())
        print(f"[pipeline] Meeting error: {msg}", flush=True)

    meeting_session = MeetingSession(
        audio_tool=audio_tool,
        stt_tool=stt_tool,
        summarizer=meeting_summarizer,
        language=lang,
        on_chunk=on_chunk,
        on_summarizing=on_summarizing,
        on_done=on_done,
        on_error=on_error,
    )
    meeting_session.start()

    # Update UI on main thread
    _Dispatcher.dispatch_to_main(lambda: app_ref.status_bar.set_meeting_active(True))
    _Dispatcher.dispatch_to_main(
        lambda: app_ref.overlay.start_meeting_timer(lambda: meeting_session.elapsed_seconds if meeting_session else 0)
    )

def stop_meeting():
    nonlocal meeting_session
    if meeting_session:
        # Run stop in a thread so it doesn't block the main thread
        threading.Thread(target=meeting_session.stop, daemon=True).start()
```

**Note:** The `_Dispatcher` import is needed. Since `pipeline_loop` runs in a background thread, we dispatch UI updates to the main thread. We need a reference to the app — this will require passing the app reference or the dispatcher.

**Step 4: Wire callbacks to the app**

The cleanest approach: `pipeline_loop` receives extra callbacks from `TalkyApp`. Add `on_meeting_start` and `on_meeting_stop` to the callback signature. `TalkyApp._toggle_meeting` calls these.

Alternatively (simpler): expose `start_meeting` and `stop_meeting` callables on TalkyApp after the pipeline thread starts, so the menu action can call them directly.

**Chosen approach:** TalkyApp stores `_on_meeting_start` and `_on_meeting_stop` callables. `pipeline_loop` sets them after AudioCaptureTool is created. The menu toggle calls them.

In `TalkyApp.__init__`, add:

```python
self._on_meeting_start = None
self._on_meeting_stop = None
```

In `TalkyApp._toggle_meeting`:

```python
def _toggle_meeting(self):
    if self.status_bar._meeting_active:
        if self._on_meeting_stop:
            self._on_meeting_stop()
    else:
        if self._on_meeting_start:
            self._on_meeting_start()
```

In `pipeline_loop`, after defining `start_meeting` and `stop_meeting`:

```python
# This requires a reference to the app. Pass it via a new callback or use a shared reference.
# Simplest: add app_ref as a closure variable by having pipeline_loop accept it.
```

**Revised wiring approach:** Pass the `TalkyApp` instance into `pipeline_loop` indirectly. The simplest way: `TalkyApp.run()` passes `self` as an additional argument to `pipeline_fn`.

Update `TalkyApp.run()` args to include `self` (as `app_ref`):

```python
def run(self):
    t = threading.Thread(
        target=self._pipeline_fn,
        args=(
            self._on_record_start,
            self._on_record_stop,
            self._on_processing,
            self._on_idle,
            self._on_warmup,
            self._on_ready,
            self.status_bar.get_language,
            self._on_stats_update,
            self,  # app_ref for meeting mode wiring
        ),
        daemon=True,
    )
    t.start()
    self._app.run()
```

Update `pipeline_loop` signature in `main.py`:

```python
def pipeline_loop(on_record_start, on_record_stop, on_processing, on_idle, on_warmup, on_ready, get_language, on_stats_update, app_ref):
```

Then in `pipeline_loop`, after defining `start_meeting`/`stop_meeting`:

```python
app_ref._on_meeting_start = start_meeting
app_ref._on_meeting_stop = stop_meeting
```

**Step 5: Add threading import to main.py**

```python
import threading
```

And import `_Dispatcher` from `app`:

```python
from app import TalkyApp, _Dispatcher
```

**Step 6: Verify**

Run the app: `python main.py` from the project root.
1. Verify menu bar shows "Start Meeting" option.
2. Click "Start Meeting" — overlay should show blue pill with timer.
3. Speak for ~1 minute.
4. Click "Stop Meeting" — overlay should show "Summarizing...", then disappear.
5. A .md file should open in the default editor.
6. Verify Fn-key dictation works again after meeting ends.
7. Verify Fn-key is ignored during meeting.

**Step 7: Commit**

```bash
git add main.py app.py
git commit -m "feat: wire meeting mode into pipeline and app lifecycle"
```

---

### Task 6: Final integration test and cleanup

**Files:**
- All modified files

**Step 1: Full smoke test**

1. Start app: `python main.py`
2. Test dictation mode: hold Fn, speak, release → text injected at cursor ✓
3. Test meeting mode: click Start Meeting, speak for 1 min, click Stop Meeting → .md file opens ✓
4. Test mode separation: during meeting, press Fn → nothing happens ✓
5. Test language: switch to German, start meeting, speak German → German summary ✓
6. Test double-tap: double-tap Fn in dictation mode → toggle mode still works ✓
7. Check file saved at: `~/Documents/Talky/Meetings/YYYY-MM-DD_HH-MM_meeting.md` ✓

**Step 2: Commit all remaining changes**

```bash
git add -A
git commit -m "feat: meeting mode — complete implementation"
```
