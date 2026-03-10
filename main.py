import time
from tools.core_audio import AudioCaptureTool
from tools.core_stt import STTTool
from tools.core_llm import LLMFormatter
from tools.core_output import OutputInjector

class TalkyRouter:
    def __init__(self):
        print("--- Initializing B.L.A.S.T Talky System ---", flush=True)
        # Note: 'f8' is default.
        self.audio_tool = AudioCaptureTool(hotkey='f8')
        
        # Load whisper base model into RAM once
        self.stt_tool = STTTool(model_size="tiny", compute_type="int8")  # We can upgrade to base or small later
        
        # Connect to local Ollama API
        self.llm_tool = LLMFormatter(host="http://localhost:11434", model="qwen2.5:3b")
        
        # Initialize text injector
        self.output_tool = OutputInjector()
        print("--- System Ready! ---", flush=True)

    def run_loop(self):
        """
        The main event loop. Listens indefinitely for the hotkey press and drives the pipeline.
        """
        while True:
            try:
                # 1. Capture Audio (Blocks until hotkey pressed, returns array on release)
                audio_buffer = self.audio_tool.record_while_pressed()
                
                # If hotkey was tapped quickly without speaking, ignore
                if len(audio_buffer) == 0:
                    continue
                    
                start_time = time.time()
                
                # 2. Transcribe
                raw_text = self.stt_tool.transcribe(audio_buffer)
                if not raw_text:
                    print("No speech detected.")
                    continue
                
                # 3. Clean and Format via LLM
                cleaned_text = self.llm_tool.format_text(raw_text)
                if not cleaned_text:
                    continue
                
                # 4. Inject
                success = self.output_tool.inject(cleaned_text)
                
                end_time = time.time()
                print(f"Pipeline completed in {end_time - start_time:.2f} seconds.\n", flush=True)
                
            except KeyboardInterrupt:
                print("\nExiting Router loop.")
                break
            except Exception as e:
                print(f"Pipeline error: {e}")

if __name__ == "__main__":
    router = TalkyRouter()
    try:
        router.run_loop()
    except KeyboardInterrupt:
        pass
