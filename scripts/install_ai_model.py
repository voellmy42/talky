"""Explicit local model installation for development/benchmarks; no inference."""
import argparse
from pathlib import Path
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.core_model_store import ModelStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', choices=['qwen3-1.7b', 'qwen3-4b'], default='qwen3-1.7b')
    parser.add_argument('--root', type=Path, default=None)
    args = parser.parse_args()
    store = ModelStore(args.model, args.root)
    cancel = threading.Event()
    last = -1
    def progress(done, total):
        nonlocal last
        percent = done * 100 // total
        if percent // 10 != last:
            last = percent // 10
            print(f'{percent}% ({done}/{total} bytes)', flush=True)
    try:
        print(f'Installing {store.manifest["repo_id"]} at {store.manifest["revision"]}', flush=True)
        store.install(cancel, progress)
        print('Verified model:', store.path, flush=True)
    except KeyboardInterrupt:
        cancel.set()
        print('Cancelled; incomplete files remain in staging for retry.', file=sys.stderr)
        return 130
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
