"""Dictation lifecycle, independent of the microphone and Cocoa UI."""
from dataclasses import dataclass, field
import threading
import time


@dataclass(frozen=True)
class Session:
    generation: int
    target: object
    language: str
    formatting_mode: str
    cancelled: threading.Event = field(default_factory=threading.Event)


@dataclass(frozen=True)
class Result:
    raw: str
    text: str
    target: object
    outcome: str
    formatting_reason: str = ''


class DictationController:
    def __init__(self, stt, formatter, output, on_status=lambda state, message: None):
        self.stt, self.formatter, self.output = stt, formatter, output
        self.on_status = on_status
        self._lock = threading.RLock()
        self._generation = 0
        self._session = None
        self._processing = False
        self._state = 'ready'
        self._last = None
        self._closed = False

    @property
    def state(self):
        with self._lock:
            return self._state

    @property
    def last_result(self):
        with self._lock:
            return self._last

    def _status(self, state, message):
        self._state = state
        self.on_status(state, message)

    def begin(self, target, language='en', formatting_mode='fast'):
        with self._lock:
            if self._closed or self._state != 'ready':
                return False
            self._generation += 1
            self._session = Session(self._generation, target, language, formatting_mode)
            self._status('recording', 'Listening… Esc to cancel')
            return True

    def cancel(self):
        with self._lock:
            if self._session is None:
                return False
            self._session.cancelled.set()
            self._generation += 1
            self._session = None
            self._last = None
            # Inference is not interruptible. Keep one worker and never deliver
            # its late result; do not accumulate model calls after repeated Esc.
            if self._processing:
                self._status('cancelling', 'Cancelled; finishing current work…')
            else:
                self._status('ready', 'Cancelled')
            return True

    def clear(self):
        with self._lock:
            self._last = None

    def close(self):
        with self._lock:
            self.cancel()
            self._closed = True
            self._last = None

    def process(self, audio, released_at=None):
        with self._lock:
            session = self._session
            if session is None or self._closed:
                return None
            if not len(audio):
                self._session = None
                self._status('ready', 'No audio captured')
                return None
            self._processing = True
            self._status('transcribing', 'Transcribing… Esc to cancel')

        timings = {}
        try:
            start = time.perf_counter()
            raw = self.stt.transcribe(audio, language=session.language)
            timings['stt_seconds'] = time.perf_counter() - start
            with self._lock:
                if session.generation != self._generation:
                    return None
                if not raw:
                    self._status('ready', 'No speech detected')
                    return None
                self._last = Result(raw, raw, session.target, 'available')
                self._status('formatting', 'Polishing… Esc to cancel' if session.formatting_mode == 'polished' else 'Formatting…')
            start = time.perf_counter()
            formatting_reason = ''
            if getattr(type(self.formatter), 'supports_format_requests', False) is True:
                formatted = self.formatter.format_session(
                    raw, language=session.language, mode=session.formatting_mode,
                    session_generation=session.generation, cancel=session.cancelled)
                text = formatted.text or raw
                if formatted.outcome == 'fallback':
                    formatting_reason = formatted.reason
                timings['ai_generation_seconds'] = formatted.generation_seconds
            else:
                text = self.formatter.format_text(raw, language=session.language, mode=session.formatting_mode) or raw
            timings['formatting_seconds'] = time.perf_counter() - start
            with self._lock:
                if session.generation != self._generation:
                    # Do not retain a cancelled transcript that completed late.
                    return None
                self._last = Result(raw, text, session.target, 'available', formatting_reason)
                self._status('delivering', 'Checking destination…')

            start = time.perf_counter()
            # The output tool invokes this guard immediately before dispatching
            # paste. Cancellation and dispatch have one linearization point.
            outcome = self.output.deliver(text, session.target,
                                          lambda send: self._dispatch(session, send))
            timings['injection_seconds'] = time.perf_counter() - start
            with self._lock:
                if session.generation != self._generation:
                    return None
                self._last = Result(raw, text, session.target, outcome, formatting_reason)
                if outcome == 'sent':
                    message = 'Paste sent'
                    if formatting_reason:
                        message += ' — Fast fallback (' + formatting_reason.replace('_', ' ') + ')'
                    self._status('ready', message)
                else:
                    self._status('ready', 'Text ready — Copy Last Dictation')
            if released_at is not None:
                timings['release_to_paste_sent_seconds' if outcome == 'sent' else 'release_to_result_seconds'] = time.perf_counter() - released_at
            return timings
        except Exception:
            with self._lock:
                if session.generation == self._generation:
                    self._status('ready', 'Could not finish — check last dictation')
            return None
        finally:
            with self._lock:
                self._processing = False
                self._session = None
                if self._state == 'cancelling':
                    self._status('ready', 'Cancelled')

    def _dispatch(self, session, send):
        with self._lock:
            if self._closed or session.generation != self._generation:
                return False
            send()
            return True
