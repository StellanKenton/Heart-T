"""Device Tool entry for ESP-IDF build/flash/reset and TCP console."""
import os
import queue
import socket
import subprocess
import sys
import threading
from pathlib import Path

import device_tool

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _discover_host():
    sys.path.insert(0, str(PROJECT_ROOT / 'HeartThirdCore'))
    from domain.communication import available_ports
    devices = available_ports(timeout=1)
    if not devices:
        raise OSError('No HeartThirdESP found; set HEART_ESP_HOST to its IP address.')
    return devices[0]['port']


def console():
    host = os.environ.get('HEART_ESP_HOST') or _discover_host()
    print(f'Connecting TCP console to {host}:45671. Ctrl+C to stop.', flush=True)
    pending = queue.Queue()

    def read_input():
        for line in sys.stdin.buffer:
            pending.put(line)

    threading.Thread(target=read_input, daemon=True).start()
    with socket.create_connection((host, 45671), timeout=3) as connection:
        connection.settimeout(0.1)
        while True:
            try:
                line = pending.get_nowait()
            except queue.Empty:
                pass
            else:
                connection.sendall(line)
            try:
                payload = connection.recv(4096)
            except socket.timeout:
                continue
            if not payload:
                return 1
            sys.stdout.buffer.write(payload)
            sys.stdout.buffer.flush()


def run(action, profile):
    if action == 'console':
        try:
            return console()
        except (OSError, KeyboardInterrupt) as error:
            print(f'ESP console stopped: {error}', file=sys.stderr)
            return 1
    spec = profile.get('esp', {})
    idf_path = spec.get('idf_path') or os.environ.get('IDF_PATH')
    tools_path = spec.get('tools_path') or os.environ.get('IDF_TOOLS_PATH')
    if not idf_path or not tools_path:
        raise device_tool.DeviceToolError('ESP-IDF paths missing from computer profile.')
    command = [
        'pwsh', '-NoProfile', '-File', str(PROJECT_ROOT / 'develop' / 'run_esp_idf.ps1'),
        '-Action', action, '-IdfPath', idf_path, '-ToolsPath', tools_path,
        '-Port', os.environ.get('HEART_ESP_PORT', ''),
    ]
    return subprocess.run(command, cwd=PROJECT_ROOT, check=False).returncode
