import multiprocessing
import sys
import os
if '--check-ai-model' in sys.argv:
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
import fcntl
import time
import threading
import ApplicationServices
import AVFoundation
from app import TalkyApp, _Dispatcher

# When launched as a .app from Finder, macOS provides only a minimal PATH
# (/usr/bin:/bin:/usr/sbin:/sbin). Patch in common tool locations so that
# ollama, pgrep, etc. are found regardless of how the app was launched.
_EXTRA_PATHS = [
    "/usr/local/bin",
    "/opt/homebrew/bin",
    "/opt/homebrew/sbin",
]
_current_path = os.environ.get("PATH", "")
_path_parts = _current_path.split(os.pathsep)
for _p in _EXTRA_PATHS:
    if _p not in _path_parts:
        _path_parts.insert(0, _p)
os.environ["PATH"] = os.pathsep.join(_path_parts)
from tools.core_audio import AudioCaptureTool
from tools.core_stt import STTTool
from tools.core_mlx_llm import EmbeddedFormatter
from tools.core_model_store import ModelStore
from tools.core_output import OutputInjector
from tools.core_focus import FocusTracker
from tools.core_session import DictationController
from tools import core_audio_feedback as chime
from tools.core_stats import StatsStore
from tools.core_config import ConfigManager
from tools.meeting_mode import MeetingSession
from tools.meeting_llm import MeetingSummarizer


_instance_lock_file = None


def _acquire_single_instance_lock():
    global _instance_lock_file
    _instance_lock_file = open(os.path.expanduser("~/.talky.lock"), "w")
    try:
        fcntl.flock(_instance_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("[startup] Talky is already running.", flush=True)
        sys.exit(0)


def _needs_setup():
    microphone_ok = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(
        AVFoundation.AVMediaTypeAudio) == AVFoundation.AVAuthorizationStatusAuthorized
    return not (ConfigManager().is_setup_complete()
                and ApplicationServices.AXIsProcessTrustedWithOptions(
                    {ApplicationServices.kAXTrustedCheckOptionPrompt: False}) and microphone_ok)


def main():
    _acquire_single_instance_lock()
    print("--- Initializing Talky ---", flush=True)

    needs_setup = _needs_setup()

    stt_tool = STTTool(model_size="small", compute_type="int8")
    llm_tool = EmbeddedFormatter(ModelStore())
    focus_tracker = FocusTracker()
    output_tool = OutputInjector(focus_tracker=focus_tracker)
    stats_store = StatsStore()
    meeting_summarizer = MeetingSummarizer(host="http://localhost:11434", model="gemma4:latest")

    print("--- Models loaded. Starting app... ---", flush=True)

    def pipeline_loop(
        on_record_start,
        on_record_stop,
        on_processing,
        on_idle,
        on_warmup,
        on_ready,
        get_language,
        get_formatting_mode,
        on_stats_update,
        app_ref,
    ):
        controller = DictationController(stt_tool, llm_tool, output_tool,
                                         app_ref._on_session_status)
        app_ref._controller = controller
        app_ref._output = output_tool
        app_ref._formatter = llm_tool
        llm_tool.on_state = lambda state, message: _Dispatcher.dispatch_to_main(
            lambda: app_ref.status_bar.set_ai_status(state, message))
        llm_tool.on_state(llm_tool.state, llm_tool.message)

        on_warmup()
        # Initialize UI stats display on UI start
        on_stats_update(stats_store.get_formatted_stats())
        import numpy as np
        print("--- Warming up models ---", flush=True)
        stt_tool.transcribe(np.zeros(16000, dtype=np.float32), is_warmup=True)
        if get_formatting_mode() == 'polished':
            llm_tool.set_enabled(True)

        def _on_start():
            chime.play_start()

        audio_tool = AudioCaptureTool(
            hotkey='fn',
            on_record_start=_on_start,
            on_capture_request=lambda: controller.begin(
                focus_tracker.capture(), get_language(), get_formatting_mode()),
            on_cancel=controller.cancel,
            on_busy=lambda: app_ref._show_notice("Processing… Esc to cancel"),
            get_toggle_shortcut=app_ref.status_bar.get_toggle_shortcut,
        )
        app_ref._audio = audio_tool
        print("--- Warmup complete ---", flush=True)
        on_ready()

        # ---- Meeting mode wiring ----
        meeting_session = None

        def start_meeting():
            nonlocal meeting_session
            if controller.state != 'ready' or meeting_session is not None:
                app_ref._show_notice('Finish dictation before starting a meeting')
                return
            lang = get_language()

            def on_chunk(count):
                print(f"[pipeline] Meeting chunk #{count} transcribed.", flush=True)

            def on_summarizing():
                _Dispatcher.dispatch_to_main(lambda: app_ref.overlay.stop_meeting_timer())
                _Dispatcher.dispatch_to_main(lambda: app_ref.overlay.set_meeting_style())
                _Dispatcher.dispatch_to_main(lambda: app_ref.overlay.show("Summarizing..."))

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

        # Capture and inference are sequential; Escape remains live on the
        # event-tap thread. New presses while processing give explicit feedback.
        while not audio_tool._closed:
            audio_buffer = audio_tool.record_while_pressed()
            if audio_tool._closed:
                break
            if len(audio_buffer):
                chime.play_stop()
            timings = controller.process(audio_buffer, audio_tool.released_at)
            result = controller.last_result
            if timings and result:
                elapsed = timings.get('release_to_paste_sent_seconds',
                                      timings.get('release_to_result_seconds', 0.0))
                print('[latency] ' + ' '.join(f'{key}={value:.3f}s'
                                             for key, value in timings.items()), flush=True)
                stats_store.add_dictation(len(audio_buffer) / 16000.0,
                                          len(result.text.split()), elapsed)
                on_stats_update(stats_store.get_formatted_stats())

    app = TalkyApp(pipeline_loop, needs_setup=needs_setup)
    app.run()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    if '--check-ai-download' in sys.argv:
        import argparse
        parser = argparse.ArgumentParser(description='Check packaged TLS/download/integrity without downloading weights')
        parser.add_argument('--check-ai-download', action='store_true')
        parser.add_argument('--model-root', required=True)
        args = parser.parse_args()
        manifest = ModelStore().manifest
        manifest = dict(manifest, files=[entry for entry in manifest['files'] if entry['name'] == 'config.json'])
        formatter = EmbeddedFormatter(ModelStore(root=args.model_root, manifest=manifest))
        try:
            formatter.install().result()
            if formatter.state != 'unloaded':
                raise RuntimeError(formatter.message)
            print('Talky packaged download check passed (pinned config, TLS and integrity).', flush=True)
        finally:
            formatter.close()
    elif '--check-ai-model' in sys.argv:
        import argparse
        parser = argparse.ArgumentParser(description='Offline packaged AI inference check; no recording or paste')
        parser.add_argument('--check-ai-model', action='store_true')
        parser.add_argument('--model-root', required=True)
        args = parser.parse_args()
        formatter = EmbeddedFormatter(ModelStore(root=args.model_root))
        try:
            pending = formatter.set_enabled(True)
            assert pending is not None, 'Install the pinned model first'
            pending.result()
            assert formatter.state == 'ready', formatter.message
            result = formatter.format_session('hello world', mode='polished', budget=10)
            assert result.reason == 'accepted', result.reason
            print('Talky offline AI check passed (local model, tokenizer, generation and validation).', flush=True)
        finally:
            formatter.close()
    elif '--check-build' in sys.argv:
        # Exercise bundled native libraries and Metal shaders without opening
        # the microphone, downloading models, reading focus or sending input.
        import mlx.core as mx
        import mlx_lm
        import certifi
        import ssl
        from tools.core_paths import resource_path
        assert os.path.isfile(resource_path('talky-logo.jpg'))
        assert os.path.isfile(resource_path('tools/model_manifests.json'))
        assert os.path.isfile(certifi.where())
        # A present CA bundle alone does not prove the packaged SSL runtime works.
        ssl.create_default_context(cafile=certifi.where())
        check = mx.array([1, 2], dtype=mx.float32) + 1
        mx.eval(check)
        assert check.tolist() == [2.0, 3.0]
        print('Talky build check passed (Metal, native imports and resources).', flush=True)
    else:
        main()
