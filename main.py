import time
import threading
from app import TalkyApp, _Dispatcher
from tools.core_audio import AudioCaptureTool
from tools.core_stt import STTTool
from tools.core_llm import LLMFormatter
from tools.core_output import OutputInjector
from tools import core_audio_feedback as chime
from tools.core_stats import StatsStore
from tools.meeting_mode import MeetingSession
from tools.meeting_llm import MeetingSummarizer


def main():
    print("--- Initializing Talky ---", flush=True)

    stt_tool = STTTool(model_size="small", compute_type="int8")
    llm_tool = LLMFormatter(host="http://localhost:11434", model="qwen2.5:3b")
    output_tool = OutputInjector()
    stats_store = StatsStore()
    meeting_summarizer = MeetingSummarizer(host="http://localhost:11434", model="qwen2.5:3b")

    print("--- Models loaded. Starting app... ---", flush=True)

    def pipeline_loop(on_record_start, on_record_stop, on_processing, on_idle, on_warmup, on_ready, get_language, on_stats_update, app_ref):
        on_warmup()
        # Initialize UI stats display on UI start
        on_stats_update(stats_store.get_formatted_stats())
        import numpy as np
        print("--- Warming up models ---", flush=True)
        stt_tool.transcribe(np.zeros(16000, dtype=np.float32))
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

    app = TalkyApp(pipeline_loop)
    app.run()


if __name__ == "__main__":
    main()
