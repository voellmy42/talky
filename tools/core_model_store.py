"""Explicit, pinned downloads. Normal model loading never uses a remote repo ID."""
import hashlib
import json
import os
from pathlib import Path
import threading
import urllib.request

from tools.core_paths import resource_path


class DownloadCancelled(Exception):
    pass


class ModelStore:
    def __init__(self, model_key='qwen3-1.7b', root=None, manifest=None):
        if manifest is None:
            with open(resource_path('tools/model_manifests.json')) as source:
                manifest = json.load(source)[model_key]
        self.manifest = manifest
        self.model_key = model_key
        self.root = Path(root or '~/Library/Application Support/Talky/models').expanduser()
        self.path = self.root / (model_key + '-' + manifest['revision'])
        self.staging = self.root / ('.' + self.path.name + '.partial')
        self._install_lock = threading.Lock()
        for entry in manifest['files']:
            if Path(entry['name']).name != entry['name']:
                raise ValueError('Model manifest must contain flat file names')

    @property
    def download_bytes(self):
        return sum(entry['size'] for entry in self.manifest['files'])

    def installed(self):
        try:
            marker = json.loads((self.path / 'verified.json').read_text())
            return marker == self.manifest and all(
                (self.path / entry['name']).stat().st_size == entry['size']
                for entry in self.manifest['files'])
        except (OSError, ValueError):
            return False

    @staticmethod
    def _check_cancel(cancel):
        if cancel.is_set():
            raise DownloadCancelled()

    def _verify_file(self, path, entry, cancel):
        self._check_cancel(cancel)
        if not path.is_file() or path.stat().st_size != entry['size']:
            return False
        digest = hashlib.sha256() if 'sha256' in entry else hashlib.sha1()
        if 'git_sha1' in entry:
            digest.update(('blob %d\0' % entry['size']).encode())
        with path.open('rb') as source:
            while chunk := source.read(1024 * 1024):
                self._check_cancel(cancel)
                digest.update(chunk)
        return digest.hexdigest() == entry.get('sha256', entry.get('git_sha1'))

    def verify(self, cancel=None):
        cancel = cancel or threading.Event()
        return self.installed() and all(self._verify_file(
            self.path / entry['name'], entry, cancel) for entry in self.manifest['files'])

    def install(self, cancel, progress=lambda done, total: None, opener=None):
        """Retry reuses verified staging files; interrupted files are never activated."""
        if opener is None:
            import certifi
            import ssl
            context = ssl.create_default_context(cafile=certifi.where())
            def opener(url, timeout):
                return urllib.request.urlopen(url, timeout=timeout, context=context)
        with self._install_lock:
            self._check_cancel(cancel)
            if self.verify(cancel):
                return self.path
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.staging.mkdir(exist_ok=True, mode=0o700)
            done = 0
            for entry in self.manifest['files']:
                destination = self.staging / entry['name']
                if not self._verify_file(destination, entry, cancel):
                    partial = destination.with_name(destination.name + '.part')
                    url = 'https://huggingface.co/{}/resolve/{}/{}'.format(
                        self.manifest['repo_id'], self.manifest['revision'], entry['name'])
                    with opener(url, timeout=15) as response, partial.open('wb') as output:
                        received = 0
                        while chunk := response.read(1024 * 1024):
                            self._check_cancel(cancel)
                            received += len(chunk)
                            if received > entry['size']:
                                raise ValueError('Downloaded model file exceeds manifest size')
                            output.write(chunk)
                            progress(done + received, self.download_bytes)
                        output.flush()
                        os.fsync(output.fileno())
                    if not self._verify_file(partial, entry, cancel):
                        raise ValueError('Downloaded model file failed integrity verification')
                    partial.replace(destination)
                done += entry['size']
                progress(done, self.download_bytes)
            self._check_cancel(cancel)
            (self.staging / 'verified.json').write_text(json.dumps(self.manifest))
            # A corrupt existing installation is retained until the replacement is ready.
            if self.path.exists():
                import shutil
                shutil.rmtree(self.path)
            self.staging.replace(self.path)
            return self.path
