import sys
sys.path.append(".")
import tools.core_audio as ca
import time

audio = ca.AudioCaptureTool(hotkey='fn')
print("Holding fn...")
# simulate press
audio._handle_press(time.time())
time.sleep(2)
# simulate release
audio._handle_release(time.time())
print("Draining queue...")
arr = audio.drain_audio_queue()
print("Audio length:", len(arr))

