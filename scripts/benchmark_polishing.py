"""Compare complete, validated formatting on synthetic fixtures; never record or paste."""
import argparse
from collections import Counter
from dataclasses import asdict
import json
import os
from pathlib import Path
import platform
import resource
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.core_llm import LLMFormatter, preserves_dictation
from tools.core_model_store import ModelStore
from tools.core_mlx_llm import EmbeddedFormatter


def percentile(values, fraction):
    values = sorted(values)
    return values[min(len(values) - 1, max(0, int(len(values) * fraction + .999) - 1))]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', choices=['qwen3-1.7b', 'qwen3-4b'], default='qwen3-1.7b')
    parser.add_argument('--root', type=Path, default=None)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--budget', type=float, default=1.5)
    parser.add_argument('--with-whisper', action='store_true')
    parser.add_argument('--fixtures', type=Path, default=Path('tests/fixtures/polishing-v1.json'))
    args = parser.parse_args()
    # No model downloads may occur in benchmark/inference; install explicitly first.
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    import mlx.core as mx
    import psutil
    available_before = psutil.virtual_memory().available
    stt = None
    if args.with_whisper:
        import numpy as np
        from tools.core_stt import STTTool
        stt = STTTool()
        stt.transcribe(np.zeros(16000, dtype=np.float32), is_warmup=True)
    formatter = EmbeddedFormatter(ModelStore(args.model, args.root))
    records = []
    try:
        future = formatter.set_enabled(True)
        if future is None:
            raise RuntimeError('Install the model explicitly before benchmarking')
        future.result()
        if formatter.state != 'ready':
            raise RuntimeError(formatter.message)
        for item in json.loads(args.fixtures.read_text()):
            start = time.perf_counter()
            fast = LLMFormatter.fast_cleanup(item['raw'], item['language'])
            fast_seconds = time.perf_counter() - start
            start = time.perf_counter()
            result = formatter.format_session(item['raw'], language=item['language'],
                                              mode='polished', budget=args.budget)
            elapsed = time.perf_counter() - start
            records.append(dict(item, fast=fast, fast_seconds=fast_seconds,
                                elapsed_seconds=elapsed, result=asdict(result),
                                exact_reference=(result.text == item['expected']) if item.get('expected') else None,
                                differs_from_fast=result.text != fast,
                                restricted_policy_pass=preserves_dictation(item['raw'], result.text, item['language'])))
        def summarize(rows):
            elapsed = [row['elapsed_seconds'] for row in rows]
            return dict(count=len(rows), outcomes=dict(Counter(row['result']['reason'] for row in rows)),
                        p50_seconds=statistics.median(elapsed), p95_seconds=percentile(elapsed, .95),
                        fast_p50_seconds=statistics.median(row['fast_seconds'] for row in rows),
                        differs_from_fast=sum(row['differs_from_fast'] for row in rows),
                        reference_count=sum(bool(row.get('expected')) for row in rows),
                        exact_reference=sum(row['exact_reference'] is True for row in rows),
                        fast_exact_reference=sum(bool(row.get('expected')) and row['fast'] == row['expected'] for row in rows),
                        restricted_policy_failures=sum(not row['restricted_policy_pass'] for row in rows))
        report = dict(model=formatter.store.manifest, platform=platform.platform(),
                      python=platform.python_version(), device=mx.device_info(),
                      whisper_resident=stt is not None, budget_seconds=args.budget,
                      load_seconds=formatter.load_seconds,
                      peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                      peak_mlx_bytes=mx.get_peak_memory(), summary=summarize(records),
                      available_memory_before_bytes=available_before,
                      available_memory_after_bytes=psutil.virtual_memory().available,
                      splits={split: summarize([r for r in records if r['split'] == split])
                              for split in ('development', 'heldout')},
                      records=records,
                      limitations='Synthetic text formatting only; not speech accuracy or release-to-paste. '
                                   'Exact reference is a strict formatting metric, not a semantic proof.')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
        print(json.dumps({k: report[k] for k in ('summary', 'splits', 'load_seconds',
                                                'peak_rss_bytes', 'peak_mlx_bytes')}, indent=2))
    finally:
        formatter.close()


if __name__ == '__main__':
    main()
