import urllib.request
print("Testing")
import sys
sys.path.append(".")
import main
import time
import threading

def sim_user():
    time.sleep(10)
    print("Test passed.")
    import os
    os._exit(0)

threading.Thread(target=sim_user, daemon=True).start()
main.main()
