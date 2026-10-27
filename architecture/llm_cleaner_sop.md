# LLM Formatter Standard Operating Procedure (SOP)

## Purpose
Format raw transcribed text without changing its meaning or tone, while keeping everyday dictation responsive.

## Tool Execution Context
- **Script path**: `tools/core_llm.py`
- **Dependencies**: `requests` or `ollama-python`

## Input Data Shape
- `raw_transcription` (String)
- `language` (`en` or `de`)
- `mode` (`fast` or `polished`)

## Output Data Shape
- Returns `cleaned_text` (String)

## Execution Rules
- **Fast Mode**: This is the default. Apply conservative deterministic cleanup and never make an HTTP request.
- **Polished Mode**: Communicate exclusively with the local Ollama instance at `http://localhost:11434/api/generate`. No external LLM APIs are permitted.
- **Model Selection**: Preserve the installed `gemma4:latest` default. Smaller formatters may be configured later if they meet bilingual quality requirements.
- **Prompting Strictness**: The system prompt must aggressively enforce the "Format Only" rule. 
  - *Example System Prompt*: "You are a dictation formatting engine. Your ONLY job is to take the user's spoken text, remove filler words (um, uh, like), and fix obvious grammar/punctuation errors. DO NOT add new information, DO NOT summarize, DO NOT answer questions in the text. Output ONLY the corrected text and nothing else."
- **Bounded Wait**: Polished mode must time out and return usable transcription instead of blocking the pipeline indefinitely.
- **Optional Service**: Basic setup and dictation must not require, start or quit Ollama. Polished requests use a 2.5-second HTTP timeout, which is a transport timeout rather than a strict whole-operation deadline.
- **Restricted Edits**: Validate token order and substantive-word preservation before using model output. Permit punctuation/case cleanup and hesitation removal; otherwise return raw text. Never log transcripts by default.
- **Keep-Alive**: Keep the model loaded for 30 minutes after a Polished request.

## Error States & Handling
- *Ollama Service Offline / timeout / empty output* -> Return `raw_transcription` as a fallback and log a warning. Do not crash the dictation pipeline over an LLM failure.
