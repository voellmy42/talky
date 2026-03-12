# macOS .app Packaging Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Package Talky as a standalone macOS `.app` bundle that runs as a menu bar tool without a terminal window.

**Architecture:** Use PyInstaller to freeze the Python application into a single `.app` bundle targeting arm64. The bundle includes all Python dependencies, native frameworks (pyobjc, MLX Metal), and assets. The app runs as `LSUIElement` (no Dock icon). Ollama and MLX-Whisper model weights remain external (pre-installed / downloaded on first run).

**Tech Stack:** PyInstaller, sips/iconutil (macOS CLI), pyobjc, MLX

---

### Task 1: Generate App Icon (`talky.icns`)

**Files:**
- Input: `talky-logo.jpg`
- Create: `packaging/talky.icns`

**Step 1: Create packaging directory and generate iconset**

```bash
mkdir -p packaging/talky.iconset
```

**Step 2: Convert JPG to 1024x1024 PNG and generate all required icon sizes**

```bash
# Base 1024 PNG
sips -s format png -z 1024 1024 talky-logo.jpg --out packaging/talky.iconset/icon_512x512@2x.png

# Generate all required sizes
sips -z 512 512 packaging/talky.iconset/icon_512x512@2x.png --out packaging/talky.iconset/icon_512x512.png
sips -z 256 256 packaging/talky.iconset/icon_512x512@2x.png --out packaging/talky.iconset/icon_256x256@2x.png
sips -z 256 256 packaging/talky.iconset/icon_512x512@2x.png --out packaging/talky.iconset/icon_256x256.png
sips -z 128 128 packaging/talky.iconset/icon_512x512@2x.png --out packaging/talky.iconset/icon_128x128@2x.png
sips -z 128 128 packaging/talky.iconset/icon_512x512@2x.png --out packaging/talky.iconset/icon_128x128.png
sips -z 64 64   packaging/talky.iconset/icon_512x512@2x.png --out packaging/talky.iconset/icon_32x32@2x.png
sips -z 32 32   packaging/talky.iconset/icon_512x512@2x.png --out packaging/talky.iconset/icon_32x32.png
sips -z 32 32   packaging/talky.iconset/icon_512x512@2x.png --out packaging/talky.iconset/icon_16x16@2x.png
sips -z 16 16   packaging/talky.iconset/icon_512x512@2x.png --out packaging/talky.iconset/icon_16x16.png
```

**Step 3: Generate .icns file**

```bash
iconutil -c icns packaging/talky.iconset -o packaging/talky.icns
```

**Step 4: Verify**

```bash
file packaging/talky.icns
# Expected: "packaging/talky.icns: Mac OS X icon, ..."
```

**Step 5: Commit**

```bash
git add packaging/
git commit -m "feat: add app icon for macOS packaging"
```

---

### Task 2: Create Entitlements Plist

**Files:**
- Create: `packaging/entitlements.plist`

**Step 1: Create the entitlements file**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.device.microphone</key>
    <true/>
</dict>
</plist>
```

**Step 2: Verify valid plist**

```bash
plutil -lint packaging/entitlements.plist
# Expected: "packaging/entitlements.plist: OK"
```

**Step 3: Commit**

```bash
git add packaging/entitlements.plist
git commit -m "feat: add microphone entitlements for app bundle"
```

---

### Task 3: Add Resource Path Helper

**Files:**
- Modify: `main.py` (add `resource_path` function near top)
- Modify: `app.py:530` (update logo path to use helper)

**Step 1: Add `resource_path()` to `main.py`**

Insert after the existing imports (after line 15):

```python
import sys
import os


def resource_path(relative_path):
    """Resolve path to bundled resource (works both from source and PyInstaller .app)."""
    if getattr(sys, '_MEIPASS', None):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)
```

**Step 2: Update `app.py` to import and use `resource_path`**

At the top of `app.py`, add import (after line 5, the existing imports):

```python
from main import resource_path
```

> **IMPORTANT:** This creates a circular import risk since `main.py` imports from `app.py`. To avoid this, instead put `resource_path` in a new tiny module `tools/core_paths.py`:

Create `tools/core_paths.py`:

```python
import sys
import os


def resource_path(relative_path):
    """Resolve path to bundled resource (works both from source and PyInstaller .app)."""
    if getattr(sys, '_MEIPASS', None):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), relative_path)
```

Note: `os.path.dirname` is called twice because this file lives inside `tools/`, so we need to go up one level to reach the project root where `talky-logo.jpg` lives.

Then in `app.py`, replace line 530:

```python
# BEFORE (line 529-530):
        import os
        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "talky-logo.jpg")

# AFTER:
        from tools.core_paths import resource_path
        logo_path = resource_path("talky-logo.jpg")
```

**Step 3: Verify the app still runs from source**

```bash
.venv/bin/python3 main.py
# Expected: App launches normally, setup wizard shows logo
# Ctrl+C to exit
```

**Step 4: Commit**

```bash
git add tools/core_paths.py app.py
git commit -m "feat: add resource_path helper for bundled asset resolution"
```

---

### Task 4: Generate `requirements.txt`

**Files:**
- Create: `requirements.txt`

**Step 1: Freeze current environment**

```bash
.venv/bin/pip freeze > requirements.txt
```

**Step 2: Verify key packages are listed**

```bash
grep -E "^(mlx|pyobjc|sounddevice|pyautogui|pyperclip|requests|numpy|av==)" requirements.txt
```

Expected output should include at minimum:
- `mlx==0.29.3`
- `mlx-whisper==0.4.3`
- `pyobjc-core==12.0`
- `sounddevice==0.5.5`
- `PyAutoGUI==0.9.54`
- `pyperclip==1.11.0`
- `requests==2.32.5`
- `numpy==2.0.2`
- `av==15.1.0`

**Step 3: Commit**

```bash
git add requirements.txt
git commit -m "feat: add requirements.txt for packaging"
```

---

### Task 5: Install PyInstaller

**Files:** None (environment setup)

**Step 1: Install PyInstaller in the venv**

```bash
.venv/bin/pip install pyinstaller
```

**Step 2: Verify**

```bash
.venv/bin/pyinstaller --version
# Expected: a version number (e.g., 6.x)
```

---

### Task 6: Create PyInstaller Spec File

**Files:**
- Create: `talky.spec`

**Step 1: Create the spec file**

```python
# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules

# Collect MLX and Metal shader resources
mlx_datas, mlx_binaries, mlx_hiddenimports = collect_all('mlx')
mlx_metal_datas, mlx_metal_binaries, mlx_metal_hiddenimports = collect_all('mlx_metal')
mlx_whisper_datas, mlx_whisper_binaries, mlx_whisper_hiddenimports = collect_all('mlx_whisper')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=mlx_binaries + mlx_metal_binaries + mlx_whisper_binaries,
    datas=[
        ('talky-logo.jpg', '.'),
    ] + mlx_datas + mlx_metal_datas + mlx_whisper_datas,
    hiddenimports=[
        # pyobjc frameworks
        'objc',
        'AppKit',
        'Quartz',
        'ApplicationServices',
        'AVFoundation',
        'CoreAudio',
        'CoreMedia',
        'CoreText',
        'pyobjc_framework_Cocoa',
        'pyobjc_framework_Quartz',
        'pyobjc_framework_ApplicationServices',
        'pyobjc_framework_AVFoundation',
        'pyobjc_framework_CoreAudio',
        'pyobjc_framework_CoreMedia',
        'pyobjc_framework_CoreText',
        # Audio
        'sounddevice',
        '_sounddevice_data',
        'av',
        # ML
        'mlx',
        'mlx.core',
        'mlx.nn',
        'mlx_whisper',
        'numpy',
        'scipy',
        # Text injection
        'pyautogui',
        'pyperclip',
        # Networking
        'requests',
        # Our modules
        'tools',
        'tools.core_audio',
        'tools.core_stt',
        'tools.core_llm',
        'tools.core_output',
        'tools.core_audio_feedback',
        'tools.core_stats',
        'tools.core_config',
        'tools.core_paths',
        'tools.meeting_mode',
        'tools.meeting_llm',
    ] + mlx_hiddenimports + mlx_metal_hiddenimports + mlx_whisper_hiddenimports
      + collect_submodules('pyobjc_framework_Cocoa')
      + collect_submodules('pyobjc_framework_Quartz')
      + collect_submodules('pyobjc_framework_ApplicationServices')
      + collect_submodules('pyobjc_framework_AVFoundation')
      + collect_submodules('pyobjc_framework_CoreAudio')
      + collect_submodules('pyobjc_framework_CoreMedia')
      + collect_submodules('pyobjc_framework_CoreText'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Talky',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    target_arch='arm64',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='Talky',
)

app = BUNDLE(
    coll,
    name='Talky.app',
    icon='packaging/talky.icns',
    bundle_identifier='com.antigravity.talky',
    info_plist={
        'LSUIElement': True,
        'CFBundleDisplayName': 'Talky',
        'CFBundleShortVersionString': '1.0.0',
        'NSMicrophoneUsageDescription': 'Talky needs microphone access for speech-to-text dictation.',
        'NSAppleEventsUsageDescription': 'Talky needs Apple Events access to control Ollama.',
    },
)
```

**Step 2: Commit**

```bash
git add talky.spec
git commit -m "feat: add PyInstaller spec for macOS app bundle"
```

---

### Task 7: Build the App

**Files:** None (build step)

**Step 1: Run PyInstaller**

```bash
.venv/bin/pyinstaller talky.spec --clean
```

This will take several minutes. Expected output ends with:
```
... INFO: Building BUNDLE BUNDLE-00.toc completed successfully.
```

**Step 2: Verify the .app exists and has expected structure**

```bash
ls -la dist/Talky.app/Contents/
# Expected: Info.plist, MacOS/, Resources/, Frameworks/ (or _internal/)
```

```bash
ls dist/Talky.app/Contents/MacOS/
# Expected: Talky (the executable)
```

```bash
# Check Info.plist has our keys
plutil -p dist/Talky.app/Contents/Info.plist | grep -E "LSUIElement|NSMicrophone|NSAppleEvents|CFBundleIdentifier"
```

**Step 3: Check the icon was included**

```bash
ls dist/Talky.app/Contents/Resources/talky.icns
```

**Step 4: Check the logo asset was bundled**

```bash
find dist/Talky.app -name "talky-logo.jpg"
# Expected: a path inside the bundle
```

---

### Task 8: Test the App

**Step 1: Launch the app**

```bash
open dist/Talky.app
```

**Step 2: Verify checklist**

- [ ] Menu bar icon appears (microphone SF Symbol)
- [ ] No Dock icon visible (LSUIElement working)
- [ ] No terminal window opens
- [ ] Overlay pill appears during warmup ("Warming up models...")
- [ ] Setup wizard shows with logo image (if first run on fresh config)
- [ ] Fn key triggers recording
- [ ] Dictation pipeline works end-to-end

**Step 3: If the app crashes, check Console.app or run from terminal for debug output**

```bash
dist/Talky.app/Contents/MacOS/Talky
```

This shows stdout/stderr for debugging missing imports or resources.

---

### Task 9: Ad-hoc Sign with Entitlements (optional but recommended)

**Step 1: Ad-hoc sign to embed entitlements**

```bash
codesign --force --deep --sign - --entitlements packaging/entitlements.plist dist/Talky.app
```

**Step 2: Verify**

```bash
codesign -dvvv dist/Talky.app 2>&1 | grep -E "Identifier|entitlements"
```

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat: complete macOS .app packaging with PyInstaller"
```

---

## Troubleshooting Reference

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `ModuleNotFoundError: No module named 'xxx'` | Missing hiddenimport | Add to `hiddenimports` in spec, rebuild |
| App crashes silently | Run from terminal to see traceback | `dist/Talky.app/Contents/MacOS/Talky` |
| Logo not showing in wizard | `resource_path` not resolving `_MEIPASS` | Check `talky-logo.jpg` is in `datas` and `_MEIPASS` path is correct |
| Metal/GPU errors | mlx_metal shaders missing | Ensure `collect_all('mlx_metal')` is in spec |
| Microphone permission not prompted | Missing `NSMicrophoneUsageDescription` | Check Info.plist in built app |
| App shows in Dock | `LSUIElement` not set | Check Info.plist `LSUIElement: true` |
| Gatekeeper blocks launch | Not code-signed | Right-click → Open, or System Settings → Privacy → allow |
