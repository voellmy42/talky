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
