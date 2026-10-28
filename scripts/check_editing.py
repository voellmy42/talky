"""Exercise real local voice-editing models on synthetic text, optionally synthetic speech."""
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'

from tools.core_config import ConfigManager
from tools.core_model_store import ModelStore
from tools.core_mlx_llm import EmbeddedFormatter


def checks(case, result):
    errors = []
    text = result.text.casefold()
    if result.outcome != 'edited':
        errors.append(result.reason)
    rules = case['checks']
    for word in rules.get('contains', []):
        if word.casefold() not in text:
            errors.append('missing: ' + word)
    for word in rules.get('not_contains', []):
        if word.casefold() in text:
            errors.append('unexpected: ' + word)
    if text.strip(' .!?\n\"\'') in [word.casefold() for word in rules.get('not_exact', [])]:
        errors.append('followed selected-text instruction')
    if rules.get('contains_any') and not any(word.casefold() in text for word in rules['contains_any']):
        errors.append('missing expected translation')
    if rules.get('shorter') and len(result.text) >= len(case['selected_text']):
        errors.append('not shorter')
    if rules.get('bullets') and sum(line.lstrip().startswith(('- ', '* ', '• '))
                                  for line in result.text.splitlines()) < rules['bullets']:
        errors.append('missing bullet structure')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('build/mlx-models'))
    parser.add_argument('--model', choices=['qwen3-1.7b', 'qwen3-4b'], default='qwen3-1.7b')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--with-speech', action='store_true')
    args = parser.parse_args()
    editor = EmbeddedFormatter(ModelStore(args.model, args.root))
    cases = json.loads(Path('tests/fixtures/editing-v1.json').read_text())
    records, speech = [], []
    try:
        pending = editor.set_enabled(True)
        if pending is None:
            raise RuntimeError('Install the pinned model first')
        pending.result()
        for case in cases:
            start = time.monotonic()
            result = editor.edit_session(case['selected_text'], case['instruction'], language=case['speech_language'])
            records.append(dict(case, result=asdict(result), elapsed_seconds=time.monotonic()-start,
                                check_failures=checks(case, result)))
        if args.with_speech:
            import av
            import numpy as np
            from tools.core_stt import STTTool
            stt = STTTool()
            with tempfile.TemporaryDirectory(dir='build') as root:
                config = ConfigManager(str(Path(root) / 'config.json'))
                for language, voice, command, source in (
                    ('en', 'Samantha', 'Make this shorter and keep all numbers.',
                     'I am writing to request that you keep exactly 42 records and do not delete the backup.'),
                    ('de', 'Anna', 'Mach das kürzer und behalte alle Zahlen.',
                     'Ich möchte dich darum bitten, genau 42 Einträge zu behalten und die Sicherung nicht zu löschen.')):
                    config.set_language(language)
                    selected_language = ConfigManager(config._path).get_language()
                    audio_path = Path(root) / (language + '.aiff')
                    subprocess.run(['say', '-v', voice, '-r', '160', '-o', str(audio_path), command], check=True)
                    resampler = av.AudioResampler(format='flt', layout='mono', rate=16000)
                    chunks = []
                    with av.open(str(audio_path)) as audio:
                        for frame in audio.decode(audio=0):
                            chunks.extend(part.to_ndarray().flatten() for part in resampler.resample(frame))
                    chunks.extend(part.to_ndarray().flatten() for part in resampler.resample(None))
                    transcript = stt.transcribe(np.concatenate(chunks), language=selected_language)
                    edited = editor.edit_session(source, transcript, language=selected_language)
                    speech.append(dict(language=selected_language, voice=voice, synthetic_command=command,
                                       transcript=transcript, selected_text=source, result=asdict(edited)))
        report = dict(model=editor.store.manifest['repo_id'], revision=editor.store.manifest['revision'],
                      load_seconds=editor.load_seconds, count=len(records),
                      passed_checks=sum(not row['check_failures'] for row in records), records=records,
                      synthetic_speech=speech,
                      limitations='Synthetic text/speech; checks are not a proof of meaning or language fidelity. '
                                  'No microphone, live app selection or paste was used.')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
        print(json.dumps(report, indent=2, ensure_ascii=False))
    finally:
        editor.close()


if __name__ == '__main__':
    main()
