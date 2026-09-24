"""Wi-Fi discovery and separate TCP workers for samples and console I/O."""
import codecs
import logging
import select
import socket
import time
from queue import Empty, Queue
from threading import Lock, Thread

LOG = logging.getLogger(__name__)
DATA_PORT = 45670
CONSOLE_PORT = 45671
DISCOVERY_PORT = 45672
DISCOVERY_REQUEST = b'HEARTTHIRD_DISCOVER'
DISCOVERY_REPLY = b'HEARTTHIRD_ESP32S3'


def available_ports(timeout=0.25):
    """Discover ESP32-S3 devices on the local LAN; targets remain editable."""
    found = {}
    probes = []
    try:
        addresses = socket.gethostbyname_ex(socket.gethostname())[2]
        for address in dict.fromkeys(addresses + ['0.0.0.0']):
            if address.startswith('127.') or address.startswith('169.254.'):
                continue
            probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                probe.bind((address, 0))
                probe.setblocking(False)
                probe.sendto(DISCOVERY_REQUEST, ('255.255.255.255', DISCOVERY_PORT))
                probes.append(probe)
            except OSError:
                probe.close()
        deadline = time.monotonic() + timeout
        while probes and time.monotonic() < deadline:
            ready, _, _ = select.select(probes, [], [], max(0, deadline - time.monotonic()))
            for probe in ready:
                try:
                    packet, address = probe.recvfrom(128)
                except OSError:
                    continue
                if packet == DISCOVERY_REPLY:
                    found[address[0]] = dict(port=address[0], label=f"HeartThirdESP · {address[0]}")
    except OSError as error:
        LOG.debug('Wi-Fi discovery unavailable: %s', error)
    finally:
        for probe in probes:
            probe.close()
    return list(found.values())


class CommunicationThread(Thread):
    """Receive the unchanged 33-byte frame stream and reconnect on network loss."""

    def __init__(self, ring, stop, port=DATA_PORT):
        super().__init__(name='communication')
        self.ring, self.stop, self.port = ring, stop, port
        self._lock = Lock()
        self._target = None
        self._generation = 0
        self._status = '未连接'

    def configure(self, target):
        with self._lock:
            self._target = target.strip() if target else None
            self._generation += 1

    def status(self):
        with self._lock:
            return self._status

    def _set_status(self, status):
        with self._lock:
            self._status = status

    def _selection(self):
        with self._lock:
            return self._target, self._generation

    def run(self):
        while not self.stop.is_set():
            target, generation = self._selection()
            if target is None:
                self._set_status('未连接')
                self.stop.wait(0.1)
                continue
            self.ring.new_session()
            try:
                self._set_status(f'正在连接 {target}:{self.port}')
                with socket.create_connection((target, self.port), timeout=2) as connection:
                    connection.settimeout(0.2)
                    self._set_status(f'已连接 {target}:{self.port}')
                    while not self.stop.is_set() and self._selection()[1] == generation:
                        try:
                            data = connection.recv(4096)
                        except socket.timeout:
                            continue
                        if not data:
                            raise ConnectionError('设备已断开')
                        self.ring.write(data)
            except OSError as error:
                if not isinstance(error, ConnectionError):
                    LOG.warning('TCP data connection failed: %s', error)
                self._set_status(f'连接中断：{error} · 1 秒后重试')
                deadline = time.monotonic() + 1
                while (not self.stop.is_set() and self._selection()[1] == generation
                       and time.monotonic() < deadline):
                    self.stop.wait(0.1)


class ConsoleThread(Thread):
    """Receive TCP logs and send line commands without blocking the GUI."""

    def __init__(self, stop, port=CONSOLE_PORT):
        super().__init__(name='tcp-console')
        self.stop, self.port = stop, port
        self._lock = Lock()
        self._target = None
        self._generation = 0
        self._status = '日志未连接'
        self._text = ''
        self._revision = 0
        self._commands = Queue()

    def configure(self, target):
        with self._lock:
            self._target = target.strip() if target else None
            self._generation += 1
            self._status = '日志未连接'
            self._revision += 1
        while True:
            try:
                self._commands.get_nowait()
            except Empty:
                break

    def send_command(self, command):
        if command.strip() and self.snapshot()[1].startswith('日志已连接'):
            self._commands.put(command.strip() + '\n')

    def snapshot(self):
        with self._lock:
            return self._revision, self._status, self._text

    def _selection(self):
        with self._lock:
            return self._target, self._generation

    def _update(self, status=None, text=None):
        with self._lock:
            if status is not None and status != self._status:
                self._status = status
                self._revision += 1
            if text:
                self._text = (self._text + text)[-20000:]
                self._revision += 1

    def run(self):
        while not self.stop.is_set():
            target, generation = self._selection()
            if not target:
                self._update(status='日志未连接')
                self.stop.wait(0.2)
                continue
            try:
                self._update(status=f'正在连接日志 {target}:{self.port}')
                decoder = codecs.getincrementaldecoder('utf-8')('replace')
                with socket.create_connection((target, self.port), timeout=2) as connection:
                    connection.settimeout(0.1)
                    self._update(status=f'日志已连接 {target}:{self.port}')
                    while not self.stop.is_set() and self._selection()[1] == generation:
                        try:
                            command = self._commands.get_nowait()
                        except Empty:
                            pass
                        else:
                            connection.sendall(command.encode('utf-8'))
                        try:
                            data = connection.recv(4096)
                        except socket.timeout:
                            continue
                        if not data:
                            raise ConnectionError('日志连接已关闭')
                        self._update(text=decoder.decode(data))
            except OSError as error:
                if not isinstance(error, ConnectionError):
                    LOG.warning('TCP console connection failed: %s', error)
                self._update(status=f'日志连接中断：{error} · 1 秒后重试')
                deadline = time.monotonic() + 1
                while (not self.stop.is_set() and self._selection()[1] == generation
                       and time.monotonic() < deadline):
                    self.stop.wait(0.1)
