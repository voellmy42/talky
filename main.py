import time
from app import TalkyApp
from tools.core_audio import AudioCaptureTool
from tools.core_stt import STTTool
from tools.core_llm import LLMFormatter
from tools.core_output import OutputInjector
from tools import core_audio_feedback as chime


def main():
    print("--- Initializing Talky ---", flush=True)

    stt_tool = STTTool(model_size="base", compute_type="int8")
    llm_tool = LLMFormatter(host="http://localhost:11434", model="qwen2.5:3b")
    output_tool = OutputInjector()

    print("--- Models loaded. Starting app... ---", flush=True)

    def pipeline_loop(on_record_start, on_record_stop, on_processing, on_idle):
        def _on_start():
            chime.play_start()
            on_record_start()

        audio_tool = AudioCaptureTool(
            hotkey='fn',
            on_record_start=_on_start,
            on_record_stop=on_record_stop,
        )

        while True:
            try:
                audio_buffer = audio_tool.record_while_pressed()

                if len(audio_buffer) == 0:
                    on_idle()
                    continue

                chime.play_stop()

                on_processing()
                start_time = time.time()

                raw_text = stt_tool.transcribe(audio_buffer)
                if not raw_text:
                    print("[pipeline] No speech detected.", flush=True)
                    on_idle()
                    continue

                cleaned_text = llm_tool.format_text(raw_text)
                if not cleaned_text:
                    on_idle()
                    continue

                output_tool.inject(cleaned_text)
                elapsed = time.time() - start_time
                print(f"[pipeline] Done in {elapsed:.2f}s", flush=True)

                on_idle()

            except Exception as e:
                print(f"[pipeline] Error: {e}", flush=True)
                on_idle()

    app = TalkyApp(pipeline_loop)
    app.run()


if __name__ == "__main__":
    main()
