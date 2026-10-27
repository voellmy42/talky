import json
import os
import tempfile
import time
import unittest
from unittest import mock

import numpy as np

from tools.core_audio import AudioRingBuffer
from tools.core_config import ConfigManager
from tools.core_llm import LLMFormatter
from tools.core_output import OutputInjector
from tools.core_stats import StatsStore


class ConfigManagerTests(unittest.TestCase):
    def test_preferences_are_persisted_and_validated(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp_dir:
            path = os.path.join(temp_dir, "config.json")
            config = ConfigManager(path)
            self.assertEqual(config.get_language(), "en")
            self.assertEqual(config.get_formatting_mode(), "fast")
            self.assertEqual(config.get_toggle_shortcut(), 'section')

            config.set_language("de")
            config.set_formatting_mode("polished")
            config.set_toggle_shortcut('ctrl_shift_space')

            reloaded = ConfigManager(path)
            self.assertEqual(reloaded.get_language(), "de")
            self.assertEqual(reloaded.get_formatting_mode(), "polished")
            self.assertEqual(reloaded.get_toggle_shortcut(), 'ctrl_shift_space')
            self.assertFalse(os.path.exists(f"{path}.tmp"))

            with self.assertRaises(ValueError):
                config.set_formatting_mode("slow")
            with self.assertRaises(ValueError):
                config.set_toggle_shortcut('media_f8')


class FastFormatterTests(unittest.TestCase):
    def test_fast_mode_is_local_and_conservative(self):
        formatter = LLMFormatter(request_timeout=0.1)
        with mock.patch("tools.core_llm.requests.post") as post:
            cleaned = formatter.format_text(
                "  um, hello  , world.  ", language="en", mode="fast"
            )

        self.assertEqual(cleaned, "Hello, world.")
        post.assert_not_called()

    def test_fast_mode_handles_german_hesitation(self):
        cleaned = LLMFormatter.fast_cleanup("ähm, das ist gut.", language="de")
        self.assertEqual(cleaned, "Das ist gut.")

    def test_polished_mode_preserves_gemma_prediction_budget(self):
        response = mock.Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"response": "Hello, world."}
        formatter = LLMFormatter(model="gemma4:latest", request_timeout=1.0)

        with mock.patch("tools.core_llm.requests.post", return_value=response) as post:
            result = formatter.format_text(
                "hello world", language="en", mode="polished"
            )

        self.assertEqual(result, "Hello, world.")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["options"]["num_predict"], 2048)
        self.assertEqual(post.call_args.kwargs["timeout"], 1.0)


class AudioRingBufferTests(unittest.TestCase):
    def test_ring_buffer_keeps_exact_latest_samples(self):
        ring = AudioRingBuffer(max_samples=8)
        ring.append(np.arange(5, dtype=np.float32))
        ring.append(np.arange(5, 11, dtype=np.float32))

        np.testing.assert_array_equal(
            ring.snapshot(), np.arange(3, 11, dtype=np.float32)
        )


class StatsStoreTests(unittest.TestCase):
    def test_latency_is_added_to_existing_stats_files(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp_dir:
            path = os.path.join(temp_dir, "stats.json")
            with open(path, "w") as stats_file:
                json.dump({"total_dictations": 1, "total_words": 5}, stats_file)

            stats = StatsStore(path)
            stats.add_dictation(2.0, 10, processing_seconds=0.75)
            formatted = stats.get_formatted_stats()

            self.assertEqual(formatted["dictations"], "2")
            self.assertEqual(formatted["last_latency"], "0.75s")
            self.assertEqual(formatted["average_latency"], "0.38s")


class _FakeOutputInjector(OutputInjector):
    def __init__(self, clipboard_replaced=False):
        super().__init__(restore_delay=0.01)
        self.clipboard = "original"
        self.restored = []
        self.shortcut_sent = False
        self.clipboard_replaced = clipboard_replaced

    def _snapshot_clipboard(self):
        return self.clipboard

    def _set_clipboard_text(self, text):
        self.clipboard = text
        return 1

    def _restore_clipboard(self, snapshot):
        self.restored.append(snapshot)
        self.clipboard = snapshot

    def _clipboard_was_replaced(self, expected_change_count):
        return self.clipboard_replaced and self.shortcut_sent

    def _send_paste_shortcut(self):
        self.shortcut_sent = True


class OutputInjectorTests(unittest.TestCase):
    def test_injection_restores_original_clipboard(self):
        injector = _FakeOutputInjector()
        self.assertTrue(injector.inject("dictated text"))
        time.sleep(0.04)

        self.assertTrue(injector.shortcut_sent)
        self.assertEqual(injector.restored, ["original"])
        self.assertEqual(injector.clipboard, "original")

    def test_new_user_clipboard_content_is_not_overwritten(self):
        injector = _FakeOutputInjector(clipboard_replaced=True)
        self.assertTrue(injector.inject("dictated text"))
        time.sleep(0.04)

        self.assertEqual(injector.restored, [])


if __name__ == "__main__":
    unittest.main()
