"""Heart-T 33-byte sample protocol; signed 24-bit samples and CRC-8/SMBUS."""
HEADER = 0xFA
FRAME_SIZE = 33
SAMPLES_PER_FRAME = 5


def crc8(data):
    """CRC-8/SMBUS over sequence and sample payload."""
    crc = 0
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = ((crc << 1) ^ (0x07 if crc & 0x80 else 0)) & 0xFF
    return crc


class FrameParser:
    """Parse arbitrary read boundaries; recover alignment after damaged frames."""

    def __init__(self):
        self.buffer = bytearray()
        self.last_sequence = None
        self.frames = 0
        self.missing_frames = 0
        self.crc_errors = 0
        self.sequence_errors = 0

    def feed(self, data):
        self.buffer.extend(data)
        result = []
        while self.buffer:
            start = self.buffer.find(bytes([HEADER]))
            if start < 0:
                self.buffer.clear()
                break
            del self.buffer[:start]
            if len(self.buffer) < FRAME_SIZE:
                break
            frame = self.buffer[:FRAME_SIZE]
            if crc8(frame[1:-1]) != frame[-1]:
                self.crc_errors += 1
                del self.buffer[0]
                continue
            del self.buffer[:FRAME_SIZE]
            sequence = frame[1]
            if self.last_sequence is not None:
                delta = (sequence - self.last_sequence) & 0xFF
                if delta == 0:
                    self.sequence_errors += 1
                else:
                    self.missing_frames += delta - 1
            self.last_sequence = sequence
            samples = []
            for offset in range(2, FRAME_SIZE - 1, 6):
                samples.append((
                    int.from_bytes(frame[offset:offset + 3], "big", signed=True),
                    int.from_bytes(frame[offset + 3:offset + 6], "big", signed=True),
                ))
            self.frames += 1
            result.append((sequence, samples))
        return result
