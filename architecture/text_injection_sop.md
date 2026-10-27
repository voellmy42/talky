# Text Injection Standard Operating Procedure (SOP)

## Purpose
Deliver text only when the original destination can still be identified. Otherwise retain it in memory for explicit Copy Last Dictation.

## Tool Execution Context
- **Script path**: `tools/core_output.py`
- **Dependencies**: `Quartz`, `AppKit`, `pyautogui`, `pyperclip`

## Input Data Shape
- `cleaned_text` (String)

## Output Data Shape
- Execution result (Boolean success/failure)

## Execution Rules
- **Injection Method**: Due to the unreliability of automating raw keystrokes (like typing out long strings character by character), the primary delivery mechanism MUST be:
  1. Save every current macOS pasteboard item and type, including rich content.
  2. Copy `cleaned_text` to clipboard.
  3. Post native `Cmd+V` events with Quartz. Do not launch an AppleScript subprocess.
  4. Restore the previous clipboard after a slight delay only if the user has not copied something new.
- **Rapid Dictations**: Use a generation counter so an older restore thread cannot overwrite a newer dictation payload.
- **OS Agnostic**: Use environment checks to route to `Ctrl+V` or `Cmd+V` as necessary.
- **Focus Preservation**: Ensure the act of injection does not steal focus from the user's active application.
- **Destination Identity**: Compare the starting PID, Accessibility window and text element, plus selection when available. Reject unsupported and secure fields. Recheck immediately before dispatch.
- **Dispatch Guard**: Validate the session generation and clipboard ownership before posting paste. Cancellation must block late output. Never send Enter.
- **Outcome**: `sent` means paste events were dispatched, not destination acceptance. `available` means retained text can be explicitly copied. Never type characters as an automatic fallback.

## Error States & Handling
- *Clipboard Access Error* -> Restore the previous clipboard if still owned; retain transcript for explicit copy.
- *No Active Window / Focus Lost* -> Do not replace the clipboard or paste. Show a brief outcome and keep Copy Last Dictation available.
