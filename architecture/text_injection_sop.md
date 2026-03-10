# Text Injection Standard Operating Procedure (SOP)

## Purpose
Deliver the final `cleaned_text` payload directly into whatever application the user is currently focused on, seamlessly, as if they had typed it.

## Tool Execution Context
- **Script path**: `tools/core_output.py`
- **Dependencies**: `pyautogui`, `pyperclip`

## Input Data Shape
- `cleaned_text` (String)

## Output Data Shape
- Execution result (Boolean success/failure)

## Execution Rules
- **Injection Method**: Due to the unreliability of automating raw keystrokes (like typing out long strings character by character), the primary delivery mechanism MUST be:
  1. Save current clipboard state.
  2. Copy `cleaned_text` to clipboard.
  3. Simulate `Ctrl+V` (or `Cmd+V` on Mac) keypress.
  4. (Optional) Restore previous clipboard state after a slight delay.
- **OS Agnostic**: Use environment checks to route to `Ctrl+V` or `Cmd+V` as necessary.
- **Focus Preservation**: Ensure the act of injection does not steal focus from the user's active application.

## Error States & Handling
- *Clipboard Access Error* -> Fallback to `pyautogui.write(cleaned_text)` (typing it out slowly).
- *No Active Window / Focus Lost* -> The text should remain copied to the clipboard, and a generic system notification/beep should occur indicating the text is ready to paste manually.
