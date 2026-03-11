# Onboarding Wizard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a single-page onboarding wizard that checks Ollama + model and Accessibility permissions before starting the audio pipeline.

**Architecture:** New `tools/core_config.py` handles JSON config persistence. `SetupWizard` NSWindow class added to `app.py` with live status checklist. `TalkyApp` and `main.py` modified to show wizard on startup when deps are missing. `core_audio.py` sys.exit(1) removed — wizard handles this gracefully.

**Tech Stack:** Python, PyObjC (AppKit, ApplicationServices), Ollama CLI/API, subprocess

---

### Task 1: Create ConfigManager (`tools/core_config.py`)

**Files:**
- Create: `tools/core_config.py`

**Step 1: Create the ConfigManager class**

```python
import json
import os
from datetime import datetime, timezone


class ConfigManager:
    """Manages ~/.talky_config.json for setup state persistence."""

    def __init__(self, path="~/.talky_config.json"):
        self._path = os.path.expanduser(path)
        self._data = {}
        self.load()

    def load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, "r") as f:
                    self._data = json.load(f)
            except Exception as e:
                print(f"[core_config] Error loading config: {e}")
                self._data = {}

    def save(self):
        try:
            with open(self._path, "w") as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            print(f"[core_config] Error saving config: {e}")

    def is_setup_complete(self) -> bool:
        return self._data.get("has_completed_setup", False)

    def mark_setup_complete(self):
        self._data["has_completed_setup"] = True
        self._data["setup_completed_at"] = datetime.now(timezone.utc).isoformat()
        self.save()
```

**Step 2: Verify file was created**

Run: `python -c "from tools.core_config import ConfigManager; c = ConfigManager('/tmp/test_talky.json'); c.mark_setup_complete(); c2 = ConfigManager('/tmp/test_talky.json'); print(c2.is_setup_complete())"`
Expected: `True`

**Step 3: Commit**

```bash
git add tools/core_config.py
git commit -m "feat: add ConfigManager for setup persistence"
```

---

### Task 2: Add SetupWizard to `app.py`

**Files:**
- Modify: `app.py` (insert new class before `TalkyApp` class, around line 397)

**Step 1: Add imports at top of app.py**

Add these imports to the top of `app.py` (after existing imports):

```python
import subprocess
import ApplicationServices
```

**Step 2: Add SetupWizard class**

Insert before the `TalkyApp` class (before line 397 comment block). The wizard is an NSWindow with:
- Title label "Welcome to Talky"
- Two checklist rows (Ollama + model, Accessibility) each with SF Symbol status icon + label + action button
- "Complete Setup" button at the bottom, disabled until all checks pass
- A 2-second NSTimer that re-checks all statuses

```python
# ---------------------------------------------------------------------------
# Setup wizard
# ---------------------------------------------------------------------------

class _SetupTarget(AppKit.NSObject):
    """Action target for setup wizard buttons."""

    _install_model_fn = None
    _open_accessibility_fn = None
    _complete_fn = None

    @objc.typedSelector(b"v@:@")
    def installModel_(self, sender):
        if self._install_model_fn:
            self._install_model_fn()

    @objc.typedSelector(b"v@:@")
    def openAccessibility_(self, sender):
        if self._open_accessibility_fn:
            self._open_accessibility_fn()

    @objc.typedSelector(b"v@:@")
    def completeSetup_(self, sender):
        if self._complete_fn:
            self._complete_fn()


class SetupWizard:
    """Single-page checklist wizard for first-run setup."""

    MODEL_NAME = "qwen2.5:3b"

    def __init__(self, on_complete):
        """
        on_complete — callable invoked (on main thread) when the user
        clicks 'Complete Setup' and all checks pass.
        """
        self._on_complete = on_complete
        self._installing_model = False

        width, height = 480, 320
        screen = AppKit.NSScreen.mainScreen().frame()
        x = (screen.size.width - width) / 2
        y = (screen.size.height - height) / 2

        self._window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            AppKit.NSMakeRect(x, y, width, height),
            AppKit.NSWindowStyleMaskTitled | AppKit.NSWindowStyleMaskClosable,
            AppKit.NSBackingStoreBuffered,
            False,
        )
        self._window.setTitle_("Welcome to Talky")
        self._window.setLevel_(AppKit.NSFloatingWindowLevel)

        content = self._window.contentView()

        # ---- Title ----
        title = AppKit.NSTextField.labelWithString_("Setup Checklist")
        title.setFrame_(AppKit.NSMakeRect(20, height - 50, width - 40, 30))
        title.setFont_(AppKit.NSFont.boldSystemFontOfSize_(20))
        content.addSubview_(title)

        subtitle = AppKit.NSTextField.labelWithString_(
            "Talky needs a few things before it can run."
        )
        subtitle.setFrame_(AppKit.NSMakeRect(20, height - 75, width - 40, 20))
        subtitle.setFont_(AppKit.NSFont.systemFontOfSize_(13))
        subtitle.setTextColor_(AppKit.NSColor.secondaryLabelColor())
        content.addSubview_(subtitle)

        # ---- Row 1: Ollama + Model ----
        row1_y = height - 130

        self._ollama_icon = AppKit.NSImageView.alloc().initWithFrame_(
            AppKit.NSMakeRect(20, row1_y, 20, 20)
        )
        content.addSubview_(self._ollama_icon)

        self._ollama_label = AppKit.NSTextField.labelWithString_("Checking Ollama...")
        self._ollama_label.setFrame_(AppKit.NSMakeRect(48, row1_y, 260, 20))
        self._ollama_label.setFont_(AppKit.NSFont.systemFontOfSize_(13))
        content.addSubview_(self._ollama_label)

        self._target = _SetupTarget.alloc().init()
        self._target._install_model_fn = self._install_model
        self._target._open_accessibility_fn = self._open_accessibility
        self._target._complete_fn = self._complete

        self._ollama_button = AppKit.NSButton.alloc().initWithFrame_(
            AppKit.NSMakeRect(340, row1_y - 2, 120, 24)
        )
        self._ollama_button.setBezelStyle_(AppKit.NSBezelStyleRounded)
        self._ollama_button.setTitle_("Install Model")
        self._ollama_button.setTarget_(self._target)
        self._ollama_button.setAction_("installModel:")
        self._ollama_button.setHidden_(True)
        content.addSubview_(self._ollama_button)

        # ---- Row 2: Accessibility ----
        row2_y = height - 180

        self._ax_icon = AppKit.NSImageView.alloc().initWithFrame_(
            AppKit.NSMakeRect(20, row2_y, 20, 20)
        )
        content.addSubview_(self._ax_icon)

        self._ax_label = AppKit.NSTextField.labelWithString_("Checking Accessibility...")
        self._ax_label.setFrame_(AppKit.NSMakeRect(48, row2_y, 260, 20))
        self._ax_label.setFont_(AppKit.NSFont.systemFontOfSize_(13))
        content.addSubview_(self._ax_label)

        self._ax_button = AppKit.NSButton.alloc().initWithFrame_(
            AppKit.NSMakeRect(340, row2_y - 2, 120, 24)
        )
        self._ax_button.setBezelStyle_(AppKit.NSBezelStyleRounded)
        self._ax_button.setTitle_("Open Settings")
        self._ax_button.setTarget_(self._target)
        self._ax_button.setAction_("openAccessibility:")
        self._ax_button.setHidden_(True)
        content.addSubview_(self._ax_button)

        # ---- Complete button ----
        self._complete_button = AppKit.NSButton.alloc().initWithFrame_(
            AppKit.NSMakeRect(width - 170, 20, 150, 32)
        )
        self._complete_button.setBezelStyle_(AppKit.NSBezelStyleRounded)
        self._complete_button.setTitle_("Complete Setup")
        self._complete_button.setTarget_(self._target)
        self._complete_button.setAction_("completeSetup:")
        self._complete_button.setEnabled_(False)
        content.addSubview_(self._complete_button)

        # Run first check, then start periodic timer
        self._check_all()
        self._timer = AppKit.NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
            2.0, True, lambda t: self._check_all()
        )

    # ---- Checks ----

    def _check_ollama(self) -> bool:
        """Returns True if Ollama is running AND the model is available."""
        try:
            result = subprocess.run(
                ["pgrep", "-x", "ollama"], capture_output=True
            )
            if result.returncode != 0:
                return False
            # Check model list via CLI
            result = subprocess.run(
                ["ollama", "list"], capture_output=True, text=True, timeout=5
            )
            return self.MODEL_NAME in result.stdout
        except Exception:
            return False

    def _check_accessibility(self) -> bool:
        return ApplicationServices.AXIsProcessTrusted()

    def _check_all(self):
        """Re-evaluate all checks and update UI."""
        ollama_ok = self._check_ollama()
        ax_ok = self._check_accessibility()

        # Update Ollama row
        self._set_row_status(
            self._ollama_icon,
            self._ollama_label,
            self._ollama_button,
            ok=ollama_ok,
            ok_text="Ollama running, model installed",
            fail_text="Ollama or model missing" if not self._installing_model else "Installing model...",
        )
        if self._installing_model:
            self._ollama_button.setHidden_(True)

        # Update Accessibility row
        self._set_row_status(
            self._ax_icon,
            self._ax_label,
            self._ax_button,
            ok=ax_ok,
            ok_text="Accessibility permission granted",
            fail_text="Accessibility permission required",
        )

        self._complete_button.setEnabled_(ollama_ok and ax_ok)

    def _set_row_status(self, icon_view, label, button, ok, ok_text, fail_text):
        if ok:
            img = AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
                "checkmark.circle.fill", "OK"
            )
            label.setStringValue_(ok_text)
            label.setTextColor_(AppKit.NSColor.labelColor())
            button.setHidden_(True)
        else:
            img = AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
                "xmark.circle.fill", "Missing"
            )
            label.setStringValue_(fail_text)
            label.setTextColor_(AppKit.NSColor.systemRedColor())
            button.setHidden_(False)
        if img:
            img.setTemplate_(False)
            icon_view.setImage_(img)

    # ---- Actions ----

    def _install_model(self):
        """Run 'ollama pull qwen2.5:3b' in a background thread."""
        self._installing_model = True
        self._ollama_button.setHidden_(True)
        self._ollama_label.setStringValue_("Installing model...")
        self._ollama_label.setTextColor_(AppKit.NSColor.secondaryLabelColor())

        def _pull():
            try:
                subprocess.run(
                    ["ollama", "pull", self.MODEL_NAME],
                    timeout=600,
                )
            except Exception as e:
                print(f"[setup] Model install failed: {e}", flush=True)
            self._installing_model = False

        import threading
        threading.Thread(target=_pull, daemon=True).start()

    def _open_accessibility(self):
        """Open macOS Accessibility preferences pane."""
        subprocess.Popen([
            "open",
            "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
        ])

    def _complete(self):
        """User clicked Complete Setup."""
        self._timer.invalidate()
        self._timer = None
        self._window.orderOut_(None)
        if self._on_complete:
            self._on_complete()

    # ---- Show / Close ----

    def show(self):
        self._window.makeKeyAndOrderFront_(None)
        # Bring app to front so the window is visible
        AppKit.NSApp.activateIgnoringOtherApps_(True)

    def close(self):
        if self._timer:
            self._timer.invalidate()
            self._timer = None
        self._window.orderOut_(None)
```

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat: add SetupWizard checklist UI"
```

---

### Task 3: Modify TalkyApp to integrate the wizard

**Files:**
- Modify: `app.py` (TalkyApp class, lines 401-504)

**Step 1: Add config import and modify TalkyApp.__init__**

Add import at top of `app.py`:
```python
from tools.core_config import ConfigManager
```

Modify `TalkyApp.__init__` to accept a `needs_setup` flag and store a config reference:

```python
class TalkyApp:
    def __init__(self, pipeline_fn, on_cleanup=None, needs_setup=False):
        self._pipeline_fn = pipeline_fn
        self._on_cleanup = on_cleanup
        self._needs_setup = needs_setup
        self._config = ConfigManager()
        self._app = AppKit.NSApplication.sharedApplication()
        self._app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)

        self.overlay = OverlayWindow()
        self.status_bar = StatusBarController(on_quit=self._quit)

        self._wizard = None

        # Meeting mode callbacks — set by pipeline after init
        self._on_meeting_start = None
        self._on_meeting_stop = None
        self.status_bar._menu_target._meeting_fn = self._toggle_meeting
```

**Step 2: Modify TalkyApp.run() to conditionally show wizard**

```python
def run(self):
    if self._needs_setup:
        self._show_wizard()
        self.status_bar.set_setup_required(True)
    else:
        self._start_pipeline()
    self._app.run()

def _show_wizard(self):
    self._wizard = SetupWizard(on_complete=self._on_setup_complete)
    self._wizard.show()

def _on_setup_complete(self):
    """Called on main thread when wizard finishes."""
    self._config.mark_setup_complete()
    self._needs_setup = False
    self._wizard = None
    self.status_bar.set_setup_required(False)
    self._start_pipeline()

def _start_pipeline(self):
    import threading
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
```

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat: integrate wizard into TalkyApp lifecycle"
```

---

### Task 4: Add StatusBar "Setup Required" support

**Files:**
- Modify: `app.py` (StatusBarController class)

**Step 1: Add `_setup_required` state and `set_setup_required` method**

Add to `StatusBarController.__init__` (after `self._ollama_offline = False`, line 260):
```python
self._setup_required = False
```

Add new method after `set_ollama_offline`:
```python
def set_setup_required(self, needed: bool):
    self._setup_required = needed
    self._update_display()
```

**Step 2: Update `_update_display` to handle setup_required**

Modify `_update_display` to check `_setup_required` first (highest priority warning):

```python
def _update_display(self):
    button = self._status_item.button()
    if self._setup_required:
        button.setImage_(self._icon_warning)
        self._status_menu_item.setTitle_("Status: Setup Required")
    elif self._is_recording:
        button.setImage_(self._icon_recording)
        self._status_menu_item.setTitle_("Status: Recording...")
    elif self._meeting_active:
        button.setImage_(self._icon_meeting)
        self._status_menu_item.setTitle_("Status: Meeting in progress")
        self._meeting_menu_item.setTitle_("Stop Meeting")
    elif self._ollama_offline:
        button.setImage_(self._icon_warning)
        self._status_menu_item.setTitle_("Status: Ollama missing")
        self._meeting_menu_item.setTitle_("Start Meeting")
    else:
        button.setImage_(self._icon_idle)
        self._status_menu_item.setTitle_("Status: Ready")
        self._meeting_menu_item.setTitle_("Start Meeting")
```

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat: add Setup Required status to menu bar"
```

---

### Task 5: Modify `main.py` startup flow

**Files:**
- Modify: `main.py`

**Step 1: Add config check and `needs_setup` detection**

Add import at top (after existing imports):
```python
from tools.core_config import ConfigManager
```

Add a function to check if setup is needed (checks both config flag and live deps):

```python
def _needs_setup() -> bool:
    """Check if the setup wizard should be shown."""
    import shutil
    import ApplicationServices

    config = ConfigManager()

    # Always check live dependencies, even if config says setup was completed
    ax_ok = ApplicationServices.AXIsProcessTrusted()

    ollama_ok = False
    try:
        result = subprocess.run(["pgrep", "-x", "ollama"], capture_output=True)
        if result.returncode == 0:
            result = subprocess.run(
                ["ollama", "list"], capture_output=True, text=True, timeout=5
            )
            ollama_ok = "qwen2.5:3b" in result.stdout
    except Exception:
        pass

    if not ax_ok or not ollama_ok:
        return True

    if not config.is_setup_complete():
        return True

    return False
```

**Step 2: Modify main() to use the setup check**

Replace the beginning of `main()` to conditionally show the wizard:

```python
def main():
    print("--- Initializing Talky ---", flush=True)

    needs_setup = _needs_setup()

    if not needs_setup:
        ensure_ollama_running()

    # ... rest of tool initialization stays the same ...

    app = TalkyApp(pipeline_loop, on_cleanup=stop_ollama, needs_setup=needs_setup)
    app.run()
```

The key change: `ensure_ollama_running()` is only called if setup is already complete. Otherwise the wizard handles Ollama detection/installation.

**Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add setup check to main startup flow"
```

---

### Task 6: Remove `sys.exit(1)` from `core_audio.py`

**Files:**
- Modify: `tools/core_audio.py` (lines 39-48)

**Step 1: Remove the accessibility check block**

Remove the entire block (lines 39-48):

```python
        # REMOVED — wizard now handles accessibility check before pipeline starts
        # Verify accessibility permission on macOS
        if sys.platform == 'darwin':
            import ApplicationServices
            if not ApplicationServices.AXIsProcessTrusted():
                print(...)
                sys.exit(1)
```

The wizard guarantees accessibility is granted before `AudioCaptureTool` is ever instantiated, so this check is no longer needed.

**Step 2: Verify the event tap still works**

The event tap creation (line ~219-238) will naturally fail if accessibility isn't granted, but since the wizard enforces it, this is safe.

**Step 3: Commit**

```bash
git add tools/core_audio.py
git commit -m "refactor: remove sys.exit(1) accessibility check (wizard handles it)"
```

---

### Task 7: End-to-end manual test

**Step 1: Test fresh setup (no config file)**

```bash
rm -f ~/.talky_config.json
python main.py
```

Expected:
- Wizard window appears with "Welcome to Talky"
- Ollama row shows status (green if running + model installed, red otherwise)
- Accessibility row shows status
- "Complete Setup" only enabled when both green
- Menu bar shows warning icon + "Status: Setup Required"

**Step 2: Test completed setup (config exists, deps present)**

```bash
python main.py
```

Expected:
- No wizard — pipeline starts directly
- Menu bar shows mic icon + "Status: Ready" after warmup

**Step 3: Test re-check (config exists but dep missing)**

```bash
# Temporarily rename ollama to simulate missing
python main.py
```

Expected:
- Wizard re-appears even though `has_completed_setup` is true
- After fixing the dep and waiting 2s, status updates live

---

## Summary of all file changes

| File | Action | Description |
|------|--------|-------------|
| `tools/core_config.py` | CREATE | ConfigManager class for `~/.talky_config.json` |
| `app.py` | MODIFY | Add `SetupWizard`, `_SetupTarget` classes; modify `TalkyApp` to support wizard flow; add `set_setup_required` to `StatusBarController` |
| `main.py` | MODIFY | Add `_needs_setup()` check; conditional wizard display; import ConfigManager |
| `tools/core_audio.py` | MODIFY | Remove `sys.exit(1)` accessibility block (lines 39-48) |
