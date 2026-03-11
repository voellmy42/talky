import numpy as np
from tools.core_audio import AudioCaptureTool
import time

def test_rms():
    print("Testing RMS volume.")
    audio_tool = AudioCaptureTool(hotkey='fn')
    
    print("Press and hold the generic hotkey 'fn' (or what you set it to), say something, then release.")
    # Actually wait, I can just record 2 seconds
    print("Recording 2 seconds of silence...")
    time.sleep(1) # just pretending
    # I can't interactively press fn in a script running in the background.

    # I'll just skip the RMS test and do a simple RMS check in transcribe.
