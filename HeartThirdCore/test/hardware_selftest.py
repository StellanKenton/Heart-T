"""Measure live ESP32-S3 ADC/TCP integrity with the production frame parser."""
import argparse
import json
import re
import socket
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from domain.protocol import FrameParser
from domain.communication import available_ports

STATUS = re.compile(
    r'mode=(\w+) wifi=(\w+) ip=(\S+) uptime=(\d+) ms '
    r'samples=(\d+) missed=(\d+) tcp_dropped=(\d+)'
)


def read_status(connection):
    """Read a fresh response from the device's line-oriented console."""
    connection.sendall(b'status\n')
    deadline = time.monotonic() + 3
    pending = ''
    while time.monotonic() < deadline:
        try:
            pending += connection.recv(4096).decode('utf-8', 'replace')
        except socket.timeout:
            continue
        for line in pending.splitlines():
            match = STATUS.search(line)
            if match:
                mode, wifi, ip, uptime, samples, missed, dropped = match.groups()
                return dict(mode=mode, wifi=wifi, ip=ip, uptime_ms=int(uptime),
                            samples=int(samples), missed=int(missed),
                            tcp_dropped=int(dropped))
    raise TimeoutError('No status response from TCP console')


def measure(host, duration):
    parser = FrameParser()
    values = [[], []]
    with socket.create_connection((host, 45671), timeout=3) as console:
        console.settimeout(0.2)
        with socket.create_connection((host, 45670), timeout=3) as data:
            data.settimeout(0.2)
            # Begin after the first frame, so connection setup is outside the rate window.
            while not parser.frames:
                for _, pairs in parser.feed(data.recv(4096)):
                    for pair in pairs:
                        values[0].append(pair[0])
                        values[1].append(pair[1])
            before = read_status(console)
            start = time.monotonic()
            while time.monotonic() - start < duration:
                try:
                    chunk = data.recv(4096)
                except socket.timeout:
                    continue
                if not chunk:
                    raise ConnectionError('Data TCP connection closed during measurement')
                for _, pairs in parser.feed(chunk):
                    for pair in pairs:
                        values[0].append(pair[0])
                        values[1].append(pair[1])
            elapsed = time.monotonic() - start
            after = read_status(console)
    result = dict(host=host, duration_s=round(elapsed, 3), frames=parser.frames,
                  sample_pairs=len(values[0]), frame_rate_hz=round(parser.frames / elapsed, 2),
                  crc_errors=parser.crc_errors, missing_frames=parser.missing_frames,
                  duplicate_sequences=parser.sequence_errors,
                  ads_missed_delta=after['missed'] - before['missed'],
                  tcp_dropped_delta=after['tcp_dropped'] - before['tcp_dropped'],
                  ch1_range=[min(values[0]), max(values[0])],
                  ch2_range=[min(values[1]), max(values[1])],
                  ch1_std=round(statistics.pstdev(values[0]), 1),
                  ch2_std=round(statistics.pstdev(values[1]), 1),
                  before=before, after=after)
    result['pass'] = (before['mode'] == after['mode'] == 'NORMAL'
                      and before['wifi'] == after['wifi'] == 'connected'
                      and result['frame_rate_hz'] >= 98
                      and parser.crc_errors == parser.missing_frames == parser.sequence_errors == 0
                      and result['ads_missed_delta'] == result['tcp_dropped_delta'] == 0)
    return result


def reboot_and_wait(host):
    """Check that the TCP command restarts the device and Wi-Fi returns."""
    with socket.create_connection((host, 45671), timeout=3) as console:
        console.settimeout(0.2)
        before = read_status(console)
        console.sendall(b'reboot\n')
        response = ''
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                chunk = console.recv(4096)
            except socket.timeout:
                continue
            if not chunk:
                break
            response += chunk.decode('utf-8', 'replace')
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, 45671), timeout=1) as console:
                console.settimeout(0.2)
                after = read_status(console)
                if (after['mode'] == 'NORMAL' and after['wifi'] == 'connected'
                        and after['uptime_ms'] < before['uptime_ms']):
                    discovered = any(item['port'] == host for item in available_ports(0.5))
                    return dict(pass_=discovered, reboot_log='rebooting HeartThirdESP' in response,
                                discovery=discovered, before=before, after=after)
        except (OSError, TimeoutError):
            pass
        time.sleep(0.5)
    return dict(pass_=False, reboot_log='rebooting HeartThirdESP' in response,
                discovery=False, before=before, after=None)


def main():
    arguments = argparse.ArgumentParser(description=__doc__)
    arguments.add_argument('host', help='ESP32-S3 IP address')
    arguments.add_argument('--seconds', type=float, default=20)
    arguments.add_argument('--reboot', action='store_true', help='Verify TCP reboot and Wi-Fi recovery')
    args = arguments.parse_args()
    if args.seconds <= 0:
        arguments.error('--seconds must be positive')
    result = measure(args.host, args.seconds)
    if args.reboot:
        result['reboot'] = reboot_and_wait(args.host)
        result['pass'] = result['pass'] and result['reboot']['pass_'] and result['reboot']['reboot_log']
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result['pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
