"""Deterministic lifecycle tests; no model, microphone or real paste required."""
import threading
import unittest
from unittest import mock

from tools.core_session import DictationController
from tools.core_llm import LLMFormatter, preserves_dictation


class ControllerTests(unittest.TestCase):
    def make_controller(self):
        self.stt = mock.Mock()
        self.stt.transcribe.return_value = 'Do not deploy version 1.2.'
        self.formatter = mock.Mock()
        self.formatter.format_text.side_effect = lambda raw, **kw: raw
        self.output = mock.Mock()
        self.sent = []
        self.output.deliver.side_effect = lambda text, target, dispatch: (
            'sent' if dispatch(lambda: self.sent.append((text, target))) else 'available')
        self.statuses = []
        self.controller = DictationController(self.stt, self.formatter, self.output,
                                              lambda state, message: self.statuses.append(state))
        return self.controller

    def test_settings_and_destination_are_snapshotted_at_start(self):
        c = self.make_controller()
        self.assertTrue(c.begin('original field', 'de', 'fast'))
        self.assertFalse(c.begin('another field', 'en', 'polished'))
        timings = c.process([1, 2, 3], released_at=0)
        self.stt.transcribe.assert_called_once_with([1, 2, 3], language='de')
        self.formatter.format_text.assert_called_once_with(
            'Do not deploy version 1.2.', language='de', mode='fast')
        self.assertEqual(self.sent, [('Do not deploy version 1.2.', 'original field')])
        self.assertIn('release_to_paste_sent_seconds', timings)
        self.assertEqual(c.state, 'ready')

    def test_focus_failure_retains_raw_and_final_for_copy(self):
        c = self.make_controller()
        self.output.deliver.return_value = 'available'
        self.output.deliver.side_effect = None
        c.begin(None)
        timings = c.process([1])
        self.assertEqual(c.last_result.outcome, 'available')
        self.assertEqual(c.last_result.raw, 'Do not deploy version 1.2.')
        self.assertNotIn('release_to_paste_sent_seconds', timings)
        self.assertEqual(self.sent, [])

    def test_cancel_recording_discards_capture(self):
        c = self.make_controller()
        c.begin('field')
        self.assertTrue(c.cancel())
        self.assertIsNone(c.process([1]))
        self.stt.transcribe.assert_not_called()
        self.assertIsNone(c.last_result)
        self.assertEqual(c.state, 'ready')

    def check_cancel_during(self, stage):
        c = self.make_controller()
        entered, release = threading.Event(), threading.Event()
        def wait(*args, **kw):
            entered.set()
            if not release.wait(2):
                raise RuntimeError('Test timed out')
            return 'Late result'
        if stage == 'stt':
            self.stt.transcribe.side_effect = wait
        else:
            self.formatter.format_text.side_effect = wait
        c.begin('field')
        worker = threading.Thread(target=c.process, args=([1],))
        worker.start()
        try:
            self.assertTrue(entered.wait(2))
            self.assertTrue(c.cancel())
            self.assertEqual(c.state, 'cancelling')
            self.assertFalse(c.begin('new field'))
        finally:
            release.set()
            worker.join(2)
        self.assertFalse(worker.is_alive())
        self.output.deliver.assert_not_called()
        self.assertIsNone(c.last_result)
        self.assertEqual(c.state, 'ready')
        self.assertTrue(c.begin('new field'))

    def test_cancel_during_recognition_blocks_late_result(self):
        self.check_cancel_during('stt')

    def test_cancel_during_polishing_blocks_late_result(self):
        self.check_cancel_during('formatter')

    def test_cancel_immediately_before_paste_blocks_dispatch(self):
        c = self.make_controller()
        def deliver(text, target, dispatch):
            c.cancel()
            self.assertFalse(dispatch(lambda: self.sent.append(text)))
            return 'available'
        self.output.deliver.side_effect = deliver
        c.begin('field')
        self.assertIsNone(c.process([1]))
        self.assertEqual(self.sent, [])

    def test_formatter_failure_keeps_original_recoverable(self):
        c = self.make_controller()
        self.formatter.format_text.side_effect = RuntimeError('Unavailable')
        c.begin('field')
        c.process([1])
        self.assertEqual(c.last_result.text, 'Do not deploy version 1.2.')
        self.assertEqual(c.state, 'ready')
        self.assertTrue(c.begin('new field'))

    def test_model_error_returns_to_ready_without_paste(self):
        c = self.make_controller()
        self.stt.transcribe.side_effect = RuntimeError('Model failed')
        c.begin('field')
        c.process([1])
        self.output.deliver.assert_not_called()
        self.assertEqual(c.state, 'ready')

    def test_silence_and_empty_audio_do_not_deliver(self):
        c = self.make_controller()
        c.begin('field')
        c.process([])
        self.stt.transcribe.assert_not_called()
        self.stt.transcribe.return_value = ''
        c.begin('field')
        c.process([1])
        self.output.deliver.assert_not_called()

    def test_clear_and_shutdown_remove_recovery_text(self):
        c = self.make_controller()
        c.begin('field')
        c.process([1])
        c.clear()
        self.assertIsNone(c.last_result)
        c.close()
        self.assertFalse(c.begin('field'))


class CleanupPolicyTests(unittest.TestCase):
    def test_rejects_role_reversal_negation_moves_and_changed_numbers(self):
        for raw, candidate in (
            ('Alice owes Bob 20 euros.', 'Bob owes Alice 20 euros.'),
            ('I do not want coffee. I want tea.', 'I want coffee. I do not want tea.'),
            ('Use port 8080.', 'Use port 80.'),
            ('Bitte nicht ändern.', 'Bitte ändern.'),
            ('Ich chume nöd am Mäntig.', 'Ich chume am Mäntig.'),
            ('What is the capital of France?', 'The capital of France is Paris.'),
            ('Run myFunction with APIKey.', 'Run myfunction with Apikey.'),
        ):
            with self.subTest(raw=raw):
                self.assertFalse(preserves_dictation(raw, candidate))

    def test_accepts_restricted_cleanup(self):
        self.assertTrue(preserves_dictation('um do not deploy v1.2', 'Do not deploy v1.2.'))
        self.assertTrue(preserves_dictation('ähm ich chume nöd am Mäntig', 'Ich chume nöd am Mäntig.'))
        self.assertTrue(preserves_dictation('What now?', 'What now?'))

    def test_real_formatter_path_falls_back_on_unsafe_nonempty_output(self):
        response = mock.Mock()
        response.json.return_value = {'response': 'Deploy version 1.2.'}
        with mock.patch('tools.core_llm.requests.post', return_value=response):
            self.assertEqual(LLMFormatter().format_text('Do not deploy version 1.2.', mode='polished'),
                             'Do not deploy version 1.2.')


if __name__ == '__main__':
    unittest.main()
