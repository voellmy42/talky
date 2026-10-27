"""Mac integration seams tested without accessing the real clipboard or mic."""
import threading
import queue
import Quartz
import unittest
from unittest import mock

import numpy as np

from tools.core_audio import AudioCaptureTool, AudioRingBuffer
from tools.core_focus import Destination, FocusTracker
from tools.core_output import OutputInjector
from app import TalkyApp


class FakeOutput(OutputInjector):
    def __init__(self, tracker):
        super().__init__(focus_tracker=tracker)
        self.clipboard = 'original'
        self.count = 0
        self.sent = []
        self._schedule_restore = mock.Mock()

    def _snapshot_clipboard(self):
        return self.clipboard

    def _set_clipboard_text(self, text):
        self.clipboard = text
        self.count += 1
        return self.count

    def _clipboard_was_replaced(self, expected):
        return expected is not None and expected != self.count

    def _restore_clipboard(self, value):
        self.clipboard = value

    def _send_paste_shortcut(self):
        self.sent.append(self.clipboard)


class DeliveryTests(unittest.TestCase):
    def make_output(self, matches):
        tracker = mock.Mock()
        tracker.matches.side_effect = matches
        return FakeOutput(tracker)

    def test_unknown_destination_does_not_touch_clipboard(self):
        out = self.make_output([False])
        self.assertEqual(out.deliver('dictation', None, lambda send: send() or True), 'available')
        self.assertEqual(out.clipboard, 'original')
        self.assertEqual(out.sent, [])

    def test_focus_changes_after_clipboard_preparation(self):
        out = self.make_output([True, False])
        self.assertEqual(out.deliver('dictation', 'field', lambda send: send() or True), 'available')
        self.assertEqual(out.sent, [])
        self.assertEqual(out.clipboard, 'original')

    def test_cancellation_before_dispatch_restores_clipboard(self):
        out = self.make_output([True])
        self.assertEqual(out.deliver('dictation', 'field', lambda send: False), 'available')
        self.assertEqual(out.sent, [])
        self.assertEqual(out.clipboard, 'original')

    def test_intervening_copy_is_neither_pasted_nor_overwritten(self):
        out = self.make_output([True, True])
        def dispatch(send):
            out._set_clipboard_text('new user copy')
            send()
            return True
        self.assertEqual(out.deliver('dictation', 'field', dispatch), 'available')
        self.assertEqual(out.sent, [])
        self.assertEqual(out.clipboard, 'new user copy')

    def test_success_sends_exact_multiline_unicode_without_typing(self):
        out = self.make_output([True, True])
        text = 'Bitte nöd ändere.\nPort 8080 → prüfen.'
        self.assertEqual(out.deliver(text, 'field', lambda send: send() or True), 'sent')
        self.assertEqual(out.sent, [text])
        out._schedule_restore.assert_called_once()

    def test_explicit_copy_invalidates_pending_restore(self):
        out = self.make_output([True, True])
        out.deliver('dictation', 'field', lambda send: send() or True)
        generation = out._clipboard_generation
        out.copy('copy last')
        out._restore_after_failure(generation)
        self.assertEqual(out.clipboard, 'copy last')


class FocusTests(unittest.TestCase):
    def test_requires_same_application_window_field_and_caret(self):
        tracker = FocusTracker()
        target = Destination(10, 'window', 'field', 'selection')
        for current in (None, Destination(11, 'window', 'field', 'selection'),
                        Destination(10, 'other', 'field', 'selection'),
                        Destination(10, 'window', 'other', 'selection'),
                        Destination(10, 'window', 'field', 'moved'),
                        Destination(10, 'window', 'field', None)):
            with self.subTest(current=current), mock.patch.object(tracker, 'capture', return_value=current), mock.patch('tools.core_focus.CFEqual', side_effect=lambda a, b: a == b):
                self.assertFalse(tracker.matches(target))
        with mock.patch.object(tracker, 'capture', return_value=target), mock.patch('tools.core_focus.CFEqual', side_effect=lambda a, b: a == b):
            self.assertTrue(tracker.matches(target))


class OverlayNoticeTests(unittest.TestCase):
    def test_temporary_feedback_restores_active_recording_indicator(self):
        talky = TalkyApp.__new__(TalkyApp)
        talky.overlay = mock.Mock()
        talky._session_state = 'recording'
        talky._session_message = 'Listening… Esc to cancel'
        talky._restore_session_overlay()
        talky.overlay.show.assert_called_once_with('Listening… Esc to cancel')
        talky.overlay.hide.assert_not_called()

    def test_temporary_feedback_can_hide_when_ready(self):
        talky = TalkyApp.__new__(TalkyApp)
        talky.overlay = mock.Mock()
        talky._session_state = 'ready'
        talky._restore_session_overlay()
        talky.overlay.hide.assert_called_once()


class AudioControlTests(unittest.TestCase):
    def make_audio(self):
        # Initialize control state only: never instantiate an audio engine.
        audio = AudioCaptureTool.__new__(AudioCaptureTool)
        audio._control_lock = threading.RLock()
        audio._audio_lock = threading.Lock()
        audio._closed = False
        audio._tap_ready = threading.Event()
        audio.meeting_active = False
        audio._dictation_session_active = True
        audio._mode = 'IDLE'
        audio._start_event = threading.Event()
        audio._stop_event = threading.Event()
        audio._last_press = audio._last_release = 0
        audio._double_tap_threshold = .4
        audio.is_recording = False
        audio._cancelled = False
        audio._controls = queue.Queue()
        audio.engine = mock.Mock()
        audio.input_node = None
        audio.on_capture_request = mock.Mock(return_value=True)
        audio.on_cancel = mock.Mock(return_value=True)
        audio.on_busy = mock.Mock()
        audio.get_toggle_shortcut = lambda: 'section'
        audio._ensure_audio_running = mock.Mock(return_value=True)
        audio._clear_audio_queue = mock.Mock()
        audio._ring_buffer = AudioRingBuffer(8)
        audio.q = mock.Mock()
        return audio

    def test_busy_keypress_does_not_open_capture(self):
        audio = self.make_audio()
        audio._dictation_session_active = False
        audio._handle_press(10)
        audio.on_busy.assert_called_once()
        audio.on_capture_request.assert_not_called()

    def test_rejected_session_does_not_start_microphone(self):
        audio = self.make_audio()
        audio.on_capture_request.return_value = False
        audio._handle_press(10)
        audio._ensure_audio_running.assert_not_called()
        self.assertFalse(audio._start_event.is_set())

    def test_release_stops_capture_and_records_release_time(self):
        audio = self.make_audio()
        audio._handle_press(10)
        audio._handle_release(11)
        self.assertTrue(audio._stop_event.is_set())
        self.assertFalse(audio.is_recording)
        self.assertGreater(audio.released_at, 0)

    def test_cancel_stops_recording_and_unblocks_waiter(self):
        audio = self.make_audio()
        audio._handle_press(10)
        audio.cancel()
        self.assertTrue(audio._cancelled)
        self.assertTrue(audio._stop_event.is_set())
        self.assertFalse(audio.is_recording)

    def test_cancel_while_processing_still_reaches_controller(self):
        audio = self.make_audio()
        audio._dictation_session_active = False
        audio.cancel()
        audio.on_cancel.assert_called_once()

    def test_stop_releases_microphone_and_input_tap(self):
        audio = self.make_audio()
        node = audio.input_node = mock.Mock()
        audio._engine_running = True
        audio.is_recording = True
        audio._stop_capture()
        audio.engine.stop.assert_called_once()
        node.removeTapOnBus_.assert_called_once_with(0)
        self.assertIsNone(audio.input_node)
        self.assertFalse(audio._engine_running)

    def test_toggle_starts_and_finishes(self):
        audio = self.make_audio()
        audio._toggle_capture(10)
        self.assertTrue(audio.is_recording)
        self.assertEqual(audio._mode, 'TOGGLED_IDLE')
        self.assertTrue(audio._start_event.is_set())
        audio._toggle_capture(11)
        self.assertFalse(audio.is_recording)
        self.assertTrue(audio._stop_event.is_set())

    def test_constructor_never_opens_input_hardware(self):
        with mock.patch.object(AudioCaptureTool, '_run_event_tap', lambda audio: audio._tap_ready.set()), \
                mock.patch('tools.core_audio.AVFoundation.AVAudioEngine') as factory, \
                mock.patch('Foundation.NSNotificationCenter'):
            engine = factory.alloc.return_value.init.return_value
            audio = AudioCaptureTool()
            try:
                engine.inputNode.assert_not_called()
                engine.prepare.assert_not_called()
                engine.startAndReturnError_.assert_not_called()
                self.assertFalse(audio._engine_running)
            finally:
                audio.close()

    def test_event_callback_only_queues_controls_and_uses_accessibility_tap(self):
        audio = self.make_audio()
        audio.hotkey = 'fn'
        audio._handle_press = mock.Mock(side_effect=AssertionError('Work inside event callback'))
        replacements = dict(
            CGEventTapCreate=mock.Mock(return_value=object()),
            CFMachPortCreateRunLoopSource=mock.Mock(return_value=object()),
            CFRunLoopGetCurrent=mock.Mock(return_value=object()),
            CFRunLoopAddSource=mock.Mock(), CGEventTapEnable=mock.Mock(),
            CFRunLoopRun=mock.Mock(),
            CGEventGetFlags=mock.Mock(side_effect=lambda event: event.get('flags', 0)),
            CGEventKeyboardGetUnicodeString=mock.Mock(side_effect=lambda event, *args: (len(event.get('text', '')), event.get('text', ''))),
            CGEventGetIntegerValueField=mock.Mock(side_effect=lambda event, field: (
                event.get('repeat', 0) if field == Quartz.kCGKeyboardEventAutorepeat else event['code'])),
        )
        with mock.patch.multiple(Quartz, **replacements):
            audio._run_event_tap()
            args = replacements['CGEventTapCreate'].call_args.args
            self.assertEqual(args[2], Quartz.kCGEventTapOptionDefault)
            callback = args[4]
            down = {'flags': Quartz.kCGEventFlagMaskSecondaryFn}
            up = {'flags': 0}
            self.assertIs(callback(None, Quartz.kCGEventFlagsChanged, down, None), down)
            callback(None, Quartz.kCGEventFlagsChanged, down, None)  # duplicate
            callback(None, Quartz.kCGEventFlagsChanged, up, None)
            f8 = {'code': 100}
            self.assertIs(callback(None, Quartz.kCGEventKeyDown, f8, None), f8)
            section = {'code': 10, 'text': '§'}
            self.assertIsNone(callback(None, Quartz.kCGEventKeyDown, section, None))
            self.assertIsNone(callback(None, Quartz.kCGEventKeyDown, {'code': 10, 'text': '§', 'repeat': 1}, None))
            self.assertIsNone(callback(None, Quartz.kCGEventKeyUp, {'code': 10}, None))
            callback(None, Quartz.kCGEventKeyDown, {'code': 53}, None)
            callback(None, Quartz.kCGEventKeyDown, {'code': 42}, None)  # unrelated
        self.assertEqual([audio._controls.get_nowait()[0] for _ in range(audio._controls.qsize())],
                         ['press', 'release', 'toggle', 'cancel'])
        audio._handle_press.assert_not_called()

    def test_shortcut_matches_character_preserves_other_keys_and_changes_live(self):
        audio = self.make_audio()
        audio.hotkey = 'fn'
        shortcut = ['section']
        audio.get_toggle_shortcut = lambda: shortcut[0]
        replacements = dict(
            CGEventTapCreate=mock.Mock(return_value=object()),
            CFMachPortCreateRunLoopSource=mock.Mock(return_value=object()),
            CFRunLoopGetCurrent=mock.Mock(return_value=object()),
            CFRunLoopAddSource=mock.Mock(), CGEventTapEnable=mock.Mock(), CFRunLoopRun=mock.Mock(),
            CGEventGetFlags=mock.Mock(side_effect=lambda event: event.get('flags', 0)),
            CGEventKeyboardGetUnicodeString=mock.Mock(side_effect=lambda event, *args: (len(event.get('text', '')), event.get('text', ''))),
            CGEventGetIntegerValueField=mock.Mock(side_effect=lambda event, field: (
                event.get('repeat', 0) if field == Quartz.kCGKeyboardEventAutorepeat else event['code'])),
        )
        with mock.patch.multiple(Quartz, **replacements):
            audio._run_event_tap()
            callback = replacements['CGEventTapCreate'].call_args.args[4]
            # The same physical key with another layout's character is ordinary typing.
            ordinary = {'code': 10, 'text': '`'}
            self.assertIs(callback(None, Quartz.kCGEventKeyDown, ordinary, None), ordinary)
            for flag in (Quartz.kCGEventFlagMaskCommand, Quartz.kCGEventFlagMaskControl, Quartz.kCGEventFlagMaskAlternate):
                modified = {'code': 10, 'text': '§', 'flags': flag}
                self.assertIs(callback(None, Quartz.kCGEventKeyDown, modified, None), modified)
            # Character matching also works if § is on a different physical key.
            self.assertIsNone(callback(None, Quartz.kCGEventKeyDown, {'code': 50, 'text': '§'}, None))
            shortcut[0] = 'off'
            self.assertIsNone(callback(None, Quartz.kCGEventKeyUp, {'code': 50}, None))
            section = {'code': 50, 'text': '§'}
            self.assertIs(callback(None, Quartz.kCGEventKeyDown, section, None), section)
            shortcut[0] = 'ctrl_shift_space'
            combo = {'code': 49, 'flags': Quartz.kCGEventFlagMaskControl | Quartz.kCGEventFlagMaskShift}
            self.assertIsNone(callback(None, Quartz.kCGEventKeyDown, combo, None))
            self.assertIsNone(callback(None, Quartz.kCGEventKeyUp, {'code': 49}, None))
        self.assertEqual([audio._controls.get_nowait()[0] for _ in range(audio._controls.qsize())],
                         ['toggle', 'toggle'])


if __name__ == '__main__':
    unittest.main()
