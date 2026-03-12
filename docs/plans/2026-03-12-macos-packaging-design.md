# Design: Package Talky as macOS .app Bundle

**Date**: 2026-03-12
**Status**: Approved

## Context

Talky is a macOS menu bar dictation tool that currently runs from source via a bash launcher script. We want to package it as a standalone `.app` bundle so it can be launched like a native macOS application.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Packaging tool | PyInstaller | Widely used, good pyobjc support, handles hiddenimports |
| Ollama | Require pre-installed | Setup wizard already handles detection & guidance |
| Model weights | Download on first run | Keeps bundle small (~50-100MB base vs +150MB with weights) |
| Code signing | None (personal use) | Bypass Gatekeeper manually via System Settings |
| Architecture | arm64 only | MLX requires Apple Silicon, no Intel support needed |

## Bundle Structure

```
dist/Talky.app/
  Contents/
    Info.plist          # LSUIElement=true, mic/accessibility descriptions
    MacOS/
      Talky             # PyInstaller bootstrap binary
    Resources/
      talky.icns        # App icon (from talky-logo.jpg)
      talky-logo.jpg    # Bundled asset for setup wizard
    Frameworks/         # Bundled Python + native libs
```

## Implementation Steps

### 1. Icon Preparation
- Convert `talky-logo.jpg` to 1024x1024 PNG via `sips`
- Create `.iconset` directory with required sizes (16, 32, 128, 256, 512 + @2x)
- Generate `talky.icns` via `iconutil`

### 2. Entitlements & Plists
- `entitlements.plist`:
  - `com.apple.security.device.microphone = true`
- `Info.plist` additions (via PyInstaller spec):
  - `LSUIElement = true` (no Dock icon, menu bar only)
  - `NSMicrophoneUsageDescription` = "Talky needs microphone access for speech-to-text dictation."
  - `NSAppleEventsUsageDescription` = "Talky needs Apple Events access to control Ollama."
  - `CFBundleIdentifier` = "com.antigravity.talky"
  - `CFBundleDisplayName` = "Talky"

### 3. Asset Path Handling
- Add `resource_path(relative)` function to `main.py`:
  - When bundled: resolve via `sys._MEIPASS`
  - When running from source: resolve relative to `__file__`
- Update `app.py` SetupWizard to use `resource_path("talky-logo.jpg")`

### 4. PyInstaller Spec File (`talky.spec`)
- `console=False` (suppress terminal)
- `target_arch='arm64'`
- `datas`: `[('talky-logo.jpg', '.')]`
- `hiddenimports`: All pyobjc-framework-* packages, mlx, mlx_whisper, sounddevice, av, etc.
- `collect_all` for: mlx, mlx_metal, mlx_whisper (Metal shaders, data files)
- `bundle_identifier`: "com.antigravity.talky"

### 5. Build & Verify
- `pyinstaller talky.spec --clean`
- Verify: menu bar icon, overlay window, Fn key, dictation pipeline

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| MLX Metal shaders missing | `collect_all('mlx')` and `collect_all('mlx_metal')` |
| Bundle size ~1-2GB | Expected; torch + mlx + numpy are large |
| pyobjc framework linking | Explicit hiddenimports for all 7 packages |
| Quartz event tap in .app | Accessibility is OS-level; works if permission granted |

## Out of Scope
- Code signing / notarization
- DMG installer creation
- Ollama bundling
- Model weight bundling
- Universal binary (Intel support)
- Removing unused dependencies (faster-whisper, torch)
