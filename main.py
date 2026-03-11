import time
import threading
import subprocess
import shutil
from app import TalkyApp, _Dispatcher
from tools.core_audio import AudioCaptureTool
from tools.core_stt import STTTool
from tools.core_llm import LLMFormatter
from tools.core_output import OutputInjector
from tools import core_audio_feedback as chime
from tools.core_stats import StatsStore
from tools.meeting_mode import MeetingSession
from tools.meeting_llm import MeetingSummarizer


_talky_started_ollama = False
_ollama_start_method = None  # "app" or "serve"


def _is_ollama_app_installed():
    """Check if Ollama.app is installed on macOS."""
    import os
    return os.path.isdir("/Applications/Ollama.app")


def _launch_ollama_app_icon_only():
    """Launch Ollama.app in background (menu bar icon only, no chat window)."""
    # -g = don't bring to foreground, -j = launch hidden
    subprocess.Popen(
        ["open", "-g", "-j", "-a", "Ollama"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Ollama always opens a chat window on startup regardless of launch flags.
    # Poll aggressively to close it and hide the dock icon as fast as possible.
    def _close_ollama_windows():
        for _ in range(8):
            time.sleep(0.5)
            try:
                subprocess.run(
                    ["osascript", "-e",
                     'tell application "System Events"\n'
                     '  if exists process "Ollama" then\n'
                     '    tell process "Ollama"\n'
                     '      set visible to false\n'
                     '      repeat with w in windows\n'
                     '        try\n'
                     '          perform action "AXPress" of '
                     '(first button of w whose subrole is "AXCloseButton")\n'
                     '        end try\n'
                     '      end repeat\n'
                     '    end tell\n'
                     '  end if\n'
                     'end tell'],
                    capture_output=True, timeout=3,
                )
            except Exception:
                pass
    threading.Thread(target=_close_ollama_windows, daemon=True).start()


def ensure_ollama_running():
    """Start Ollama if installed but not already running. Returns True if started by us."""
    global _talky_started_ollama, _ollama_start_method
    try:
        result = subprocess.run(
            ["pgrep", "-x", "ollama"],
            capture_output=True,
        )
        if result.returncode == 0:
            print("[startup] Ollama is already running.", flush=True)
            # Ensure the menu bar icon is visible even if started via 'ollama serve'
            if _is_ollama_app_installed():
                _launch_ollama_app_icon_only()
                print("[startup] Ollama menu bar icon activated.", flush=True)
            return

        # Check if Ollama.app is installed (macOS GUI app)
        if _is_ollama_app_installed():
            _launch_ollama_app_icon_only()
            _talky_started_ollama = True
            _ollama_start_method = "app"
            print("[startup] Ollama started (menu bar icon visible).", flush=True)
        elif shutil.which("ollama"):
            # CLI-only install (e.g. via Homebrew) — no icon possible
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            _talky_started_ollama = True
            _ollama_start_method = "serve"
            print("[startup] Ollama serve started (CLI only, no icon).", flush=True)
        else:
            print("[startup] Ollama not found, skipping.", flush=True)
    except Exception as e:
        print(f"[startup] Could not start Ollama: {e}", flush=True)


def stop_ollama():
    """Stop Ollama if Talky started it."""
    if not _talky_started_ollama:
        return
    try:
        if _ollama_start_method == "app":
            subprocess.run(
                ["osascript", "-e", 'quit app "Ollama"'],
                capture_output=True, timeout=5,
            )
        else:
            subprocess.run(["pkill", "-x", "ollama"], capture_output=True, timeout=5)
        print("[shutdown] Ollama stopped.", flush=True)
    except Exception as e:
        print(f"[shutdown] Could not stop Ollama: {e}", flush=True)


def main():
    print("--- Initializing Talky ---", flush=True)
    ensure_ollama_running()

    stt_tool = STTTool(model_size="small", compute_type="int8")
    llm_tool = LLMFormatter(host="http://localhost:11434", model="qwen2.5:3b")
    output_tool = OutputInjector()
    stats_store = StatsStore()
    meeting_summarizer = MeetingSummarizer(host="http://localhost:11434", model="qwen2.5:3b")

    print("--- Models loaded. Starting app... ---", flush=True)

    def pipeline_loop(on_record_start, on_record_stop, on_processing, on_idle, on_warmup, on_ready, get_language, on_stats_update, app_ref):
        def on_ollama_state_change(is_offline):
            _Dispatcher.dispatch_to_main(lambda: app_ref.status_bar.set_ollama_offline(is_offline))
            
        llm_tool.on_state_change_callback = on_ollama_state_change

        on_warmup()
        # Initialize UI stats display on UI start
        on_stats_update(stats_store.get_formatted_stats())
        import numpy as np
        print("--- Warming up models ---", flush=True)
        stt_tool.transcribe(np.zeros(16000, dtype=np.float32), is_warmup=True)
        
        # Ping Ollama server to ensure it's responsive before formatting
        import requests
        for _ in range(10):
            try:
                res = requests.get("http://localhost:11434/", timeout=0.5)
                if res.status_code == 200:
                    break
            except Exception:
                time.sleep(0.5)

        try:
            llm_tool.format_text("warmup phrase")
        except Exception:
            pass
        print("--- Warmup complete ---", flush=True)
        on_ready()

        def _on_start():
            chime.play_start()
            on_record_start()

        audio_tool = AudioCaptureTool(
            hotkey='fn',
            on_record_start=_on_start,
            on_record_stop=on_record_stop,
        )

        # ---- Meeting mode wiring ----
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
                session = meeting_session
                threading.Thread(target=session.stop, daemon=True).start()

        app_ref._on_meeting_start = start_meeting
        app_ref._on_meeting_stop = stop_meeting

        # ---- Dictation loop ----
        while True:
            try:
                audio_buffer = audio_tool.record_while_pressed()

                if len(audio_buffer) == 0:
                    on_idle()
                    continue

                chime.play_stop()

                on_processing()
                start_time = time.time()

                lang = get_language()
                raw_text = stt_tool.transcribe(audio_buffer, language=lang)
                if not raw_text:
                    print("[pipeline] No speech detected.", flush=True)
                    on_idle()
                    continue

                cleaned_text = llm_tool.format_text(raw_text, language=lang)
                if not cleaned_text:
                    on_idle()
                    continue

                output_tool.inject(cleaned_text)
                elapsed = time.time() - start_time
                print(f"[pipeline] Done in {elapsed:.2f}s", flush=True)

                # Update Stats
                duration_seconds = len(audio_buffer) / 16000.0
                words_count = len(cleaned_text.split())
                stats_store.add_dictation(duration_seconds, words_count)
                on_stats_update(stats_store.get_formatted_stats())

                on_idle()

            except Exception as e:
                print(f"[pipeline] Error: {e}", flush=True)
                on_idle()

    app = TalkyApp(pipeline_loop, on_cleanup=stop_ollama)
    app.run()


if __name__ == "__main__":
    main()
