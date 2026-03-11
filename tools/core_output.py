import pyautogui
import pyperclip
import time

class OutputInjector:
    def __init__(self):
        # We assume pyautogui is configured properly for the OS
        # Pause between keystrokes — 0.08s balances speed vs modifier reliability
        pyautogui.PAUSE = 0.08
        
        # Warm up pyautogui's accessibility API on macOS to prevent dropping the 
        # first modifier key press, which results in a bare 'v' instead of Cmd+V.
        import sys
        try:
            mod = 'command' if sys.platform == 'darwin' else 'ctrl'
            pyautogui.keyDown(mod)
            pyautogui.keyUp(mod)
        except Exception:
            pass
    
    def inject(self, text: str) -> bool:
        """
        Injects the formatted text into the current cursor position.
        Uses the clipboard copy-paste method for speed and reliability.
        """
        if not text:
            return False
            
        print("[core_output] Injecting formatted payload...")
        try:
            # 1. Save current clipboard content
            old_clipboard = pyperclip.paste()
            
            # 2. Copy the new text
            pyperclip.copy(text)
            
            import sys
            import threading

            # 3. Brief pause to let any modifier key state (e.g. Fn release) settle
            time.sleep(0.15)
            
            # 4. Simulate Cmd+V / Ctrl+V to paste
            #    On macOS, pyautogui can drop the first modifier key press, so 
            #    we use AppleScript for perfect reliability on the first run.
            if sys.platform == 'darwin':
                import subprocess
                subprocess.run(['osascript', '-e', 'tell application "System Events" to keystroke "v" using command down'])
            else:
                mod = 'ctrl'
                pyautogui.keyDown(mod)
                time.sleep(0.03)
                pyautogui.press('v')
                pyautogui.keyUp(mod)
            
            # 4. Restore original clipboard after a short delay
            #    (OS needs time to complete the paste event)
            def _restore():
                time.sleep(0.2)
                try:
                    pyperclip.copy(old_clipboard)
                except Exception:
                    pass
            threading.Thread(target=_restore, daemon=True).start()
            
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
