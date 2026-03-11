import sys
sys.path.append(".")
import threading
import time
import main
import app
import tools.core_audio as ca

def patch_handle_press(now):
    print("PATCHED HANDLE PRESS", flush=True)
    # ca.AudioCaptureTool._handle_press(self, now) -- wait, we need instance...

original_record = ca.AudioCaptureTool.record_while_pressed

def hook_record(self):
    print("HOOK TRIGGERED", flush=True)
    time.sleep(1) # wait for initialization
    threading.Thread(target=lambda: self._handle_press(time.time()), daemon=True).start()
    threading.Thread(target=lambda: (time.sleep(2), self._handle_release(time.time())), daemon=True).start()
    return original_record(self)

ca.AudioCaptureTool.record_while_pressed = hook_record

# Start main
main.main()
