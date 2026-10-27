"""Deterministic installer, worker and cancellation regressions; no models or GPU."""
import hashlib
import io
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest import mock

from tools.core_model_store import ModelStore, DownloadCancelled
from tools.core_mlx_llm import EmbeddedFormatter, MLXRuntime
from tools.core_session import DictationController
from tools.core_llm import preserves_dictation
from tools.core_memory import MemoryMonitor, GIB
from app import TalkyApp, StatusBarController
import AppKit


class DownloadDialogTests(unittest.TestCase):
    def setUp(self):
        self.app = object.__new__(TalkyApp)
        self.app._ai_download_prompt_open = False
        self.formatter = mock.Mock()
        self.formatter.state = 'not_installed'
        self.formatter.store.installed.return_value = False
        self.formatter.store.download_bytes = 984012537
        def enable(enabled):
            # Simulate the old backend overwriting a failure immediately.
            self.formatter.state = 'not_installed'
        def fail():
            self.formatter.state = 'failed'
        self.formatter.set_enabled.side_effect = enable
        self.formatter.install.side_effect = fail
        self.app._formatter = self.formatter
        status = object.__new__(StatusBarController)
        status._config = mock.Mock()
        status._update_formatting_checks = mock.Mock()
        status.on_formatting_change = self.app._formatting_changed
        self.app.status_bar = status
        self.alert = mock.Mock()
        self.alert.runModal.side_effect = [AppKit.NSAlertFirstButtonReturn,
                                         AssertionError('Download dialog opened recursively')]
        patcher = mock.patch('app.AppKit.NSAlert')
        alert_class = patcher.start()
        self.addCleanup(patcher.stop)
        alert_class.alloc.return_value.init.return_value = self.alert

    def test_immediate_failure_does_not_reopen_download_dialog(self):
        self.app._formatting_changed('polished')
        self.assertEqual(self.alert.runModal.call_count, 1)
        self.formatter.install.assert_called_once()
        self.assertEqual(self.formatter.state, 'failed')
        self.assertFalse(self.app._ai_download_prompt_open)

    def test_later_does_not_start_download(self):
        self.alert.runModal.side_effect = [AppKit.NSAlertSecondButtonReturn]
        self.app._install_ai()
        self.formatter.install.assert_not_called()
        self.assertFalse(self.app._ai_download_prompt_open)

    def test_pending_download_or_open_prompt_cannot_open_another_dialog(self):
        self.formatter.state = 'downloading'
        self.app._install_ai()
        self.formatter.state = 'not_installed'
        self.app._ai_download_prompt_open = True
        self.app._install_ai()
        self.alert.runModal.assert_not_called()


class ModelStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.payload = b'verified model'
        self.manifest = dict(repo_id='test/model', revision='fixed', files=[dict(
            name='model.safetensors', size=len(self.payload),
            sha256=hashlib.sha256(self.payload).hexdigest())])
        self.store = ModelStore(root=self.temp.name, manifest=self.manifest)

    def opener(self, url, timeout):
        self.assertIn('/resolve/fixed/', url)
        return io.BytesIO(self.payload)

    def test_verified_install_and_same_size_tampering(self):
        self.store.install(threading.Event(), opener=self.opener)
        self.assertTrue(self.store.verify())
        (self.store.path / 'model.safetensors').write_bytes(b'x' * len(self.payload))
        self.assertFalse(self.store.verify())
        self.store.install(threading.Event(), opener=self.opener)
        self.assertTrue(self.store.verify())

    def test_corrupt_download_is_never_activated(self):
        with self.assertRaises(ValueError):
            self.store.install(threading.Event(), opener=lambda *a, **kw: io.BytesIO(b'bad'))
        self.assertFalse(self.store.installed())
        self.assertFalse(self.store.path.exists())

    def test_cancel_during_download_then_retry(self):
        cancel = threading.Event()
        def progress(*args):
            cancel.set()
        with self.assertRaises(DownloadCancelled):
            self.store.install(cancel, progress, self.opener)
        self.assertFalse(self.store.installed())
        self.store.install(threading.Event(), opener=self.opener)
        self.assertTrue(self.store.verify())

    def test_git_blob_hash_and_manifest_path_restriction(self):
        entry = self.manifest['files'][0]
        entry['git_sha1'] = hashlib.sha1(
            b'blob ' + str(len(self.payload)).encode() + b'\0' + self.payload).hexdigest()
        del entry['sha256']
        self.store.install(threading.Event(), opener=self.opener)
        self.assertTrue(self.store.verify())
        entry['name'] = '../outside'
        with self.assertRaises(ValueError):
            ModelStore(root=self.temp.name, manifest=self.manifest)


class PolicyTests(unittest.TestCase):
    def test_memory_monitor_uses_recovery_hysteresis(self):
        probe = mock.Mock(side_effect=[GIB // 2, GIB + 1, 3 * GIB])
        changed = mock.Mock()
        monitor = MemoryMonitor(changed, probe)
        for _ in range(3):
            monitor.sample()
        self.assertEqual(changed.call_args_list, [mock.call(True), mock.call(False)])
    def test_chat_template_explicitly_disables_thinking(self):
        runtime = object.__new__(MLXRuntime)
        runtime.tokenizer = mock.Mock()
        runtime.prompt('Synthetic dictation.', 'de')
        kwargs = runtime.tokenizer.apply_chat_template.call_args.kwargs
        self.assertIs(kwargs['enable_thinking'], False)
        self.assertTrue(kwargs['tokenize'])

    def test_german_preposition_um_cannot_be_deleted(self):
        self.assertFalse(preserves_dictation('Wir treffen uns um drei', 'Wir treffen uns drei.', 'de'))
        self.assertTrue(preserves_dictation('ähm wir treffen uns um drei', 'Wir treffen uns um drei.', 'de'))

    def test_code_punctuation_and_flags_cannot_change(self):
        for raw, candidate in [('Open core_llm.py', 'Open core_llm py.'),
                               ('Run --dry-run', 'Run dry run.'),
                               ('Use x >= 3', 'Use x <= 3.'),
                               ('Open tools/main.py', 'Open tools main.py.')]:
            self.assertFalse(preserves_dictation(raw, candidate, 'en'))


class FakeStore:
    path = Path('/synthetic/local/model')
    manifest = {'revision': 'test-revision'}
    def installed(self):
        return True
    def verify(self, cancel):
        return not cancel.is_set()


class FakeRuntime:
    def __init__(self, path):
        self.owner = threading.get_ident()
        self.text, self.finish = 'Hello, world.', 'stop'
        self.action = lambda: None
        self.closed_streams = 0
        self.is_closed = False
        self.prompt_size = 10
        self.on_prompt = lambda: None
    def prompt(self, text, language):
        assert self.owner == threading.get_ident()
        self.on_prompt()
        return [1] * self.prompt_size
    def token_count(self, text):
        return len(text.split())
    def stream(self, prompt, max_tokens):
        try:
            self.action()
            yield SimpleNamespace(text=self.text, finish_reason=self.finish)
        finally:
            self.closed_streams += 1
    def synchronize(self):
        assert self.owner == threading.get_ident()
    def clear_cache(self):
        pass
    def close(self):
        assert self.owner == threading.get_ident()
        self.is_closed = True


class FormatterTests(unittest.TestCase):
    def setUp(self):
        self.factory = mock.Mock(side_effect=FakeRuntime)
        self.formatter = EmbeddedFormatter(FakeStore(), runtime_factory=self.factory,
                                            idle_seconds=0, memory_probe=lambda: 8 * GIB)
        self.addCleanup(self.cleanup)
    def cleanup(self):
        self.formatter.close()
        if self.formatter._executor:
            self.formatter._executor.shutdown(wait=True)
    def ready(self):
        self.formatter.set_enabled(True).result(timeout=2)
        self.assertEqual(self.formatter.state, 'ready')
        return self.formatter._runtime
    def format(self, **kw):
        return self.formatter.format_session('hello world', mode='polished', **kw)

    def test_fast_and_not_ready_never_load_a_model(self):
        self.assertEqual(self.formatter.format_text('um hello', mode='fast'), 'Hello')
        self.assertEqual(self.format().reason, 'not_ready')
        self.factory.assert_not_called()
        self.assertIsNone(self.formatter._executor)

    def test_verified_complete_result_and_worker_ownership(self):
        runtime = self.ready()
        result = self.format()
        self.assertEqual(result.text, 'Hello, world.')
        self.assertEqual(result.reason, 'accepted')
        self.assertEqual(result.model_revision, 'test-revision')
        self.assertNotEqual(runtime.owner, threading.get_ident())

    def test_truncated_output_is_never_used(self):
        self.ready().finish = 'length'
        result = self.format()
        self.assertEqual((result.text, result.reason), ('Hello world', 'length_limit'))

    def test_changed_numbers_roles_or_words_are_rejected(self):
        self.ready().text = 'Delete everything.'
        self.assertEqual(self.format().reason, 'validation')

    def test_cancel_during_inference_discards_candidate_and_closes_stream(self):
        runtime = self.ready()
        cancel = threading.Event()
        runtime.action = cancel.set
        result = self.format(cancel=cancel)
        self.assertEqual((result.text, result.outcome), ('', 'cancelled'))
        self.assertEqual(runtime.closed_streams, 2)  # warmup + request

    def test_deadline_before_generation_returns_fast(self):
        runtime = self.ready()
        runtime.action = lambda: self.fail('Must not generate after deadline')
        self.assertEqual(self.format(budget=-1).reason, 'deadline')

    def test_deadline_during_generation_does_not_paste_partial_output(self):
        runtime = self.ready()
        runtime.action = lambda: time.sleep(.02)
        result = self.format(budget=.005)
        self.assertEqual((result.text, result.reason), ('Hello world', 'deadline'))

    def test_cancel_while_gpu_cleanup_drains_still_discards_output(self):
        runtime = self.ready()
        cancel = threading.Event()
        runtime.synchronize = cancel.set
        result = self.format(cancel=cancel)
        self.assertEqual((result.text, result.reason), ('', 'cancelled'))

    def test_shutdown_during_generation_drains_then_unloads_on_worker(self):
        runtime = self.ready()
        entered, release = threading.Event(), threading.Event()
        def wait():
            entered.set()
            release.wait(2)
        runtime.action = wait
        results = []
        caller = threading.Thread(target=lambda: results.append(self.format()))
        caller.start()
        self.assertTrue(entered.wait(1))
        self.formatter.close()
        release.set()
        caller.join(2)
        self.formatter._executor.shutdown(wait=True)
        self.assertFalse(caller.is_alive())
        self.assertEqual(results[0].reason, 'cancelled')
        self.assertTrue(runtime.is_closed)

    def test_context_overflow_is_not_truncated(self):
        self.ready().prompt_size = 4096
        self.assertEqual(self.format().reason, 'length_limit')

    def test_generator_failure_uses_fast_and_next_request_can_succeed(self):
        runtime = self.ready()
        runtime.action = mock.Mock(side_effect=ValueError('Synthetic error'))
        self.assertEqual(self.format().reason, 'model_error')
        runtime.action = lambda: None
        self.assertEqual(self.format().reason, 'accepted')

    def test_disable_unloads_on_worker_and_fast_does_not_reload(self):
        runtime = self.ready()
        self.formatter.set_enabled(False).result(timeout=2)
        self.assertTrue(runtime.is_closed)
        self.formatter.format_text('hello', mode='fast')
        self.assertEqual(self.factory.call_count, 1)

    def test_rapid_mode_changes_do_not_run_a_stale_unload(self):
        runtime = self.ready()
        entered, release = threading.Event(), threading.Event()
        def wait():
            entered.set()
            release.wait(2)
        blocker = self.formatter._submit(wait)
        self.assertTrue(entered.wait(1))
        pending = self.formatter.set_enabled(False)
        self.formatter.set_enabled(True)
        release.set()
        blocker.result(timeout=2)
        pending.result(timeout=2)
        self.assertFalse(runtime.is_closed)
        self.assertEqual(self.formatter.state, 'ready')

    def test_idle_eviction_checks_last_use_and_reloads_asynchronously(self):
        self.ready()
        self.formatter.idle_seconds = 10
        self.formatter._submit(self.formatter._unload, True).result(timeout=2)
        self.assertEqual(self.formatter.state, 'ready')
        self.formatter._last_used = 0
        self.formatter._submit(self.formatter._unload, True).result(timeout=2)
        self.assertEqual(self.formatter.state, 'unloaded')
        self.assertEqual(self.format().reason, 'not_ready')
        self.formatter._load_future.result(timeout=2)
        self.assertEqual(self.formatter.state, 'ready')

    def test_failed_load_can_be_retried(self):
        self.factory.side_effect = RuntimeError('Synthetic load failure')
        self.formatter.set_enabled(True).result(timeout=2)
        self.assertEqual(self.formatter.state, 'failed')
        self.factory.side_effect = FakeRuntime
        self.ready()

    def test_failed_download_stays_visible_when_polished_is_selected(self):
        self.formatter.store.installed = lambda: False
        self.formatter.store.install = mock.Mock(side_effect=PermissionError('Synthetic failure'))
        self.formatter.install().result(timeout=2)
        message = self.formatter.message
        self.assertEqual(self.formatter.state, 'failed')
        self.formatter.set_enabled(True)
        self.assertEqual(self.formatter.state, 'failed')
        self.assertEqual(self.formatter.message, message)
        self.formatter.install().result(timeout=2)
        self.assertEqual(self.formatter.store.install.call_count, 2)

    def test_low_memory_unloads_and_recovers_without_overlapping_inference(self):
        runtime = self.ready()
        self.formatter._memory_changed(True)
        self.formatter._submit(lambda: None).result(timeout=2)
        self.assertTrue(runtime.is_closed)
        self.assertEqual(self.format().reason, 'not_ready')
        self.assertEqual(self.factory.call_count, 1)
        self.formatter._memory_changed(False)
        self.assertEqual(self.format().reason, 'not_ready')
        self.formatter._load_future.result(timeout=2)
        self.assertEqual(self.formatter.state, 'ready')

    def test_controller_propagates_cancellation_token_and_fallback_reason(self):
        stt = mock.Mock()
        stt.transcribe.return_value = 'hello world'
        output = mock.Mock()
        output.deliver.side_effect = lambda text, target, dispatch: 'sent' if dispatch(lambda: None) else 'available'
        controller = DictationController(stt, self.formatter, output)
        controller.begin('target', formatting_mode='polished')
        controller.process([1])
        self.assertEqual(controller.last_result.formatting_reason, 'not_ready')
        self.assertEqual(controller.last_result.text, 'Hello world')
        runtime = self.ready()
        runtime.action = controller.cancel
        controller.begin('target', formatting_mode='polished')
        self.assertIsNone(controller.process([1]))
        self.assertIsNone(controller.last_result)
        self.assertEqual(output.deliver.call_count, 1)


if __name__ == '__main__':
    unittest.main()
