"""Protocol checks independent of serial hardware."""
import unittest
from receiver import FrameParser, crc8


def frame(sequence, pairs=None):
    if pairs is None:
        pairs = [(-8388608, 8388607), (-1, 0), (250, -250), (0xFA, -6), (42, 43)]
    payload = bytes([sequence]) + b"".join(
        value.to_bytes(3, "big", signed=True) for pair in pairs for value in pair)
    return b"\xFA" + payload + bytes([crc8(payload)])


class ReceiverTests(unittest.TestCase):
    def test_crc_reference(self):
        self.assertEqual(crc8(b"123456789"), 0xF4)

    def test_bytewise_signed_channels(self):
        parser = FrameParser()
        result = []
        for value in frame(7):
            result.extend(parser.feed(bytes([value])))
        self.assertEqual(result[0][0], 7)
        self.assertEqual(result[0][1], [(-8388608, 8388607), (-1, 0),
                                      (250, -250), (250, -6), (42, 43)])
        self.assertFalse(parser.buffer)

    def test_wrap_and_missing(self):
        parser = FrameParser()
        self.assertEqual(len(parser.feed(frame(254) + frame(255) + frame(0) + frame(3))), 4)
        self.assertEqual(parser.missing_frames, 2)

    def test_corruption_noise_and_partial(self):
        parser = FrameParser()
        damaged = bytearray(frame(11))
        damaged[5] ^= 1
        self.assertEqual(len(parser.feed(frame(10) + damaged + b"noise" + frame(12)[:9])), 1)
        self.assertEqual(parser.feed(frame(12)[9:])[0][0], 12)
        self.assertGreaterEqual(parser.crc_errors, 1)
        self.assertEqual(parser.missing_frames, 1)
        self.assertLess(len(parser.buffer), 33)

    def test_duplicate_sequence(self):
        parser = FrameParser()
        parser.feed(frame(1) + frame(1))
        self.assertEqual(parser.sequence_errors, 1)
        self.assertEqual(parser.missing_frames, 0)


if __name__ == "__main__":
    unittest.main()
