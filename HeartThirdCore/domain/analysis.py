"""Decode on a worker thread and publish bounded, synchronized raw and filtered history."""
import math
from collections import deque
from threading import Lock, Thread

from domain.protocol import FrameParser


class EcgFilter:
    """Streaming display filter at 500 SPS; preserve state across frame boundaries."""

    def __init__(self, morphology=False):
        self.sections = []
        # A single-pole 0.05 Hz high-pass reduces low-frequency phase distortion.
        if morphology:
            k = math.tan(math.pi * 0.05 / 500)
            self.sections.append(([1 / (1 + k), -1 / (1 + k), 0],
                                  (k - 1) / (1 + k), 0, [0.0, 0.0]))
        high = [] if morphology else [('high', 0.5, math.sqrt(0.5))]
        for kind, frequency, quality in high + [
                                          ('notch', 50, 8),
                                          ('notch', 50, 8),
                                          ('notch', 100, 8),
                                          ('notch', 100, 8),
                                          ('notch', 150, 8),
                                          ('low', 40, 0.541196100146197),
                                          ('low', 40, 1.306562964876377)]:
            omega = 2 * math.pi * frequency / 500
            cosine = math.cos(omega)
            alpha = math.sin(omega) / (2 * quality)
            if kind == 'high':
                b = ((1 + cosine) / 2, -(1 + cosine), (1 + cosine) / 2)
            elif kind == 'low':
                b = ((1 - cosine) / 2, 1 - cosine, (1 - cosine) / 2)
            else:
                b = (1, -2 * cosine, 1)
            scale = 1 + alpha
            self.sections.append(([value / scale for value in b],
                                  -2 * cosine / scale, (1 - alpha) / scale, [0.0, 0.0]))
        self.baseline = None

    def process(self, value):
        # Remove the initial ADC offset to avoid a large connection transient.
        if self.baseline is None:
            self.baseline = value
        value -= self.baseline
        for b, a1, a2, state in self.sections:
            output = b[0] * value + state[0]
            state[0] = b[1] * value - a1 * output + state[1]
            state[1] = b[2] * value - a2 * output
            value = output
        return value


class SampleStore:
    def __init__(self, capacity=2500, channel=1):
        if channel not in (0, 1):
            raise ValueError('ECG channel must be 0 or 1')
        self._lock = Lock()
        self._samples = deque(maxlen=capacity)
        self._filtered = [deque(maxlen=capacity), deque(maxlen=capacity)]
        self._filters = [EcgFilter(), EcgFilter(morphology=True)]
        self._mode = 0
        self._channel = channel
        self._sequence = None
        self._stats = dict(frames=0, missing=0, crc=0, duplicates=0)
        self._revision = 0

    @property
    def channel(self):
        with self._lock:
            return self._channel

    def _reset_filters(self):
        self._filters = [EcgFilter(), EcgFilter(morphology=True)]
        for history in self._filtered:
            history.clear()

    def _filter_samples(self, samples):
        for filter_, history in zip(self._filters, self._filtered):
            history.extend(filter_.process(pair[self._channel]) for pair in samples)

    def set_mode(self, mode):
        """Both modes run continuously, so switching does not restart settling."""
        if mode not in (0, 1):
            raise ValueError('ECG mode must be 0 or 1')
        with self._lock:
            self._mode = mode
            self._revision += 1

    def set_channel(self, channel):
        """Rebuild the selected channel from bounded raw history under the same lock."""
        if channel not in (0, 1):
            raise ValueError('ECG channel must be 0 or 1')
        with self._lock:
            if channel == self._channel:
                return
            self._channel = channel
            self._reset_filters()
            self._filter_samples(self._samples)
            self._revision += 1

    def publish(self, parser, frames, reset=False):
        with self._lock:
            if reset:
                self._samples.clear()
                self._reset_filters()
                self._sequence = None
            for sequence, samples in frames:
                if self._sequence is not None:
                    delta = (sequence - self._sequence) & 0xFF
                    if delta == 0:
                        continue
                    if delta != 1:
                        # A gap is not a contiguous 500 SPS stream; start a new trace.
                        self._samples.clear()
                        self._reset_filters()
                self._sequence = sequence
                self._samples.extend(samples)
                self._filter_samples(samples)
            self._stats = dict(frames=parser.frames, missing=parser.missing_frames,
                               crc=parser.crc_errors, duplicates=parser.sequence_errors)
            self._revision += 1

    def snapshot(self, previous_revision=None, include_filtered=False):
        with self._lock:
            if previous_revision == self._revision:
                return None
            snapshot = self._revision, list(self._samples), self._stats.copy()
            return snapshot + (list(self._filtered[self._mode]),) if include_filtered else snapshot


class AnalysisThread(Thread):
    def __init__(self, ring, store, stop):
        super().__init__(name="analysis")
        self.ring, self.store, self.stop = ring, store, stop

    def run(self):
        session = None
        parser = FrameParser()
        while not self.stop.is_set():
            current, data = self.ring.read()
            reset = current != session
            if reset:
                session, parser = current, FrameParser()
            if data or reset:
                self.store.publish(parser, parser.feed(data), reset)
