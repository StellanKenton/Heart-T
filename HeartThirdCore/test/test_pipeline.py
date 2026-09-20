"""Exercise bounded buffering, worker lifecycle and serial reconnection."""
import math
import sys
import time
import unittest
from pathlib import Path
from threading import Event, Thread
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from domain.analysis import AnalysisThread, EcgFilter, SampleStore
from domain.communication import CommunicationThread
from domain.ringbuffer import RingBuffer
from test_receiver import frame


def wait_for(predicate, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return False


class EcgFilterTests(unittest.TestCase):
    def test_vendor_board_defaults_to_ecg_channel_two(self):
        from domain.protocol import FrameParser
        parser, store = FrameParser(), SampleStore()
        pairs = [(100, n * 100) for n in range(5)]
        store.publish(parser, parser.feed(frame(0, pairs)))
        reference = EcgFilter()
        self.assertEqual(store.channel, 1)
        self.assertEqual(store.snapshot(include_filtered=True)[3],
                         [reference.process(pair[1]) for pair in pairs])

    def test_gap_resets_and_duplicate_does_not_repeat_samples(self):
        from domain.protocol import FrameParser
        parser, store = FrameParser(), SampleStore(channel=0)
        packets = frame(255, [(100, 0)] * 5) + frame(0, [(200, 0)] * 5)
        store.publish(parser, parser.feed(packets))
        self.assertEqual(len(store.snapshot()[1]), 10)
        store.publish(parser, parser.feed(frame(0, [(200, 0)] * 5)))
        self.assertEqual(len(store.snapshot()[1]), 10)
        store.publish(parser, parser.feed(frame(2, [(900000, 0)] * 5)))
        self.assertEqual(store.snapshot(include_filtered=True)[3], [0.0] * 5)
        self.assertEqual(store.snapshot()[2]['missing'], 1)

    def test_channel_switch_rebuilds_filter_and_preserves_raw(self):
        from domain.protocol import FrameParser
        parser, store = FrameParser(), SampleStore(channel=0)
        pairs = [(100, n * 100) for n in range(5)]
        store.publish(parser, parser.feed(frame(0, pairs)))
        self.assertEqual(store.snapshot(include_filtered=True)[3], [0.0] * 5)
        store.set_channel(1)
        reference = EcgFilter()
        self.assertEqual(store.snapshot()[1], pairs)
        self.assertEqual(store.snapshot(include_filtered=True)[3],
                         [reference.process(pair[1]) for pair in pairs])

    def test_frequency_response(self):
        def gain(frequency):
            filter_ = EcgFilter()
            values = [filter_.process(math.sin(2 * math.pi * frequency * n / 500))
                      for n in range(10000)]
            return math.sqrt(2 * sum(value * value for value in values[5000:]) / 5000)
        self.assertGreater(gain(10), 0.95)
        self.assertLess(gain(0.1), 0.05)
        self.assertLess(gain(50), 0.01)
        self.assertLess(gain(100), 0.025)
        self.assertLess(gain(49), 0.06)
        self.assertLess(gain(51), 0.06)
        self.assertLess(gain(100.2), 0.0001)
        self.assertLess(gain(150.3), 0.0001)

    def test_morphology_preserves_low_frequency_amplitude_and_phase(self):
        filter_ = EcgFilter(morphology=True)
        values = [filter_.process(math.sin(2 * math.pi * 0.5 * n / 500))
                  for n in range(30000)]
        sine = 2 * sum(values[n] * math.sin(2 * math.pi * 0.5 * n / 500)
                       for n in range(20000, 30000)) / 10000
        cosine = 2 * sum(values[n] * math.cos(2 * math.pi * 0.5 * n / 500)
                         for n in range(20000, 30000)) / 10000
        self.assertGreater(math.hypot(sine, cosine), 0.99)
        self.assertLess(abs(math.degrees(math.atan2(cosine, sine))), 8)

    def test_mode_switch_uses_continuous_state_not_short_history_restart(self):
        parser = type('Parser', (), dict(frames=0, missing_frames=0,
                                        crc_errors=0, sequence_errors=0))()
        store, reference = SampleStore(7, channel=0), EcgFilter(morphology=True)
        expected = []
        for seq in range(100):
            pairs = [(100000 + math.sin((seq * 5 + i) / 30) * 1000, 0)
                     for i in range(5)]
            store.publish(parser, [(seq, pairs)])
            expected.extend(reference.process(pair[0]) for pair in pairs)
        raw = store.snapshot()[1]
        store.set_mode(1)
        self.assertEqual(store.snapshot(include_filtered=True)[3], expected[-7:])
        self.assertEqual(store.snapshot()[1], raw)

    def test_streaming_history_and_session_reset(self):
        parser = type('Parser', (), dict(frames=0, missing_frames=0,
                                        crc_errors=0, sequence_errors=0))()
        pairs = [(100000 + n * 10, -n) for n in range(30)]
        whole, chunked = SampleStore(7, channel=0), SampleStore(7, channel=0)
        whole.publish(parser, [(0, pairs)])
        for start in range(0, len(pairs), 5):
            chunked.publish(parser, [(start // 5, pairs[start:start + 5])])
        self.assertEqual(whole.snapshot(include_filtered=True)[1:],
                         chunked.snapshot(include_filtered=True)[1:])
        self.assertEqual(len(chunked.snapshot(include_filtered=True)[3]), 7)
        chunked.publish(parser, [(0, [(900000, 0)] * 5)], reset=True)
        self.assertEqual(chunked.snapshot(include_filtered=True)[3], [0.0] * 5)


class PipelineTests(unittest.TestCase):
    def test_wrap_backpressure_and_close(self):
        ring = RingBuffer(7)
        payload = bytes(range(100))
        writer = Thread(target=ring.write, args=(payload,))
        writer.start()
        received = bytearray()
        while len(received) < len(payload):
            received.extend(ring.read(3)[1])
        writer.join(1)
        self.assertFalse(writer.is_alive())
        self.assertEqual(bytes(received), payload)
        ring.write(b'1234567')
        blocked = Thread(target=ring.write, args=(b'8',))
        blocked.start()
        ring.close()
        blocked.join(1)
        self.assertFalse(blocked.is_alive())

    def test_sessions_and_bounded_history(self):
        ring, store, stop = RingBuffer(128), SampleStore(7, channel=0), Event()
        worker = AnalysisThread(ring, store, stop)
        worker.start()
        try:
            packet = frame(255) + frame(0)
            for offset in range(0, len(packet), 3):
                ring.write(packet[offset:offset + 3])
            self.assertTrue(wait_for(lambda: store.snapshot()[2]['frames'] == 2))
            self.assertEqual(len(store.snapshot()[1]), 7)
            ring.write(frame(1)[:9])
            ring.new_session()
            ring.write(frame(45))
            self.assertTrue(wait_for(lambda: store.snapshot()[2]['frames'] == 1))
            self.assertEqual(store.snapshot()[2]['missing'], 0)
            self.assertEqual(len(store.snapshot()[1]), 5)
        finally:
            stop.set()
            ring.close()
            worker.join(1)
        self.assertFalse(worker.is_alive())

    def test_cdc_read_and_reconnect(self):
        ring, store, stop = RingBuffer(), SampleStore(channel=0), Event()
        communication = CommunicationThread(ring, stop)
        analysis = AnalysisThread(ring, store, stop)
        sessions = []

        class FakeSerial:
            def __init__(self, *args, **kwargs):
                self.remaining = bytearray(frame(17))
                sessions.append(self)
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.closed = True
            @property
            def in_waiting(self):
                return min(len(self.remaining), 4)
            def read(self, count):
                result = bytes(self.remaining[:count])
                del self.remaining[:count]
                if not result:
                    stop.wait(0.01)
                return result

        with patch('domain.communication.serial.Serial', FakeSerial):
            analysis.start()
            communication.configure('COM_TEST')
            communication.start()
            try:
                self.assertTrue(wait_for(lambda: store.snapshot()[2]['frames'] == 1))
                communication.configure('COM_TEST_2')
                self.assertTrue(wait_for(lambda: len(sessions) == 2))
                self.assertTrue(wait_for(lambda: store.snapshot()[2]['frames'] == 1
                                        and len(store.snapshot()[1]) == 5))
            finally:
                stop.set()
                ring.close()
                communication.join(1)
                analysis.join(1)
        self.assertFalse(communication.is_alive())
        self.assertTrue(all(session.closed for session in sessions))


if __name__ == '__main__':
    unittest.main()
