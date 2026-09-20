"""Receive Heart-T ADC frames without transmitting any serial data."""
import argparse
import time

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from domain.protocol import FrameParser, SAMPLES_PER_FRAME, crc8


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
