# LLM Formatter Standard Operating Procedure (SOP)

## Purpose
Take the raw, raw transcribed text (often containing filler words, hesitations, and poor grammar) and format it perfectly without ever changing the meaning or tone.

## Tool Execution Context
- **Script path**: `tools/core_llm.py`
- **Dependencies**: `requests` or `ollama-python`

## Input Data Shape
- `raw_transcription` (String)

## Output Data Shape
- Returns `cleaned_text` (String)

## Execution Rules
- **API Endpoint**: The script must communicate exclusively with the local Ollama instance (usually `http://localhost:11434/api/generate`). No external LLM APIs (OpenAI, Anthropic) are permitted.
- **Model Selection**: Defaults to `llama3:8b` or `phi3:mini` (configurable) as they are fast enough for the <2s latency requirement.
- **Prompting Strictness**: The system prompt must aggressively enforce the "Format Only" rule. 
  - *Example System Prompt*: "You are a dictation formatting engine. Your ONLY job is to take the user's spoken text, remove filler words (um, uh, like), and fix obvious grammar/punctuation errors. DO NOT add new information, DO NOT summarize, DO NOT answer questions in the text. Output ONLY the corrected text and nothing else."
- **Keep-Alive**: Make sure Ollama keeps the model loaded in memory by sending a blank keep-alive request or configuring the Ollama service `OLLAMA_KEEP_ALIVE` variable.

## Error States & Handling
- *Ollama Service Offline* -> Bypass the LLM entirely and return `raw_transcription` as a fallback, logging the failure as a warning. Do not crash the dictation pipeline over an LLM failure.
