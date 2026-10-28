"""Meter lifecycle and bounded visual math; no native windows or microphone."""
import queue
import threading
import unittest
from unittest import mock

import numpy as np

from tools.core_audio import AudioCaptureTool, AudioRingBuffer
from tools.ui_overlay import presentation, wave_heights


class AudioMeterTests(unittest.TestCase):
    def make_audio(self):
        audio = AudioCaptureTool.__new__(AudioCaptureTool)
        audio.is_recording = False
        audio.input_level = 0.0
        audio._audio_lock = threading.Lock()
        audio._ring_buffer = AudioRingBuffer(0)
        audio.q = queue.Queue()
        audio.engine = mock.Mock()
        audio.input_node = None
        return audio

    def test_inactive_audio_does_not_animate_or_queue(self):
        audio = self.make_audio()
        audio._route_audio_chunk(np.ones(256))
        self.assertEqual(audio.input_level, 0)
        self.assertTrue(audio.q.empty())

    def test_active_level_is_bounded_and_reset_on_stop(self):
        audio = self.make_audio()
        audio.is_recording = True
        for amplitude, expected in ((0, 0), (.063, .5), (10, 1), (float('nan'), 0)):
            audio._route_audio_chunk(np.full(256, amplitude))
            self.assertAlmostEqual(audio.input_level, expected, places=4)
        audio._stop_capture()
        self.assertEqual(audio.input_level, 0)
        self.assertFalse(audio.is_recording)


class VisualContractTests(unittest.TestCase):
    def test_waveform_stays_in_its_lane_and_silence_is_flat(self):
        for phase in np.linspace(0, 20, 100):
            for level in (-1, 0, .2, 1, 4):
                for processing in (False, True):
                    bars = wave_heights(level, phase, processing)
                    self.assertEqual(len(bars), 11)
                    self.assertTrue(all(3 <= value <= 25 for value in bars))
            self.assertEqual(wave_heights(0, phase), [3] * 11)

    def test_editing_and_recovery_are_distinct_from_success(self):
        self.assertEqual(presentation('Editing selection · DE — Esc to cancel')[2:4], ('DE', 'editing'))
        self.assertEqual(presentation('Text ready — Copy Last Result')[3], 'notice')
        self.assertEqual(presentation('Speech engine unavailable; restart Talky')[3], 'notice')


if __name__ == '__main__':
    unittest.main()
