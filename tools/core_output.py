import pyautogui
import pyperclip
import time

class OutputInjector:
    def __init__(self):
        # We assume pyautogui is configured properly for the OS
        # PyAutoGUI's default pause is 0.1s, we reduce it for lower latency
        pyautogui.PAUSE = 0.05
    
    def inject(self, text: str) -> bool:
        """
        Injects the formatted text into the current cursor position.
        Uses the clipboard copy-paste method for speed and reliability.
        """
        if not text:
            return False
            
        print("[core_output] Injecting formatted payload...")
        try:
            # 1. Save current clipboard content (optional, but polite)
            old_clipboard = pyperclip.paste()
            
            # 2. Copy the new text
            pyperclip.copy(text)
            
            # 3. Simulate Ctrl+V to paste
            # Note: On Mac this should be 'command', 'v'. 
            # PyAutoGUI's hotkey handles modifier keys depending on OS, but we force 'ctrl' for Windows.
            # If running cross-platform, sys.platform checks are ideal. Here we assume Windows per user OS.
            pyautogui.hotkey('ctrl', 'v')
            
            # 4. Optional: We skip restoring the clipboard immediately 
            # because the OS needs a tiny fraction of a second to complete the paste event before the clipboard changes back.
            # Leaving the text in the clipboard acts as a good fallback if focus was lost.
            
            print("[core_output] Injection successful.")
            return True
            
        except Exception as e:
            print(f"[core_output] Error injecting via clipboard: {e}")
            print("[core_output] Falling back to slow typing...")
            try:
                pyautogui.write(text, interval=0.01)
                return True
            except Exception as write_e:
                print(f"[core_output] Fallback also failed: {write_e}")
                return False

if __name__ == "__main__":
    # Test execution
    injector = OutputInjector()
    print("Testing output injection. Focus a text field within 3 seconds...")
    time.sleep(3)
    injector.inject("This is a test injection.")
