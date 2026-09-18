"""Receive Heart-T ADC frames without transmitting any serial data."""
import argparse
import time

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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port", help="USB CDC port, e.g. COM25")
    parser.add_argument("--baud", type=int, default=115200,
                        help="CDC line coding only; does not change USB speed")
    parser.add_argument("--all", action="store_true", help="display every sample pair")
    args = parser.parse_args()
    import serial

    decoder = FrameParser()
    report_time = time.monotonic()
    try:
        with serial.Serial(args.port, args.baud, timeout=0.1) as port:
            while True:
                frames = decoder.feed(port.read(min(max(port.in_waiting, 1), 4096)))
                for sequence, samples in frames:
                    if args.all:
                        for index, (ch1, ch2) in enumerate(samples):
                            print(f"seq={sequence:3d} sample={index} ch1={ch1} ch2={ch2}")
                    if time.monotonic() - report_time >= 1:
                        ch1, ch2 = samples[-1]
                        print(f"frames={decoder.frames} samples={decoder.frames * SAMPLES_PER_FRAME} "
                              f"missing={decoder.missing_frames} crc_errors={decoder.crc_errors} "
                              f"sequence_errors={decoder.sequence_errors} ch1={ch1} ch2={ch2}")
                        report_time = time.monotonic()
    except KeyboardInterrupt:
        pass
    except serial.SerialException as error:
        parser.exit(1, f"Serial error: {error}; reopen the receiver after reconnecting the device.\n")


if __name__ == "__main__":
    main()
