"""Receive HeartThirdESP ADC frames over Wi-Fi TCP."""
import argparse
import time
import socket

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from domain.protocol import FrameParser, SAMPLES_PER_FRAME, crc8


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", help="ESP32-S3 IP address or hostname")
    parser.add_argument("--all", action="store_true", help="display every sample pair")
    args = parser.parse_args()
    decoder = FrameParser()
    report_time = time.monotonic()
    try:
        with socket.create_connection((args.host, 45670), timeout=3) as port:
            port.settimeout(0.2)
            while True:
                try:
                    chunk = port.recv(4096)
                except socket.timeout:
                    continue
                if not chunk:
                    raise ConnectionError('Device closed TCP connection')
                frames = decoder.feed(chunk)
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
    except OSError as error:
        parser.exit(1, f"TCP error: {error}; reconnect to the ESP32-S3.\n")


if __name__ == "__main__":
    main()
